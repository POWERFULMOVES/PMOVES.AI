/* ═══════════════════════════════════════════════════════════════════════════
   Time Utilities
   Shared time formatting and manipulation utilities
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Formats a date string as a relative time description (e.g., "5m ago", "2h ago").
 * Handles null/undefined dates and provides locale date formatting for older dates.
 *
 * @param dateStr - ISO date string or null/undefined
 * @returns Relative time string or "Never" for null dates
 */
export function formatTimeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Never';

  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  // For dates older than a week, show the actual date
  return date.toLocaleDateString();
}

/**
 * Formats a duration in milliseconds as a human-readable string.
 *
 * @param ms - Duration in milliseconds
 * @returns Formatted duration (e.g., "2m 5s", "1h 30m")
 */
export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (hours < 24) {
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
  }

  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`;
}
