import { SupabaseClient, createClient } from '@supabase/supabase-js';

export type ArchonPrompt = {
  id: string;
  prompt_name: string;
  prompt: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type ArchonPromptInput = {
  prompt_name: string;
  prompt: string;
  description?: string | null;
};

export class DuplicatePromptNameError extends Error {
  constructor(message = 'A prompt with this name already exists.') {
    super(message);
    this.name = 'DuplicatePromptNameError';
  }
}

export class PolicyViolationError extends Error {
  constructor(message = 'Operation blocked by row level security policy.') {
    super(message);
    this.name = 'PolicyViolationError';
  }
}

const TABLE_NAME = 'archon_prompts';

let cachedAnonClient: SupabaseClient | null = null;
let cachedServiceClient: SupabaseClient | null = null;

function getSupabaseUrl(): string {
  const url =
    process.env.NEXT_PUBLIC_SUPABASE_URL ||
    process.env.SUPABASE_URL ||
    process.env.PUBLIC_SUPABASE_URL;

  if (!url) {
    throw new Error('Supabase URL is not configured.');
  }

  return url;
}

function getAnonKey(): string {
  const key =
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    process.env.PUBLIC_SUPABASE_ANON_KEY;

  if (!key) {
    throw new Error('Supabase anonymous key is not configured.');
  }

  return key;
}

function getServiceRoleKey(): string {
  const key =
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    process.env.SUPABASE_SERVICE_KEY ||
    process.env.PRIVATE_SUPABASE_SERVICE_ROLE_KEY;

  if (!key) {
    throw new Error(
      'Supabase service role key is not configured. Server side writes require the service role due to RLS.'
    );
  }

  return key;
}

function ensureAnonClient(): SupabaseClient {
  if (!cachedAnonClient) {
    cachedAnonClient = createClient(getSupabaseUrl(), getAnonKey(), {
      auth: { persistSession: false },
    });
  }
  return cachedAnonClient;
}

function ensureServiceClient(): SupabaseClient {
  if (!cachedServiceClient) {
    cachedServiceClient = createClient(getSupabaseUrl(), getServiceRoleKey(), {
      auth: { persistSession: false },
    });
  }
  return cachedServiceClient;
}

function normalizeInput(values: ArchonPromptInput): ArchonPromptInput {
  return {
    prompt_name: values.prompt_name.trim(),
    prompt: values.prompt,
    description:
      values.description === undefined || values.description === null || values.description === ''
        ? null
        : values.description,
  };
}

function translateError(error: { code?: string; message: string }): Error {
  if (!error) {
    return new Error('Unknown Supabase error.');
  }

  if (error.code === '23505') {
    return new DuplicatePromptNameError();
  }

  if (error.code === '42501' || /row level security/i.test(error.message)) {
    return new PolicyViolationError();
  }

  return new Error(error.message);
}

export async function listArchonPrompts(
  search?: string,
  options?: { client?: SupabaseClient }
): Promise<ArchonPrompt[]> {
  const client = options?.client ?? ensureAnonClient();

  let query = client
    .from(TABLE_NAME)
    .select('*')
    .order('prompt_name', { ascending: true });

  if (search && search.trim()) {
    query = query.ilike('prompt_name', `%${search.trim()}%`);
  }

  const { data, error } = await query;

  if (error) {
    throw translateError(error);
  }

  return (data as ArchonPrompt[]) ?? [];
}

export async function createArchonPrompt(
  values: ArchonPromptInput,
  options?: { client?: SupabaseClient }
): Promise<ArchonPrompt> {
  const client = options?.client ?? ensureServiceClient();
  const payload = normalizeInput(values);

  if (!payload.prompt_name) {
    throw new Error('Prompt name is required.');
  }

  if (!payload.prompt) {
    throw new Error('Prompt body is required.');
  }

  const { data, error } = await client
    .from(TABLE_NAME)
    .insert([payload])
    .select()
    .single();

  if (error) {
    throw translateError(error);
  }

  return data as ArchonPrompt;
}

export async function updateArchonPrompt(
  id: string,
  values: Partial<ArchonPromptInput>,
  options?: { client?: SupabaseClient }
): Promise<ArchonPrompt> {
  const client = options?.client ?? ensureServiceClient();
  const payload = normalizeInput({
    prompt_name: values.prompt_name ?? '',
    prompt: values.prompt ?? '',
    description: values.description ?? null,
  });

  if (!id) {
    throw new Error('Prompt id is required.');
  }

  if (!payload.prompt_name || !payload.prompt) {
    throw new Error('Prompt name and body are required for updates.');
  }

  const { data, error } = await client
    .from(TABLE_NAME)
    .update(payload)
    .eq('id', id)
    .select()
    .single();

  if (error) {
    throw translateError(error);
  }

  return data as ArchonPrompt;
}

export async function deleteArchonPrompt(
  id: string,
  options?: { client?: SupabaseClient }
): Promise<void> {
  const client = options?.client ?? ensureServiceClient();

  if (!id) {
    throw new Error('Prompt id is required.');
  }

  const { error } = await client.from(TABLE_NAME).delete().eq('id', id);

  if (error) {
    throw translateError(error);
  }
}

export function resetSupabaseClients() {
  cachedAnonClient = null;
  cachedServiceClient = null;
}
