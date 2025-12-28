/* ═══════════════════════════════════════════════════════════════════════════
   Alert Banner Component
   Reusable alert/notification banner with variants and dismiss functionality
   ═══════════════════════════════════════════════════════════════════════════ */

import type { HTMLAttributes } from "react";

export interface AlertBannerProps extends HTMLAttributes<HTMLDivElement> {
  /** The message to display */
  message: string;
  /** Visual style variant */
  variant?: "error" | "warning" | "success" | "info";
  /** Optional dismiss callback */
  onDismiss?: () => void;
}

const VARIANT_CLASSES: Record<NonNullable<AlertBannerProps["variant"]>, string> = {
  error: "bg-red-50 border-red-300 text-red-800",
  warning: "bg-amber-50 border-amber-300 text-amber-800",
  success: "bg-green-50 border-green-300 text-green-800",
  info: "bg-blue-50 border-blue-300 text-blue-800",
};

/**
 * Reusable alert banner component for displaying notifications and errors.
 * Supports multiple visual variants and an optional dismiss button.
 *
 * @example
 * // Error with dismiss
 * <AlertBanner message="Something went wrong" variant="error" onDismiss={() => setError(null)} />
 *
 * @example
 * // Success without dismiss
 * <AlertBanner message="Operation completed" variant="success" />
 */
export function AlertBanner({
  message,
  variant = "error",
  onDismiss,
  className,
  ...props
}: AlertBannerProps) {
  const baseClasses = "rounded border p-4 text-sm flex items-center justify-between";
  const variantClasses = VARIANT_CLASSES[variant];
  // Use assertive for errors (interrupts immediately), polite for other variants
  const ariaLive = variant === "error" ? "assertive" : "polite";

  return (
    <div
      className={`${baseClasses} ${variantClasses} ${className || ""}`}
      role="alert"
      aria-live={ariaLive}
      {...props}
    >
      <span>{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="ml-4 hover:opacity-70 transition-opacity"
          aria-label="Dismiss notification"
        >
          ×
        </button>
      )}
    </div>
  );
}
