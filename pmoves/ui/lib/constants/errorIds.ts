/**
 * Error ID constants for log aggregation (Loki/Promtail).
 * Each unique error type gets a stable ID for tracking and alerting.
 *
 * Usage: logError(message, error, 'error', { errorId: ErrorIds.TOKENISM_SIMULATION_FAILED, ... })
 */

export const ErrorIds = {
  // Tokenism Service Errors
  TOKENISM_SIMULATION_FAILED: 'tokenism_simulation_failed',
  TOKENISM_GEOMETRY_LOAD_FAILED: 'tokenism_geometry_load_failed',
  TOKENISM_HEALTH_CHECK_FAILED: 'tokenism_health_check_failed',
  TOKENISM_API_ERROR: 'tokenism_api_error',

  // Network Errors
  NETWORK_TIMEOUT: 'network_timeout',
  NETWORK_CONNECTION_REFUSED: 'network_connection_refused',
  NETWORK_OFFLINE: 'network_offline',

  // Data Validation Errors
  INVALID_SIMULATION_RESULT: 'invalid_simulation_result',
  MISSING_WEEKLY_METRICS: 'missing_weekly_metrics',
  INVALID_METRICS_DATA: 'invalid_metrics_data',

  // UI Errors
  CANVAS_RENDER_FAILED: 'canvas_render_failed',
  VISUALIZATION_FALLBACK: 'visualization_fallback',
} as const;

export type ErrorId = typeof ErrorIds[keyof typeof ErrorIds];
