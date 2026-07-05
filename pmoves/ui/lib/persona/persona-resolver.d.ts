export function agentThemeURL(
  id: string,
  opts?: { alter?: string | null; gw?: string }
): string;
export function fetchAgentTheme(
  id: string,
  opts?: {
    alter?: string | null;
    gw?: string;
    fetchImpl?: typeof fetch;
    timeoutMs?: number;
  }
): Promise<any>;
