/* ═══════════════════════════════════════════════════════════════════════════
   Bulk Approval Actions Component
   Provides bulk selection and actions for ingestion queue items
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";
import type { IngestionQueueItem, IngestionStatus, IngestionSourceType } from "@/lib/realtimeClient";

// Tailwind JIT static class lookup objects
const BUTTON_PRIMARY_CLASSES = "rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition";
const BUTTON_SECONDARY_CLASSES = "rounded border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed transition";
const BUTTON_DANGER_CLASSES = "rounded border border-red-600 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition";
const CHECKBOX_CLASSES = "w-4 h-4 text-green-600 border-neutral-300 rounded focus:ring-green-500";

export interface BulkActionOptions {
  /** Priority to set when bulk approving */
  priority?: number;
  /** Reason for bulk rejection */
  rejectionReason?: string;
}

interface BulkApprovalActionsProps {
  /** All items currently displayed */
  items: IngestionQueueItem[];
  /** IDs of currently selected items */
  selectedIds: Set<string>;
  /** Callback when selection changes */
  onSelectionChange: (ids: Set<string>) => void;
  /** Callback to approve selected items */
  onApprove: (ids: string[], options?: BulkActionOptions) => Promise<void>;
  /** Callback to reject selected items */
  onReject: (ids: string[], reason?: string) => Promise<void>;
  /** Callback to export selected items to CSV */
  onExport?: (ids: string[]) => void;
  /** Whether operations are in progress */
  processing?: boolean;
  /** Current status filter for "select all visible" behavior */
  statusFilter?: IngestionStatus | 'all';
  /** Current source type filter */
  sourceFilter?: IngestionSourceType | 'all';
}

/**
 * Bulk actions bar with selection controls and action buttons.
 * Shows only when items are selected.
 */
export function BulkApprovalActions({
  items,
  selectedIds,
  onSelectionChange,
  onApprove,
  onReject,
  onExport,
  processing = false,
  statusFilter = 'all',
  sourceFilter = 'all',
}: BulkApprovalActionsProps) {
  const [showOptions, setShowOptions] = useState<boolean | 'reject'>(false);
  const [priority, setPriority] = useState(5);
  const [rejectionReason, setRejectionReason] = useState('');

  const selectedItems = items.filter(item => selectedIds.has(item.id));
  const pendingSelected = selectedItems.filter(item => item.status === 'pending');

  // Selection handlers
  const handleSelectAll = () => {
    const allIds = new Set(items.map(item => item.id));
    onSelectionChange(allIds);
  };

  const handleSelectVisible = () => {
    // Only select items that match current filters
    const visibleIds = new Set(items.map(item => item.id));
    onSelectionChange(visibleIds);
  };

  const handleSelectPending = () => {
    const pendingIds = new Set(items.filter(item => item.status === 'pending').map(item => item.id));
    onSelectionChange(pendingIds);
  };

  const handleDeselectAll = () => {
    onSelectionChange(new Set());
  };

  const handleToggleItem = (id: string) => {
    const newSelection = new Set(selectedIds);
    if (newSelection.has(id)) {
      newSelection.delete(id);
    } else {
      newSelection.add(id);
    }
    onSelectionChange(newSelection);
  };

  // Action handlers
  const handleBulkApprove = async () => {
    const idsToApprove = pendingSelected.map(item => item.id);
    if (idsToApprove.length === 0) return;

    await onApprove(idsToApprove, { priority });
    onSelectionChange(new Set()); // Clear selection after action
    setShowOptions(false);
  };

  const handleBulkReject = async () => {
    const idsToReject = selectedItems.map(item => item.id);
    if (idsToReject.length === 0) return;

    await onReject(idsToReject, rejectionReason || 'Bulk rejected');
    onSelectionChange(new Set()); // Clear selection after action
    setShowOptions(false);
    setRejectionReason('');
  };

  const handleCloseRejectModal = () => {
    setShowOptions(false);
    setRejectionReason('');
  };

  const handleExport = () => {
    if (onExport) {
      const ids = Array.from(selectedIds);
      onExport(ids);
    }
  };

  // Don't render if no items selected
  if (selectedIds.size === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border-2 border-blue-500 bg-blue-50 p-4 mb-4">
      <div className="flex items-center justify-between flex-wrap gap-4">
        {/* Selection Summary */}
        <div className="flex items-center gap-4">
          <div className="text-sm font-medium text-blue-900">
            {selectedIds.size} item{selectedIds.size !== 1 ? 's' : ''} selected
            {pendingSelected.length > 0 && pendingSelected.length < selectedIds.size && (
              <span className="text-blue-700 font-normal">
                ({pendingSelected.length} can be approved)
              </span>
            )}
          </div>

          {/* Selection Controls */}
          <div className="flex items-center gap-2 text-xs">
            <button
              onClick={handleSelectVisible}
              className="text-blue-700 hover:text-blue-900 underline"
              type="button"
            >
              Select All Visible
            </button>
            <button
              onClick={handleSelectPending}
              className="text-blue-700 hover:text-blue-900 underline"
              type="button"
            >
              Select Pending
            </button>
            <button
              onClick={handleDeselectAll}
              className="text-red-600 hover:text-red-800 underline"
              type="button"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 relative">
          {pendingSelected.length > 0 && (
            <>
              <button
                onClick={() => setShowOptions(showOptions === true ? false : true)}
                className={BUTTON_PRIMARY_CLASSES}
                disabled={processing}
                type="button"
              >
                {processing ? 'Processing...' : `Approve (${pendingSelected.length})`}
              </button>

              {/* Expandable Options Panel */}
              {showOptions === true && (
                <div className="absolute top-full mt-2 right-0 z-10 rounded-lg border border-neutral-200 bg-white shadow-lg p-4 w-64">
                  <h4 className="text-sm font-medium mb-3">Approval Options</h4>

                  {/* Priority Setting */}
                  <div className="mb-4">
                    <label className="block text-xs text-neutral-600 mb-1">
                      Priority: {priority}
                    </label>
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={priority}
                      onChange={(e) => setPriority(parseInt(e.target.value))}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-neutral-500">
                      <span>Low</span>
                      <span>High</span>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={handleBulkApprove}
                      className="flex-1 rounded bg-green-600 px-3 py-2 text-sm text-white hover:bg-green-700 disabled:opacity-50"
                      disabled={processing}
                      type="button"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => setShowOptions(false)}
                      className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm hover:bg-neutral-50"
                      type="button"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          <button
            onClick={() => setShowOptions(showOptions === 'reject' ? false : 'reject')}
            className={BUTTON_DANGER_CLASSES}
            disabled={processing || selectedIds.size === 0}
            type="button"
          >
            Reject ({selectedIds.size})
          </button>

          {/* Rejection Options Panel */}
          {showOptions === 'reject' && (
            <div className="absolute top-full mt-2 right-0 z-10 rounded-lg border border-neutral-200 bg-white shadow-lg p-4 w-80">
              <h4 className="text-sm font-medium mb-3">Reject Items</h4>

              {/* Reason Input */}
              <div className="mb-4">
                <label className="block text-xs text-neutral-600 mb-1">
                  Rejection Reason (optional)
                </label>
                <textarea
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g., Duplicate content, Low quality..."
                  className="w-full rounded border border-neutral-300 px-3 py-2 text-sm resize-none"
                  rows={3}
                  maxLength={500}
                />
                <div className="text-xs text-neutral-500 mt-1 text-right">
                  {rejectionReason.length} / 500
                </div>
              </div>

              {/* Quick Reasons */}
              <div className="mb-4">
                <label className="block text-xs text-neutral-600 mb-1">Quick reasons:</label>
                <div className="flex flex-wrap gap-1">
                  {['Duplicate', 'Low quality', 'Irrelevant', 'NSFW', 'Copyright'].map((reason) => (
                    <button
                      key={reason}
                      onClick={() => setRejectionReason(reason)}
                      className={`text-xs px-2 py-1 rounded border ${
                        rejectionReason === reason
                          ? 'bg-red-100 border-red-300 text-red-800'
                          : 'border-neutral-200 hover:bg-neutral-50'
                      }`}
                      type="button"
                    >
                      {reason}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handleBulkReject}
                  className="flex-1 rounded bg-red-600 px-3 py-2 text-sm text-white hover:bg-red-700 disabled:opacity-50"
                  disabled={processing}
                  type="button"
                >
                  Reject
                </button>
                <button
                  onClick={() => {
                    setShowOptions(false);
                    setRejectionReason('');
                  }}
                  className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm hover:bg-neutral-50"
                  type="button"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {onExport && (
            <button
              onClick={handleExport}
              className={BUTTON_SECONDARY_CLASSES}
              disabled={processing}
              type="button"
            >
              Export CSV
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

interface BulkSelectionCheckboxProps {
  /** Whether this item is selected */
  checked: boolean;
  /** Whether item can be selected (e.g., is pending) */
  selectable?: boolean;
  /** Toggle callback */
  onToggle: () => void;
}

/**
 * Individual checkbox for row-level selection in the queue list.
 */
export function BulkSelectionCheckbox({
  checked,
  selectable = true,
  onToggle,
}: BulkSelectionCheckboxProps) {
  return (
    <input
      type="checkbox"
      checked={checked}
      onChange={onToggle}
      disabled={!selectable}
      className={CHECKBOX_CLASSES}
      aria-label={checked ? "Deselect item" : "Select item"}
    />
  );
}
