'use client';

import { useCallback, useMemo, useState } from 'react';
import type { DropEvent } from 'react-dropzone';
import { useDropzone } from 'react-dropzone';
import { v4 as uuidv4 } from 'uuid';
import { getBrowserSupabaseClient } from '../lib/supabaseBrowser';

type UploadStatus = 'idle' | 'preparing' | 'uploading' | 'persisting' | 'complete' | 'error';

type UploadEntry = {
  id: string;
  file: File;
  status: UploadStatus;
  progress: number;
  error?: string;
  presignedGetUrl?: string;
};

type UploadDropzoneProps = {
  bucket: string;
  namespace?: string;
  tags?: string[];
  className?: string;
  author?: string;
};

type PresignResponse = {
  url: string;
  method: string;
  headers?: Record<string, string>;
  fields?: Record<string, string>;
};

const KB = 1024;
const MB = KB * 1024;

const formatBytes = (bytes: number) => {
  if (!Number.isFinite(bytes)) return '';
  if (bytes >= MB) return `${(bytes / MB).toFixed(1)} MB`;
  if (bytes >= KB) return `${(bytes / KB).toFixed(1)} KB`;
  return `${bytes} B`;
};

async function requestPresign(body: Record<string, unknown>): Promise<PresignResponse> {
  const res = await fetch('/api/uploads/presign', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const message = await res.text();
    throw new Error(message || `Failed to fetch presigned URL (${res.status})`);
  }
  return res.json();
}

async function uploadViaPresign(url: string, file: File, headers: Record<string, string> | undefined, onProgress: (pct: number) => void) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      const pct = Math.round((event.loaded / event.total) * 100);
      onProgress(pct);
    };
    xhr.onerror = () => reject(new Error('Upload failed'));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100);
        resolve();
      } else {
        reject(new Error(`Upload failed (${xhr.status})`));
      }
    };
    xhr.open('PUT', url, true);
    if (headers) {
      for (const [key, value] of Object.entries(headers)) {
        if (value) xhr.setRequestHeader(key, value);
      }
    }
    xhr.send(file);
  });
}

async function persistMetadata(payload: Record<string, unknown>) {
  const res = await fetch('/api/uploads/persist', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to persist upload (${res.status})`);
  }
  return res.json();
}

export function UploadDropzone({ bucket, namespace = 'pmoves', tags = [], className, author }: UploadDropzoneProps) {
  const [uploads, setUploads] = useState<UploadEntry[]>([]);
  const supabase = useMemo(() => {
    try {
      return getBrowserSupabaseClient();
    } catch (err) {
      console.warn('Supabase client unavailable', err);
      return null;
    }
  }, []);

  const updateUpload = useCallback((id: string, patch: Partial<UploadEntry>) => {
    setUploads((items) => items.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }, []);

  const createUploadEvent = useCallback(
    async (id: string, file: File, status: UploadStatus, progress: number, extra: Record<string, unknown> = {}) => {
      if (!supabase) return;

      const { object_key, error_message, ...metaRest } = extra;
      const metaPayload: Record<string, unknown> = {
        namespace,
        tags,
        ingest: 'ui-dropzone',
        author,
        ...metaRest,
      };
      if (typeof object_key === 'string') {
        metaPayload.object_key = object_key;
      }

      await supabase.from('upload_events').upsert([
        {
          upload_id: id,
          filename: file.name,
          bucket,
          object_key: typeof object_key === 'string' ? object_key : null,
          status,
          progress,
          error_message: typeof error_message === 'string' ? error_message : null,
          size_bytes: file.size,
          content_type: file.type,
          meta: metaPayload,
        },
      ]);
    },
    [author, bucket, namespace, supabase, tags]
  );

  const onDrop = useCallback(
    async (acceptedFiles: File[], _rejected: File[], _event: DropEvent) => {
      for (const file of acceptedFiles) {
        const uploadId = uuidv4();
        const entry: UploadEntry = { id: uploadId, file, status: 'preparing', progress: 0 };
        setUploads((prev) => [entry, ...prev]);

        const objectKey = `${namespace}/uploads/${uploadId}/${file.name}`;
        try {
          await createUploadEvent(uploadId, file, 'preparing', 0, { object_key: objectKey, author });

          updateUpload(uploadId, { status: 'preparing' });
          const presign = await requestPresign({
            bucket,
            key: objectKey,
            method: 'put',
            contentType: file.type,
          });

          await createUploadEvent(uploadId, file, 'uploading', 1, { object_key: objectKey, author });
          updateUpload(uploadId, { status: 'uploading', progress: 1 });

          await uploadViaPresign(presign.url, file, presign.headers, (pct) => {
            updateUpload(uploadId, { progress: pct });
            createUploadEvent(uploadId, file, 'uploading', pct, { object_key: objectKey, author }).catch((err) => {
              console.warn('Failed to update upload progress', err);
            });
          });

          updateUpload(uploadId, { status: 'persisting', progress: 100 });
          await createUploadEvent(uploadId, file, 'persisting', 100, { object_key: objectKey, author });

          const persistResult = await persistMetadata({
            uploadId,
            bucket,
            key: objectKey,
            namespace,
            title: file.name,
            size: file.size,
            contentType: file.type,
            tags,
            author,
          });

          const presignedGetUrl = persistResult?.presignedGetUrl as string | undefined;
          updateUpload(uploadId, { status: 'complete', progress: 100, presignedGetUrl });
          await createUploadEvent(uploadId, file, 'complete', 100, {
            object_key: objectKey,
            presigned_get: presignedGetUrl,
            author,
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Upload failed';
          updateUpload(uploadId, { status: 'error', error: message });
          await createUploadEvent(uploadId, file, 'error', 0, {
            object_key: objectKey,
            error_message: message,
            author,
          }).catch(() => undefined);
        }
      }
    },
    [author, bucket, createUploadEvent, namespace, tags, updateUpload]
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    noClick: true,
    multiple: true,
  });

  return (
    <div className={className}>
      <div
        {...getRootProps({
          className:
            'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center transition hover:border-slate-500 hover:bg-white',
        })}
      >
        <input {...getInputProps()} />
        <div className="text-lg font-semibold text-slate-800">Upload creative assets</div>
        <p className="max-w-lg text-sm text-slate-500">
          Drag &amp; drop renders or voiceovers here, or
          <button
            type="button"
            onClick={open}
            className="ml-1 rounded bg-slate-900 px-2 py-1 text-sm font-medium text-white hover:bg-slate-700"
          >
            browse files
          </button>
        </p>
        <p className="text-xs uppercase tracking-wide text-slate-400">
          Target bucket: <span className="font-mono text-slate-600">{bucket}</span>
        </p>
        {isDragActive && <p className="text-sm text-slate-600">Release to start the upload…</p>}
      </div>

      {uploads.length > 0 && (
        <div className="mt-6 space-y-3">
          {uploads.map((upload) => (
            <div key={upload.id} className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-slate-900">{upload.file.name}</div>
                  <div className="text-xs text-slate-500">{formatBytes(upload.file.size)}</div>
                </div>
                <span
                  className={
                    upload.status === 'complete'
                      ? 'rounded bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700'
                      : upload.status === 'error'
                      ? 'rounded bg-rose-100 px-2 py-1 text-xs font-medium text-rose-700'
                      : 'rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600'
                  }
                >
                  {upload.status}
                </span>
              </div>
              <div className="mt-3 h-2 w-full rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-slate-900 transition-all"
                  style={{ width: `${upload.progress}%` }}
                />
              </div>
              {upload.error && <p className="mt-2 text-xs text-rose-600">{upload.error}</p>}
              {upload.presignedGetUrl && (
                <a
                  href={upload.presignedGetUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-flex items-center text-xs font-medium text-slate-700 hover:underline"
                >
                  View asset
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default UploadDropzone;
