/**
 * Error handling utilities for PMOVES UI
 * Provides consistent error logging and user feedback
 */

type ErrorSeverity = 'debug' | 'info' | 'warning' | 'error' | 'critical';

interface ErrorContext {
  component?: string;
  action?: string;
  userId?: string;
  [key: string]: unknown;
}

/**
 * Structured log entry format for Loki/Promtail ingestion.
 * In production, emitted as JSON to stdout where Promtail picks up docker logs.
 */
interface StructuredLogEntry {
  timestamp: string;
  level: ErrorSeverity;
  message: string;
  error?: {
    name: string;
    message: string;
    stack?: string;
  };
  component?: string;
  action?: string;
  context?: Record<string, unknown>;
}

/**
 * Emit structured log entry.
 * Production: JSON to stdout for Promtail/Loki ingestion.
 * Development: Pretty console output for debugging.
 */
function emitStructuredLog(entry: StructuredLogEntry): void {
  if (process.env.NODE_ENV === 'production') {
    // JSON format for Promtail to parse and send to Loki
    console.log(JSON.stringify(entry));
  } else {
    // Pretty output for development
    const levelColors: Record<ErrorSeverity, string> = {
      debug: '\x1b[90m',   // gray
      info: '\x1b[36m',    // cyan
      warning: '\x1b[33m', // yellow
      error: '\x1b[31m',   // red
      critical: '\x1b[35m' // magenta
    };
    const reset = '\x1b[0m';
    const color = levelColors[entry.level] || '';
    console.log(`${color}[${entry.level.toUpperCase()}]${reset} ${entry.message}`, entry);
  }
}

/**
 * Log error for debugging (development only, or with flag)
 * Use for errors that help developers but shouldn't go to production monitoring
 */
export function logForDebugging(
  message: string,
  error?: Error | unknown,
  context?: ErrorContext
): void {
  if (process.env.NODE_ENV === 'development' || process.env.NEXT_PUBLIC_DEBUG_LOGGING === 'true') {
    console.debug(`[DEBUG] ${message}`, { error, context });
  }
}

/**
 * Log error to structured logging system (Loki via Promtail)
 * Use for errors that should be tracked in production
 */
export function logError(
  message: string,
  error: Error | unknown,
  severity: ErrorSeverity = 'error',
  context?: ErrorContext
): void {
  const errorObj = error instanceof Error ? error : new Error(String(error));

  const entry: StructuredLogEntry = {
    timestamp: new Date().toISOString(),
    level: severity,
    message,
    error: {
      name: errorObj.name,
      message: errorObj.message,
      stack: errorObj.stack,
    },
    component: context?.component,
    action: context?.action,
    context: context ? { ...context } : undefined,
  };

  emitStructuredLog(entry);
}

/**
 * Result type for operations that can fail
 * Prefer this over throwing errors for expected failures
 */
export type Result<T, E = string> =
  | { ok: true; data: T }
  | { ok: false; error: E };

/**
 * Create a success result
 */
export function ok<T>(data: T): Result<T, never> {
  return { ok: true, data };
}

/**
 * Create a failure result
 */
export function err<E>(error: E): Result<never, E> {
  return { ok: false, error };
}

/**
 * User-friendly error messages for common HTTP status codes
 */
export function getErrorMessage(status: number): string {
  const messages: Record<number, string> = {
    400: 'Invalid request. Please check your input.',
    401: 'Please sign in to continue.',
    403: "You don't have permission to access this.",
    404: 'The requested resource was not found.',
    408: 'Request timed out. Please try again.',
    429: 'Too many requests. Please wait a moment.',
    500: 'Server error. Please try again later.',
    502: 'Service temporarily unavailable.',
    503: 'Service is under maintenance.',
  };
  return messages[status] || 'An unexpected error occurred.';
}
