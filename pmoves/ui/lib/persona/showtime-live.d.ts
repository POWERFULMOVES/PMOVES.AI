export function applyStage(stage: string | null, root?: HTMLElement): void;
export function watchShowtime(opts?: {
  gw?: string;
  onState?: (s: string | null) => void;
  onError?: (e: any, rs?: number) => void;
  EventSourceImpl?: any;
  fetchImpl?: typeof fetch;
  setIntervalImpl?: any;
  clearIntervalImpl?: any;
  pollMs?: number;
  poll?: boolean;
}): { close(): void };
