'use client';

import { useCallback, useMemo, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { v4 as uuidv4 } from 'uuid';
import type { Database, Json } from '../lib/database.types';
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
  ownerId: string;
};

type UploadEventInsert = Database['public']['Tables']['upload_events']['Insert'];

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

export function UploadDropzone({
  bucket,
  namespace = 'pmoves',
  tags = [],
  className,
  author,
  ownerId,
}: UploadDropzoneProps) {
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
      const metaPayload: Record<string, Json> = {
        namespace,
        tags,
        ingest: 'ui-dropzone',
        owner_id: ownerId,
        ...metaRest,
      };
      if (author) {
        metaPayload.author = author;
      }
      if (typeof object_key === 'string') {
        metaPayload.object_key = object_key;
      }
      const record: UploadEventInsert = {
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
        owner_id: ownerId,
      };

      await supabase.from('upload_events').upsert([record]);
    },
    [author, bucket, namespace, ownerId, supabase, tags]
  );

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (!ownerId) {
        console.error('UploadDropzone: missing ownerId, aborting upload.');
        return;
      }
      for (const file of acceptedFiles) {
        const uploadId = uuidv4();
        const entry: UploadEntry = { id: uploadId, file, status: 'preparing', progress: 0 };
        setUploads((prev) => [entry, ...prev]);

        const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
        const objectKey = `${namespace}/users/${ownerId}/uploads/${uploadId}/${safeName}`;
        try {
          await createUploadEvent(uploadId, file, 'preparing', 0, { object_key: objectKey, author });

          updateUpload(uploadId, { status: 'preparing' });
          const presign = await requestPresign({
            bucket,
            key: objectKey,
            method: 'put',
            contentType: file.type,
            uploadId,
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
            ownerId,
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
    [author, bucket, createUploadEvent, namespace, ownerId, tags, updateUpload]
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
            'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-brand-border bg-brand-surface-muted p-8 text-center transition hover:border-brand-slate hover:bg-brand-inverse',
        })}
      >
        <input {...getInputProps()} />
        <div className="text-lg font-semibold text-brand-ink">Upload creative assets</div>
        <p className="max-w-lg text-sm text-brand-muted">
          Drag &amp; drop renders or voiceovers here, or
          <button
            type="button"
            onClick={open}
            className="ml-1 rounded bg-brand-forest px-2 py-1 text-sm font-medium text-brand-ink-strong hover:bg-brand-gold"
          >
            browse files
          </button>
        </p>
        <p className="text-xs uppercase tracking-wide text-brand-subtle">
          Target bucket: <span className="font-mono text-brand-muted">{bucket}</span>
        </p>
        {isDragActive && <p className="text-sm text-brand-muted">Release to start the upload…</p>}
      </div>

      {uploads.length > 0 && (
        <div className="mt-6 space-y-3">
          {uploads.map((upload) => (
            <div key={upload.id} className="rounded-md border border-brand-border bg-brand-inverse p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-brand-ink">{upload.file.name}</div>
                  <div className="text-xs text-brand-subtle">{formatBytes(upload.file.size)}</div>
                </div>
                <span
                  className={
                    upload.status === 'complete'
                      ? 'rounded border border-brand-forest bg-brand-inverse px-2 py-1 text-xs font-medium text-brand-forest'
                      : upload.status === 'error'
                      ? 'rounded border border-brand-crimson bg-brand-inverse px-2 py-1 text-xs font-medium text-brand-crimson'
                      : 'rounded border border-brand-border bg-brand-surface-muted px-2 py-1 text-xs font-medium text-brand-muted'
                  }
                >
                  {upload.status}
                </span>
              </div>
              <div className="mt-3 h-2 w-full rounded-full bg-brand-surface-muted">
                <div
                  className="h-2 rounded-full bg-brand-forest transition-all"
                  style={{ width: `${upload.progress}%` }}
                />
              </div>
              {upload.error && <p className="mt-2 text-xs text-brand-crimson">{upload.error}</p>}
              {upload.presignedGetUrl && (
                <a
                  href={upload.presignedGetUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-flex items-center text-xs font-medium text-brand-ink hover:text-brand-ink-strong hover:underline"
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
