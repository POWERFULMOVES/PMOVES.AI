/**
 * Error ID constants for log aggregation (Loki/Promtail).
 * Each unique error type gets a stable ID for tracking and alerting.
 *
 * Usage: logError(message, error, 'error', { errorId: ErrorIds.TOKENISM_SIMULATION_FAILED, ... })
 */

export const ErrorIds = {
  // === TOKENISM SERVICE ERRORS ===
  TOKENISM_SIMULATION_FAILED: 'tokenism_simulation_failed',
  TOKENISM_GEOMETRY_LOAD_FAILED: 'tokenism_geometry_load_failed',
  TOKENISM_HEALTH_CHECK_FAILED: 'tokenism_health_check_failed',
  TOKENISM_API_ERROR: 'tokenism_api_error',

  // === NETWORK ERRORS ===
  NETWORK_TIMEOUT: 'network_timeout',
  NETWORK_CONNECTION_REFUSED: 'network_connection_refused',
  NETWORK_OFFLINE: 'network_offline',

  // === DATA VALIDATION ERRORS ===
  INVALID_SIMULATION_RESULT: 'invalid_simulation_result',
  MISSING_WEEKLY_METRICS: 'missing_weekly_metrics',
  INVALID_METRICS_DATA: 'invalid_metrics_data',

  // === UI ERRORS ===
  CANVAS_RENDER_FAILED: 'canvas_render_failed',
  VISUALIZATION_FALLBACK: 'visualization_fallback',

  // === AUTHENTICATION/AUTHORIZATION ERRORS ===
  JWT_PARSE_FAILED: 'jwt_parse_failed',
  JWT_INVALID_FORMAT: 'jwt_invalid_format',
  JWT_MISSING_HEADER: 'jwt_missing_header',
  JWT_INVALID_SIGNATURE: 'jwt_invalid_signature',
  SUPABASE_AUTH_FAILED: 'supabase_auth_failed',
  SUPABASE_QUERY_FAILED: 'supabase_query_failed',

  // === CHAT ERRORS ===
  CHAT_SEND_FAILED: 'chat_send_failed',
  CHAT_FETCH_FAILED: 'chat_fetch_failed',

  // === NOTEBOOK ERRORS ===
  NOTEBOOK_RUNTIME_FETCH_FAILED: 'notebook_runtime_fetch_failed',
  NOTEBOOK_SOURCES_FETCH_FAILED: 'notebook_sources_fetch_failed',
  NOTEBOOK_SYNC_FAILED: 'notebook_sync_failed',
  NOTEBOOK_SYNC_TRIGGER_FAILED: 'notebook_sync_trigger_failed',

  // === JELLYFIN ERRORS ===
  JELLYFIN_SEARCH_FAILED: 'jellyfin_search_failed',
  JELLYFIN_SYNC_STATUS_FAILED: 'jellyfin_sync_status_failed',
  JELLYFIN_LINK_FAILED: 'jellyfin_link_failed',
  JELLYFIN_PLAYBACK_URL_FAILED: 'jellyfin_playback_url_failed',
  JELLYFIN_SYNC_TRIGGER_FAILED: 'jellyfin_sync_trigger_failed',
  JELLYFIN_BACKFILL_FAILED: 'jellyfin_backfill_failed',

  // === RESEARCH ERRORS ===
  RESEARCH_INITIATE_FAILED: 'research_initiate_failed',
  RESEARCH_TASK_FETCH_FAILED: 'research_task_fetch_failed',
  RESEARCH_TASK_LIST_FAILED: 'research_task_list_failed',
  RESEARCH_RESULTS_FETCH_FAILED: 'research_results_fetch_failed',
  RESEARCH_CANCEL_FAILED: 'research_cancel_failed',
  RESEARCH_HEALTH_CHECK_FAILED: 'research_health_check_failed',
  RESEARCH_PUBLISH_FAILED: 'research_publish_failed',

  // === HI-RAG ERRORS ===
  HIRAG_QUERY_FAILED: 'hirag_query_failed',
  HIRAG_HEALTH_CHECK_FAILED: 'hirag_health_check_failed',
  HIRAG_EXPORT_FAILED: 'hirag_export_failed',

  // === ERROR BOUNDARY ERRORS ===
  ROOT_ERROR_BOUNDARY: 'root_error_boundary',
  DASHBOARD_ERROR_BOUNDARY: 'dashboard_error_boundary',

  // === TENSORZERO ERRORS ===
  TENSORZERO_REQUEST_FAILED: 'tensorzero_request_failed',
  TENSORZERO_TIMEOUT: 'tensorzero_timeout',
} as const;

export type ErrorId = typeof ErrorIds[keyof typeof ErrorIds];

/**
 * Runtime validator for error IDs from external sources.
 * Use this to validate strings received from APIs, user input, or config files.
 *
 * @example
 * if (isValidErrorId(externalErrorId)) {
 *   logError(..., { errorId: externalErrorId });
 * }
 */
export function isValidErrorId(value: string): value is ErrorId {
  return Object.values(ErrorIds).includes(value as any);
}
