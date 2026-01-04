import fs from 'node:fs';
import path from 'node:path';
import { cache } from 'react';
import toml from 'toml';

export type SupabaseOAuthProvider = {
  key: string;
  label: string;
};

type SupabaseConfig = {
  auth?: {
    external?: Record<string, { enabled?: boolean; name?: string }>;
  };
};

const formatLabel = (providerKey: string): string =>
  providerKey
    .split('_')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');

const resolveConfigPath = (): string => {
  const candidates = [
    path.resolve(process.cwd(), '..', 'supabase', 'config.toml'),
    path.resolve(process.cwd(), 'supabase', 'config.toml'),
    path.resolve(process.cwd(), '..', '..', 'supabase', 'config.toml')
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return candidates[0];
};

const readSupabaseConfig = (): SupabaseConfig => {
  const configPath = resolveConfigPath();

  if (!fs.existsSync(configPath)) {
    return {};
  }

  const fileContent = fs.readFileSync(configPath, 'utf8');
  return toml.parse(fileContent) as SupabaseConfig;
};

export const getEnabledAuthProviders = cache((): SupabaseOAuthProvider[] => {
  const config = readSupabaseConfig();
  const external = config.auth?.external ?? {};

  return Object.entries(external)
    .filter(([, settings]) => settings?.enabled)
    .map(([key, settings]) => ({
      key,
      label: settings?.name ?? formatLabel(key)
    }));
});
