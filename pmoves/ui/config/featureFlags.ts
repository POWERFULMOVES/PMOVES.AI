const truthy = new Set(['1', 'true', 'yes']);

const getFlag = (envKey: string, fallback = false): boolean => {
  const value = process.env[envKey];
  if (value === undefined) {
    return fallback;
  }
  return truthy.has(value.toLowerCase());
};

export const featureFlags = {
  passwordAuth: getFlag('NEXT_PUBLIC_SUPABASE_PASSWORD_AUTH_ENABLED', true),
  oauth: getFlag('NEXT_PUBLIC_SUPABASE_OAUTH_ENABLED', true)
};
