export function setTheme(name: string): void;
export function currentTheme(): string;
export function toggleTheme(a?: string, b?: string): void;
export function applyPersonaThemeToRoot(
  theme: any,
  root?: HTMLElement
): Record<string, string>;
export function clearPersona(root?: HTMLElement): void;
export function setPersona(
  id: string,
  opts?: {
    root?: HTMLElement;
    alter?: string | null;
    gw?: string;
    fetchImpl?: typeof fetch;
    timeoutMs?: number;
  }
): Promise<Record<string, string> | null>;
