export type UIConfig = {
  supabaseUrl: string;
  supabaseAnonKey: string;
  supabaseServiceRoleKey?: string;
  supabaseRestUrl?: string;
  supabaseRealtimeUrl?: string;
  apiUrl: string;
  websocketUrl: string;
};

const getRequiredEnv = (...keys: string[]): string => {
  for (const key of keys) {
    const value = process.env[key];
    if (value) {
      return value;
    }
  }

  throw new Error(`Missing required environment variable. Checked: ${keys.join(", ")}`);
};

const getOptionalEnv = (...keys: string[]): string | undefined => {
  for (const key of keys) {
    const value = process.env[key];
    if (value) {
      return value;
    }
  }
  return undefined;
};

export const uiConfig: UIConfig = {
  supabaseUrl: getRequiredEnv("NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_URL"),
  supabaseAnonKey: getRequiredEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "SUPABASE_ANON_KEY"),
  supabaseServiceRoleKey: getOptionalEnv("SUPABASE_SERVICE_ROLE_KEY"),
  supabaseRestUrl: getOptionalEnv("NEXT_PUBLIC_SUPABASE_REST_URL", "SUPABASE_REST_URL"),
  supabaseRealtimeUrl: getOptionalEnv("NEXT_PUBLIC_SUPABASE_REALTIME_URL", "SUPABASE_REALTIME_URL"),
  apiUrl: getOptionalEnv("NEXT_PUBLIC_PMOVES_API_URL", "PMOVES_API_URL") ?? "http://localhost:8080",
  websocketUrl: getOptionalEnv("NEXT_PUBLIC_PMOVES_WS_URL", "PMOVES_WS_URL") ?? "ws://localhost:8080",
};
