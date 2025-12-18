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
 * Log error for debugging (development only, or with flag)
 * Use for errors that help developers but shouldn't go to Sentry
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
 * Log error to error reporting service (Sentry when configured)
 * Use for errors that should be tracked in production
 */
export function logError(
  message: string,
  error: Error | unknown,
  severity: ErrorSeverity = 'error',
  context?: ErrorContext
): void {
  const errorObj = error instanceof Error ? error : new Error(String(error));

  // Always log to console in development
  if (process.env.NODE_ENV === 'development') {
    console.error(`[${severity.toUpperCase()}] ${message}`, { error: errorObj, context });
  }

  // TODO: Integrate with Sentry when configured
  // Sentry.captureException(errorObj, {
  //   level: severity,
  //   tags: { component: context?.component, action: context?.action },
  //   extra: context,
  // });
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
