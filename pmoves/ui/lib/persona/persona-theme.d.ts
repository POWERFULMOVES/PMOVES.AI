export function personaThemeVars(theme: any): Record<string, string>;
export function resolvePersonaFromURL(
  search: string
): { id: string; alter: string | null; gw: string | null } | null;
export function stageFromShowtimeEvent(evt: any): "live" | null;
export function alterOptions(
  sig: any
): Array<{ value: string; label: string }>;
