/* ═══════════════════════════════════════════════════════════════════════════
   Confirmation Dialog Component
   Reusable modal for confirming destructive or critical actions
   ═══════════════════════════════════════════════════════════════════════════ */

import { useEffect, useRef } from "react";

export interface ConfirmDialogProps {
  /** Whether the dialog is visible */
  isOpen: boolean;
  /** Title displayed at the top of the dialog */
  title: string;
  /** Message explaining the action to be confirmed */
  message: string;
  /** Text for the confirm button (default: "Confirm") */
  confirmLabel?: string;
  /** Text for the cancel button (default: "Cancel") */
  cancelLabel?: string;
  /** Called when user confirms */
  onConfirm: () => void;
  /** Called when user cancels or closes */
  onCancel: () => void;
  /** Visual style for the confirm button */
  variant?: "danger" | "warning" | "info";
}

const VARIANT_CLASSES: Record<
  NonNullable<ConfirmDialogProps["variant"]>,
  string
> = {
  danger: "bg-red-600 hover:bg-red-700 focus:ring-red-500",
  warning: "bg-amber-600 hover:bg-amber-700 focus:ring-amber-500",
  info: "bg-blue-600 hover:bg-blue-700 focus:ring-blue-500",
};

/**
 * Reusable confirmation modal for critical actions.
 * Replaces the native confirm() with a customizable React component.
 *
 * @example
 * // Dangerous action deletion
 * <ConfirmDialog
 *   isOpen={showDialog}
 *   title="Delete Rule"
 *   message="Are you sure you want to delete this rule? This action cannot be undone."
 *   variant="danger"
 *   onConfirm={() => handleDelete()}
 *   onCancel={() => setShowDialog(false)}
 * />
 */
export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  variant = "danger",
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  // Focus management: store previous focus and restore on close
  useEffect(
    () => {
      if (isOpen) {
        // Store the element that had focus before opening
        previousActiveElement.current = document.activeElement as HTMLElement;

        // Move focus to the cancel button (safest default)
        cancelRef.current?.focus();

        return () => {
          // Restore focus when dialog closes
          previousActiveElement.current?.focus();
        };
      }
    },
    [isOpen]
  );

  // Escape key handler for WCAG 2.1 SC 2.1.2 (No Keyboard Trap)
  useEffect(
    () => {
      if (!isOpen) return;

      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          onCancel();
        }
      };

      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    },
    [isOpen, onCancel]
  );

  if (!isOpen) return null;

  const handleConfirm = () => {
    onConfirm();
  };

  return (
    <div
      ref={dialogRef}
      tabIndex={-1}
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-message"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div className="relative z-10 bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3
          id="confirm-dialog-title"
          className="text-lg font-medium text-neutral-900 mb-2"
        >
          {title}
        </h3>
        <p
          id="confirm-dialog-message"
          className="text-sm text-neutral-600 mb-6"
        >
          {message}
        </p>

        <div className="flex justify-end gap-3">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded border border-neutral-300 text-neutral-700 hover:bg-neutral-50 focus:outline-none focus:ring-2 focus:ring-neutral-300 focus:ring-offset-2"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            className={`px-4 py-2 rounded text-white focus:outline-none focus:ring-2 focus:ring-offset-2 ${VARIANT_CLASSES[variant]}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
