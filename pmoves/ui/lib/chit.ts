import fs from 'fs/promises';
import fsSync from 'fs';
import path from 'path';
import YAML from 'yaml';

export type ChitManifestEntry = {
  id: string;
  source: { type: string; label: string };
  targets: Array<{ file: string; key: string }>;
  required?: boolean;
};

export type ChitManifest = {
  version: number;
  cgp_file: string;
  entries: ChitManifestEntry[];
};

export type ChitEntryStatus = {
  id: string;
  label: string;
  required: boolean;
  satisfied: boolean;
  targets: Array<{
    key: string;
    file: string;
    present: boolean;
  }>;
};

export type ChitLiveData = {
  manifestPath: string;
  cgpFilePath: string;
  cgpFileExists: boolean;
  entries: ChitEntryStatus[];
  stats: {
    total: number;
    required: number;
    satisfied: number;
    missingRequired: number;
    optionalMissing: number;
  };
  error?: string;
};

function resolveRepoRoot(): string {
  const cwd = process.cwd();
  const candidates = [path.resolve(cwd, '..', '..'), path.resolve(cwd, '..'), cwd];

  for (const candidate of candidates) {
    const manifestCandidate = path.resolve(candidate, 'pmoves', 'chit', 'secrets_manifest.yaml');
    if (fsSync.existsSync(manifestCandidate)) {
      return candidate;
    }
  }

  return cwd;
}

function resolveManifestPath(): string {
  const repoRoot = resolveRepoRoot();
  const manifestPath = path.resolve(repoRoot, 'pmoves', 'chit', 'secrets_manifest.yaml');
  if (fsSync.existsSync(manifestPath)) {
    return manifestPath;
  }
  return path.resolve(repoRoot, 'chit', 'secrets_manifest.yaml');
}

function resolveCgpPath(cgpFile: string | undefined): string {
  if (!cgpFile) return '';
  if (path.isAbsolute(cgpFile)) return cgpFile;
  const repoRoot = resolveRepoRoot();
  return path.resolve(repoRoot, cgpFile);
}

export async function getChitLiveData(): Promise<ChitLiveData> {
  const manifestPath = resolveManifestPath();

  try {
    const raw = await fs.readFile(manifestPath, 'utf-8');
    const parsed = YAML.parse(raw) as ChitManifest;
    const entries = Array.isArray(parsed?.entries) ? parsed.entries : [];
    const envCache = await loadTargetEnvValues(entries);

    const entryStatuses: ChitEntryStatus[] = entries.map((entry) => {
      const required = entry.required !== false;
      const targets = (entry.targets || []).map((target) => {
        const present = hasValue(process.env[target.key]) || hasValue(envCache.get(target.file)?.[target.key]);
        return {
          key: target.key,
          file: target.file,
          present,
        };
      });
      const satisfied = targets.length === 0 || targets.every((target) => target.present);
      return {
        id: entry.id,
        label: entry.source?.label ?? entry.id,
        required,
        targets,
        satisfied,
      };
    });

    const cgpFilePath = resolveCgpPath(parsed?.cgp_file);
    const cgpFileExists = Boolean(cgpFilePath) && (await fileExists(cgpFilePath));

    const total = entryStatuses.length;
    const requiredCount = entryStatuses.filter((entry) => entry.required).length;
    const satisfiedCount = entryStatuses.filter((entry) => entry.satisfied).length;
    const missingRequired = entryStatuses.filter((entry) => entry.required && !entry.satisfied).length;
    const optionalMissing = entryStatuses.filter((entry) => !entry.required && !entry.satisfied).length;

    return {
      manifestPath,
      cgpFilePath,
      cgpFileExists,
      entries: entryStatuses,
      stats: {
        total,
        required: requiredCount,
        satisfied: satisfiedCount,
        missingRequired,
        optionalMissing,
      },
    };
  } catch (error: any) {
    return {
      manifestPath,
      cgpFilePath: '',
      cgpFileExists: false,
      entries: [],
      stats: {
        total: 0,
        required: 0,
        satisfied: 0,
        missingRequired: 0,
        optionalMissing: 0,
      },
      error: error?.message ?? 'Unable to load CHIT manifest',
    };
  }
}

async function fileExists(targetPath: string): Promise<boolean> {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function loadTargetEnvValues(entries: ChitManifestEntry[]): Promise<Map<string, Record<string, string>>> {
  const repoRoot = resolveRepoRoot();
  const cache = new Map<string, Record<string, string>>();
  const seen = new Set<string>();

  for (const entry of entries) {
    for (const target of entry.targets ?? []) {
      if (!target?.file || seen.has(target.file)) continue;
      seen.add(target.file);
      const values = await readEnvFile(repoRoot, target.file);
      if (values) {
        cache.set(target.file, values);
      }
    }
  }

  return cache;
}

async function readEnvFile(repoRoot: string, relativePath: string): Promise<Record<string, string> | undefined> {
  const candidates = [path.resolve(repoRoot, relativePath)];
  const prefixed = path.resolve(repoRoot, 'pmoves', relativePath);
  if (!candidates.includes(prefixed)) {
    candidates.push(prefixed);
  }

  for (const candidate of candidates) {
    try {
      await fs.access(candidate);
      const content = await fs.readFile(candidate, 'utf-8');
      return parseEnvLines(content);
    } catch {
      continue;
    }
  }

  return undefined;
}

function parseEnvLines(content: string): Record<string, string> {
  const result: Record<string, string> = {};
  const lines = content.split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const idx = trimmed.indexOf('=');
    if (idx <= 0) continue;
    const key = trimmed.slice(0, idx).trim();
    const value = trimmed.slice(idx + 1).trim();
    if (key) {
      result[key] = value;
    }
  }
  return result;
}

function hasValue(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}
