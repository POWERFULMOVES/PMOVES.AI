export type MetricPayload = Record<string, unknown>;

const formatPayload = (payload: MetricPayload) => ({
  ...payload,
  timestamp: new Date().toISOString(),
});

export const trackUiMetric = (name: string, payload: MetricPayload = {}): void => {
  try {
    console.info(`[metric] ${name}`, formatPayload(payload));
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[metric] failed to emit ${name}`, error);
    }
  }
};

export const trackUiEvent = (name: string, payload: MetricPayload = {}): void => {
  try {
    console.debug(`[event] ${name}`, formatPayload(payload));
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[event] failed to emit ${name}`, error);
    }
  }
};
