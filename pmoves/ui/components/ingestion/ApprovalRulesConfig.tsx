/* ═══════════════════════════════════════════════════════════════════════════
   Approval Rules Configuration Component
   Configure workflow rules for automatic approval/rejection of items
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useState, useCallback } from "react";
import type { IngestionSourceType } from "@/lib/realtimeClient";

// Tailwind JIT static class lookup objects
const MODAL_OVERLAY_CLASSES = "fixed inset-0 bg-black/50 flex items-center justify-center z-50";
const MODAL_CONTENT_CLASSES = "bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col";
const RULE_CARD_CLASSES = "border border-neutral-200 rounded-lg p-4 hover:border-neutral-300 transition";
const BUTTON_PRIMARY_CLASSES = "rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition";
const BUTTON_SECONDARY_CLASSES = "rounded border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50 transition";
const BUTTON_DANGER_CLASSES = "rounded border border-red-600 px-4 py-2 text-sm text-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition";

export type ApprovalRuleAction = 'auto_approve' | 'auto_reject' | 'flag';

export interface ApprovalRuleCondition {
  /** Source type to match (empty = all) */
  sourceType?: IngestionSourceType | 'all';
  /** Channel name must contain this string */
  channelContains?: string;
  /** Title must contain this string */
  titleContains?: string;
  /** Minimum duration in seconds (null = no minimum) */
  minDuration?: number | null;
  /** Maximum duration in seconds (null = no maximum) */
  maxDuration?: number | null;
}

export interface ApprovalRule {
  /** Unique rule identifier */
  id: string;
  /** Human-readable rule name */
  name: string;
  /** Description of what the rule does */
  description?: string;
  /** Conditions for matching items */
  conditions: ApprovalRuleCondition;
  /** Action to take when matched */
  action: ApprovalRuleAction;
  /** Priority for approved items (1-10) */
  priority?: number;
  /** Whether the rule is enabled */
  enabled: boolean;
  /** ISO timestamp of creation */
  createdAt: string;
  /** Number of items matched */
  matchCount?: number;
  /** ISO timestamp of last match */
  lastMatchedAt?: string;
}

interface ApprovalRulesConfigProps {
  /** All configured rules */
  rules: ApprovalRule[];
  /** Callback when a new rule is created */
  onCreateRule: (rule: Omit<ApprovalRule, 'id' | 'createdAt' | 'matchCount' | 'lastMatchedAt'>) => void;
  /** Callback when a rule is updated */
  onUpdateRule: (id: string, rule: Partial<ApprovalRule>) => void;
  /** Callback when a rule is deleted */
  onDeleteRule: (id: string) => void;
  /** Callback to test a rule against pending items */
  onTestRule?: (rule: ApprovalRuleCondition) => Promise<{ matched: number; total: number }>;
  /** Callback to fetch execution log */
  onFetchLog?: () => Promise<Array<{ ruleId: string; ruleName: string; itemId: string; action: string; timestamp: string }>>;
  /** Whether operations are in progress */
  processing?: boolean;
}

const ACTION_BADGES: Record<ApprovalRuleAction, { label: string; classes: string }> = {
  auto_approve: { label: 'Auto-Approve', classes: 'bg-green-100 text-green-800' },
  auto_reject: { label: 'Auto-Reject', classes: 'bg-red-100 text-red-800' },
  flag: { label: 'Flag', classes: 'bg-amber-100 text-amber-800' },
};

const SOURCE_TYPE_LABELS: Record<IngestionSourceType | 'all', string> = {
  all: 'All Sources',
  youtube: 'YouTube',
  pdf: 'PDF',
  url: 'URL',
  upload: 'Upload',
  notebook: 'Notebook',
  discord: 'Discord',
  telegram: 'Telegram',
  rss: 'RSS',
};

/**
 * Approval rules configuration panel.
 * Allows creating, editing, and testing automatic approval/rejection rules.
 */
export function ApprovalRulesConfig({
  rules,
  onCreateRule,
  onUpdateRule,
  onDeleteRule,
  onTestRule,
  onFetchLog,
  processing = false,
}: ApprovalRulesConfigProps) {
  const [showModal, setShowModal] = useState(false);
  const [editingRule, setEditingRule] = useState<ApprovalRule | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [executionLog, setExecutionLog] = useState<Array<{ ruleId: string; ruleName: string; itemId: string; action: string; timestamp: string }>>([]);
  const [testResult, setTestResult] = useState<{ matched: number; total: number } | null>(null);

  // Form state for new/edit rule
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    enabled: true,
    conditions: {
      sourceType: 'all' as IngestionSourceType | 'all',
      channelContains: '',
      titleContains: '',
      minDuration: null as number | null,
      maxDuration: null as number | null,
    } as ApprovalRuleCondition,
    action: 'flag' as ApprovalRuleAction,
    priority: 5,
  });

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      enabled: true,
      conditions: {
        sourceType: 'all',
        channelContains: '',
        titleContains: '',
        minDuration: null,
        maxDuration: null,
      },
      action: 'flag',
      priority: 5,
    });
    setEditingRule(null);
    setTestResult(null);
  };

  const openCreateModal = () => {
    resetForm();
    setShowModal(true);
  };

  const openEditModal = (rule: ApprovalRule) => {
    setEditingRule(rule);
    setFormData({
      name: rule.name,
      description: rule.description ?? '',
      enabled: rule.enabled,
      conditions: rule.conditions,
      action: rule.action,
      priority: rule.priority ?? 5,
    });
    setShowModal(true);
    setTestResult(null);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    resetForm();
  };

  const handleSave = () => {
    if (editingRule) {
      onUpdateRule(editingRule.id, formData);
    } else {
      onCreateRule(formData);
    }
    handleCloseModal();
  };

  const handleToggleEnabled = (id: string, enabled: boolean) => {
    onUpdateRule(id, { enabled });
  };

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this rule?')) {
      onDeleteRule(id);
    }
  };

  const handleTestRule = async () => {
    if (onTestRule) {
      try {
        const result = await onTestRule(formData.conditions);
        setTestResult(result);
      } catch (error) {
        console.error('Failed to test rule:', error);
        setTestResult(null);
        // Consider adding user-facing error state
      }
    }
  };

  const handleFetchLog = async () => {
    if (onFetchLog) {
      try {
        const log = await onFetchLog();
        setExecutionLog(log);
        setShowLog(true);
      } catch (error) {
        console.error('Failed to fetch log:', error);
        // Consider adding user-facing error state
      }
    }
  };

  const updateCondition = <K extends keyof ApprovalRuleCondition>(
    key: K,
    value: ApprovalRuleCondition[K]
  ) => {
    setFormData(prev => ({
      ...prev,
      conditions: {
        ...prev.conditions,
        [key]: value,
      },
    }));
  };

  // Format rule condition summary
  const formatConditionSummary = (conditions: ApprovalRuleCondition): string => {
    const parts: string[] = [];

    if (conditions.sourceType && conditions.sourceType !== 'all') {
      parts.push(SOURCE_TYPE_LABELS[conditions.sourceType]);
    }
    if (conditions.channelContains) {
      parts.push(`channel contains "${conditions.channelContains}"`);
    }
    if (conditions.titleContains) {
      parts.push(`title contains "${conditions.titleContains}"`);
    }
    if (conditions.minDuration !== null && conditions.minDuration !== undefined) {
      parts.push(`duration ≥ ${conditions.minDuration}s`);
    }
    if (conditions.maxDuration !== null && conditions.maxDuration !== undefined) {
      parts.push(`duration ≤ ${conditions.maxDuration}s`);
    }

    return parts.length > 0 ? parts.join(', ') : 'Always match';
  };

  const enabledRules = rules.filter(r => r.enabled);
  const disabledRules = rules.filter(r => !r.enabled);

  return (
    <>
      <div className="rounded border border-neutral-200 bg-white p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-medium">Approval Rules</h3>
            <p className="text-sm text-neutral-500">
              {enabledRules.length} active rule{enabledRules.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {onFetchLog && (
              <button
                onClick={handleFetchLog}
                className={BUTTON_SECONDARY_CLASSES}
                disabled={processing}
                type="button"
              >
                View Log
              </button>
            )}
            <button
              onClick={openCreateModal}
              className={BUTTON_PRIMARY_CLASSES}
              disabled={processing}
              type="button"
            >
              + New Rule
            </button>
          </div>
        </div>

        {/* Rules List */}
        <div className="space-y-3">
          {[...enabledRules, ...disabledRules].map((rule) => (
            <div
              key={rule.id}
              className={`${RULE_CARD_CLASSES} ${!rule.enabled ? 'opacity-60' : ''}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium">{rule.name}</h4>
                    <span className={`text-xs px-2 py-0.5 rounded ${ACTION_BADGES[rule.action].classes}`}>
                      {ACTION_BADGES[rule.action].label}
                    </span>
                    {!rule.enabled && (
                      <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                        Disabled
                      </span>
                    )}
                  </div>
                  {rule.description && (
                    <p className="text-sm text-neutral-600 mb-2">{rule.description}</p>
                  )}
                  <p className="text-xs text-neutral-500">
                    When: {formatConditionSummary(rule.conditions)}
                  </p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-neutral-500">
                    {rule.matchCount !== undefined && (
                      <span>Matched: {rule.matchCount} items</span>
                    )}
                    {rule.lastMatchedAt && (
                      <span>Last: {new Date(rule.lastMatchedAt).toLocaleString()}</span>
                    )}
                    {rule.action === 'auto_approve' && rule.priority !== undefined && (
                      <span>Priority: {rule.priority}</span>
                    )}
                  </div>
                </div>

                {/* Rule Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggleEnabled(rule.id, !rule.enabled)}
                    className="text-xs text-blue-600 hover:text-blue-800"
                    type="button"
                  >
                    {rule.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button
                    onClick={() => openEditModal(rule)}
                    className="text-xs text-blue-600 hover:text-blue-800"
                    type="button"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(rule.id)}
                    className="text-xs text-red-600 hover:text-red-800"
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}

          {rules.length === 0 && (
            <div className="text-center py-8 text-sm text-neutral-500">
              <div className="text-2xl mb-2">📋</div>
              <p>No approval rules configured.</p>
              <p className="text-xs">Click "New Rule" to create one.</p>
            </div>
          )}
        </div>
      </div>

      {/* Rule Edit/Create Modal */}
      {showModal && (
        <div className={MODAL_OVERLAY_CLASSES} onClick={handleCloseModal}>
          <div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-neutral-200">
              <h3 className="text-lg font-medium">
                {editingRule ? 'Edit Rule' : 'New Approval Rule'}
              </h3>
            </div>

            <div className="p-4 overflow-y-auto flex-1 space-y-4">
              {/* Rule Name */}
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Rule Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., Auto-approve trusted channels"
                  className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
                  maxLength={100}
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Description (optional)
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Describe what this rule does..."
                  className="w-full rounded border border-neutral-300 px-3 py-2 text-sm resize-none"
                  rows={2}
                  maxLength={500}
                />
              </div>

              {/* Action Selection */}
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Action
                </label>
                <div className="flex gap-2">
                  {([
                    { value: 'auto_approve' as const, label: 'Auto-Approve', color: 'bg-green-100 text-green-800' },
                    { value: 'auto_reject' as const, label: 'Auto-Reject', color: 'bg-red-100 text-red-800' },
                    { value: 'flag' as const, label: 'Flag for Review', color: 'bg-amber-100 text-amber-800' },
                  ]).map((action) => (
                    <button
                      key={action.value}
                      type="button"
                      onClick={() => setFormData(prev => ({ ...prev, action: action.value }))}
                      className={`px-3 py-2 rounded text-sm border ${
                        formData.action === action.value
                          ? `${action.color} border-current`
                          : 'border-neutral-200 hover:bg-neutral-50'
                      }`}
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Conditions */}
              <div className="border border-neutral-200 rounded p-3 space-y-3">
                <h4 className="text-sm font-medium">Conditions</h4>

                {/* Source Type */}
                <div>
                  <label className="block text-xs text-neutral-600 mb-1">Source Type</label>
                  <select
                    value={formData.conditions.sourceType}
                    onChange={(e) => updateCondition('sourceType', e.target.value as IngestionSourceType | 'all')}
                    className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
                  >
                    {Object.entries(SOURCE_TYPE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>

                {/* Channel Contains */}
                <div>
                  <label className="block text-xs text-neutral-600 mb-1">Channel name contains</label>
                  <input
                    type="text"
                    value={formData.conditions.channelContains ?? ''}
                    onChange={(e) => updateCondition('channelContains', e.target.value || undefined)}
                    placeholder="e.g., TED, PBS, NatGeo"
                    className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
                  />
                </div>

                {/* Title Contains */}
                <div>
                  <label className="block text-xs text-neutral-600 mb-1">Title contains</label>
                  <input
                    type="text"
                    value={formData.conditions.titleContains ?? ''}
                    onChange={(e) => updateCondition('titleContains', e.target.value || undefined)}
                    placeholder="e.g., tutorial, review"
                    className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
                  />
                </div>

                {/* Duration Range */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-neutral-600 mb-1">Min duration (seconds)</label>
                    <input
                      type="number"
                      value={formData.conditions.minDuration ?? ''}
                      onChange={(e) => updateCondition('minDuration', e.target.value ? parseInt(e.target.value) : null)}
                      placeholder="Any"
                      min={0}
                      className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-neutral-600 mb-1">Max duration (seconds)</label>
                    <input
                      type="number"
                      value={formData.conditions.maxDuration ?? ''}
                      onChange={(e) => updateCondition('maxDuration', e.target.value ? parseInt(e.target.value) : null)}
                      placeholder="Any"
                      min={0}
                      className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
                    />
                  </div>
                </div>

                {/* Test Button */}
                {onTestRule && (
                  <button
                    onClick={handleTestRule}
                    className="w-full text-sm text-blue-600 hover:text-blue-800 underline py-2"
                    disabled={processing}
                    type="button"
                  >
                    Test this rule against pending items
                  </button>
                )}

                {/* Test Result */}
                {testResult && (
                  <div className={`text-sm p-2 rounded ${
                    testResult.matched > 0 ? 'bg-blue-50 text-blue-800' : 'bg-gray-50 text-gray-600'
                  }`}>
                    Would match {testResult.matched} of {testResult.total} pending items
                  </div>
                )}
              </div>

              {/* Priority (for auto-approve) */}
              {formData.action === 'auto_approve' && (
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">
                    Priority: {formData.priority}
                  </label>
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={formData.priority}
                    onChange={(e) => setFormData(prev => ({ ...prev, priority: parseInt(e.target.value) }))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-neutral-500">
                    <span>Low</span>
                    <span>High</span>
                  </div>
                </div>
              )}

              {/* Enabled Toggle */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="rule-enabled"
                  checked={formData.enabled}
                  onChange={(e) => setFormData(prev => ({ ...prev, enabled: e.target.checked }))}
                  className="w-4 h-4 text-blue-600 border-neutral-300 rounded focus:ring-blue-500"
                />
                <label htmlFor="rule-enabled" className="text-sm text-neutral-700">
                  Enable this rule
                </label>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="p-4 border-t border-neutral-200 flex justify-end gap-2">
              <button
                onClick={handleCloseModal}
                className={BUTTON_SECONDARY_CLASSES}
                disabled={processing}
                type="button"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className={BUTTON_PRIMARY_CLASSES}
                disabled={processing || !formData.name.trim()}
                type="button"
              >
                {editingRule ? 'Update Rule' : 'Create Rule'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Execution Log Modal */}
      {showLog && (
        <div className={MODAL_OVERLAY_CLASSES} onClick={() => setShowLog(false)}>
          <div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-neutral-200 flex justify-between items-center">
              <h3 className="text-lg font-medium">Rule Execution Log</h3>
              <button
                onClick={() => setShowLog(false)}
                className="text-neutral-500 hover:text-neutral-700"
                type="button"
              >
                ×
              </button>
            </div>

            <div className="p-4 overflow-y-auto flex-1">
              {executionLog.length === 0 ? (
                <p className="text-sm text-neutral-500 text-center py-4">No execution log entries</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-neutral-200">
                      <th className="text-left py-2 font-medium">Time</th>
                      <th className="text-left py-2 font-medium">Rule</th>
                      <th className="text-left py-2 font-medium">Action</th>
                      <th className="text-left py-2 font-medium">Item ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {executionLog.map((entry, index) => (
                      <tr key={index} className="border-b border-neutral-100">
                        <td className="py-2 text-neutral-500">
                          {new Date(entry.timestamp).toLocaleString()}
                        </td>
                        <td className="py-2">{entry.ruleName}</td>
                        <td className="py-2">
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            entry.action === 'approved' ? 'bg-green-100 text-green-800' :
                            entry.action === 'rejected' ? 'bg-red-100 text-red-800' :
                            'bg-amber-100 text-amber-800'
                          }`}>
                            {entry.action}
                          </span>
                        </td>
                        <td className="py-2 text-neutral-500 font-mono text-xs">
                          {entry.itemId.slice(0, 8)}...
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="p-4 border-t border-neutral-200 flex justify-end">
              <button
                onClick={() => setShowLog(false)}
                className={BUTTON_SECONDARY_CLASSES}
                type="button"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
