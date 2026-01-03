/* ═══════════════════════════════════════════════════════════════════════════
   Approval Rules Configuration Component Tests
   Tests workflow rules for automatic approval/rejection of items
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent } from '@testing-library/react';
import { ApprovalRulesConfig, type ApprovalRule } from './ApprovalRulesConfig';
import type { IngestionSourceType } from '@/lib/realtimeClient';

const mockRules: ApprovalRule[] = [
  {
    id: 'rule1',
    name: 'Auto-approve TED talks',
    description: 'Automatically approve videos from TED channel',
    conditions: {
      sourceType: 'youtube',
      channelContains: 'TED',
    },
    action: 'auto_approve',
    priority: 8,
    enabled: true,
    createdAt: '2025-01-15T10:00:00Z',
    matchCount: 42,
    lastMatchedAt: '2025-01-15T12:30:00Z',
  },
  {
    id: 'rule2',
    name: 'Block spam',
    description: 'Auto-reject known spam channels',
    conditions: {
      sourceType: 'youtube',
      channelContains: 'spam',
    },
    action: 'auto_reject',
    enabled: true,
    createdAt: '2025-01-14T10:00:00Z',
    matchCount: 15,
  },
  {
    id: 'rule3',
    name: 'Flag long videos',
    conditions: {
      minDuration: 3600, // 1 hour
    },
    action: 'flag',
    enabled: false,
    createdAt: '2025-01-13T10:00:00Z',
  },
];

describe('ApprovalRulesConfig', () => {
  const mockOnCreateRule = jest.fn();
  const mockOnUpdateRule = jest.fn();
  const mockOnDeleteRule = jest.fn();
  const mockOnTestRule = jest.fn().mockResolvedValue({ matched: 5, total: 10 });
  const mockOnFetchLog = jest.fn().mockResolvedValue([]);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rules list display', () => {
    it('should list all rules with enable/disable toggle', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      expect(screen.getByText('Auto-approve TED talks')).toBeInTheDocument();
      expect(screen.getByText('Block spam')).toBeInTheDocument();
      expect(screen.getByText('Flag long videos')).toBeInTheDocument();
    });

    it('should show active rule count', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      expect(screen.getByText('2 active rules')).toBeInTheDocument();
    });

    it('should show action badges', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      expect(screen.getByText('Auto-Approve')).toBeInTheDocument();
      expect(screen.getByText('Auto-Reject')).toBeInTheDocument();
      expect(screen.getByText('Flag')).toBeInTheDocument();
    });

    it('should show disabled badge for disabled rules', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });

    it('should show match count and last matched', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      expect(screen.getByText('Matched: 42 items')).toBeInTheDocument();
      expect(screen.getByText(/Last:/)).toBeInTheDocument();
    });
  });

  describe('Enable/disable toggle', () => {
    it('should toggle rule enabled state', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      const disableButton = screen.getAllByText('Disable')[0];
      fireEvent.click(disableButton);

      expect(mockOnUpdateRule).toHaveBeenCalledWith('rule1', { enabled: false });
    });

    it('should enable disabled rule', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      const enableButton = screen.getByText('Enable');
      fireEvent.click(enableButton);

      expect(mockOnUpdateRule).toHaveBeenCalledWith('rule3', { enabled: true });
    });
  });

  describe('Create rule modal', () => {
    it('should open create rule modal', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      const newRuleButton = screen.getByText('+ New Rule');
      fireEvent.click(newRuleButton);

      expect(screen.getByText('New Approval Rule')).toBeInTheDocument();
    });

    it('should validate rule name is required', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));

      // Try to save without name
      const saveButton = screen.getByText('Create Rule');
      expect(saveButton).toBeDisabled();
    });

    it('should create rule with conditions', () => {
      const { container } = render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));

      // Fill in name
      const nameInput = screen.getByPlaceholderText('e.g., Auto-approve trusted channels');
      fireEvent.change(nameInput, { target: { value: 'New test rule' } });

      // Select action - click the button for auto_approve (in the action selection area)
      // Use getByRole for robust button selection
      fireEvent.click(screen.getByRole('button', { name: /auto-approve/i }));

      // Set conditions - use getByLabelText for robust form element selection
      const sourceSelect = screen.getByLabelText('Source Type') as HTMLSelectElement;
      fireEvent.change(sourceSelect, { target: { value: 'youtube' } });

      const channelInput = screen.getByPlaceholderText('e.g., TED, PBS, NatGeo');
      fireEvent.change(channelInput, { target: { value: 'TestChannel' } });

      // Save
      fireEvent.click(screen.getByText('Create Rule'));

      expect(mockOnCreateRule).toHaveBeenCalledWith({
        name: 'New test rule',
        description: '',
        enabled: true,
        conditions: {
          sourceType: 'youtube',
          channelContains: 'TestChannel',
          titleContains: '',
          minDuration: null,
          maxDuration: null,
        },
        action: 'auto_approve',
        priority: 5,
      });
    });
  });

  describe('Edit rule modal', () => {
    it('should open edit rule modal with existing data', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      const editButtons = screen.getAllByText('Edit');
      fireEvent.click(editButtons[0]);

      expect(screen.getByText('Edit Rule')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Auto-approve TED talks')).toBeInTheDocument();
    });

    it('should update existing rule', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      // Open edit modal
      const editButtons = screen.getAllByText('Edit');
      fireEvent.click(editButtons[0]);

      // Change name
      const nameInput = screen.getByDisplayValue('Auto-approve TED talks');
      fireEvent.change(nameInput, { target: { value: 'Updated rule name' } });

      // Save
      fireEvent.click(screen.getByText('Update Rule'));

      expect(mockOnUpdateRule).toHaveBeenCalledWith('rule1', expect.objectContaining({
        name: 'Updated rule name',
      }));
    });
  });

  describe('Delete rule', () => {
    it('should delete rule after confirmation', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      // Click the first delete button in the rules list
      const deleteButtons = screen.getAllByText('Delete');
      fireEvent.click(deleteButtons[0]);

      // ConfirmDialog should be visible
      expect(screen.getByText('Delete Rule')).toBeInTheDocument();

      // Click confirm button - get the button inside the dialog (after the title)
      const dialogTitle = screen.getByText('Delete Rule');
      const dialogParent = dialogTitle.closest('div[role="dialog"]');
      const confirmButton = dialogParent?.querySelector('button:last-child');
      if (confirmButton) fireEvent.click(confirmButton);

      expect(mockOnDeleteRule).toHaveBeenCalledWith('rule1');
    });

    it('should not delete rule when confirmation cancelled', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      // Click the first delete button in the rules list
      const deleteButtons = screen.getAllByText('Delete');
      fireEvent.click(deleteButtons[0]);

      // ConfirmDialog should be visible
      expect(screen.getByText('Delete Rule')).toBeInTheDocument();

      // Click cancel button - get the first button inside the dialog
      const dialogTitle = screen.getByText('Delete Rule');
      const dialogParent = dialogTitle.closest('div[role="dialog"]');
      const cancelButton = dialogParent?.querySelector('button:first-child');
      if (cancelButton) fireEvent.click(cancelButton);

      expect(mockOnDeleteRule).not.toHaveBeenCalled();
    });
  });

  describe('Condition summary formatting', () => {
    it('should format condition summary correctly', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      // Rule 1: sourceType + channelContains
      expect(screen.getByText(/When: YouTube, channel contains "TED"/)).toBeInTheDocument();

      // Rule 2: sourceType + channelContains
      expect(screen.getByText(/When: YouTube, channel contains "spam"/)).toBeInTheDocument();

      // Rule 3: minDuration
      expect(screen.getByText(/When: duration ≥ 3600s/)).toBeInTheDocument();
    });

    it('should show "Always match" for empty conditions', () => {
      const emptyRule: ApprovalRule = {
        id: 'rule4',
        name: 'Match all',
        conditions: {},
        action: 'flag',
        enabled: true,
        createdAt: '2025-01-15T10:00:00Z',
      };

      render(
        <ApprovalRulesConfig
          rules={[emptyRule]}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      expect(screen.getByText('When: Always match')).toBeInTheDocument();
    });
  });

  describe('Rule conditions', () => {
    it('should match by source type', () => {
      const { container } = render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));

      // Query by select element (only one in the modal)
      const sourceSelect = container.querySelector('select') as HTMLSelectElement;
      fireEvent.change(sourceSelect, { target: { value: 'pdf' } });

      expect(sourceSelect).toHaveValue('pdf');
    });

    it('should match by channel contains', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));

      const channelInput = screen.getByPlaceholderText('e.g., TED, PBS, NatGeo');
      fireEvent.change(channelInput, { target: { value: 'TestChannel' } });

      expect(channelInput).toHaveValue('TestChannel');
    });

    it('should match by title contains', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));

      const titleInput = screen.getByPlaceholderText('e.g., tutorial, review');
      fireEvent.change(titleInput, { target: { value: 'tutorial' } });

      expect(titleInput).toHaveValue('tutorial');
    });

    it('should match by duration range', () => {
      const { container } = render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));

      // Both duration inputs have placeholder "Any", so get all number inputs
      const numberInputs = container.querySelectorAll('input[type="number"]');
      const minDurationInput = numberInputs[0]; // First is Min duration
      fireEvent.change(minDurationInput, { target: { value: '60' } });

      expect(minDurationInput).toHaveValue(60);
    });
  });

  describe('Priority for auto-approve', () => {
    it('should set priority for auto-approve rules', () => {
      const { container } = render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      // Open create modal
      fireEvent.click(screen.getByText('+ New Rule'));

      // Select auto_approve action - find button with exact text match
      const actionButtons = container.querySelectorAll('button');
      for (const btn of Array.from(actionButtons)) {
        if (btn.textContent === 'Auto-Approve') {
          fireEvent.click(btn);
          break;
        }
      }

      // Priority slider should be visible - the label includes "Priority: {value}"
      // Use container to avoid multiple element errors
      expect(container.textContent).toContain('Priority:');

      // Find the range input for priority
      const prioritySlider = container.querySelector('input[type="range"]') as HTMLInputElement;
      fireEvent.change(prioritySlider, { target: { value: '8' } });

      // "Priority: 8" appears in both the label and display span - use getAllByText
      expect(screen.getAllByText('Priority: 8')).toHaveLength(2);
    });

    it('should not show priority for non-auto-approve actions', () => {
      const { container } = render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));

      // Select flag action (default)
      expect(screen.getByText('Flag for Review')).toBeInTheDocument();

      // Priority slider should not be visible - no range input when action is not auto_approve
      expect(container.querySelector('input[type="range"]')).not.toBeInTheDocument();
    });
  });

  describe('Test rule', () => {
    it('should test rule against pending items', async () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
          onTestRule={mockOnTestRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));

      const testButton = await screen.findByText('Test this rule against pending items');
      fireEvent.click(testButton);

      expect(mockOnTestRule).toHaveBeenCalled();
    });

    it('should show test result', async () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
          onTestRule={mockOnTestRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));

      const testButton = await screen.findByText('Test this rule against pending items');
      fireEvent.click(testButton);

      expect(await screen.findByText('Would match 5 of 10 pending items')).toBeInTheDocument();
    });
  });

  describe('Execution log modal', () => {
    it('should show execution log modal', async () => {
      const mockLog = [
        {
          ruleId: 'rule1',
          ruleName: 'Auto-approve TED talks',
          itemId: 'item123',
          action: 'approved',
          timestamp: '2025-01-15T10:00:00Z',
        },
      ];

      mockOnFetchLog.mockResolvedValueOnce(mockLog);

      const { container } = render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
          onFetchLog={mockOnFetchLog}
        />
      );

      fireEvent.click(screen.getByText('View Log'));

      // Wait for the async modal content to load
      expect(await screen.findByText('Rule Execution Log')).toBeInTheDocument();

      // The rule name appears in multiple places (modal header and table)
      // Use container to check for presence anywhere
      expect(container.textContent).toContain('Auto-approve TED talks');
      expect(container.textContent).toContain('approved');
    });

    it('should show empty log message', async () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
          onFetchLog={mockOnFetchLog}
        />
      );

      fireEvent.click(screen.getByText('View Log'));

      expect(await screen.findByText('No execution log entries')).toBeInTheDocument();
    });
  });

  describe('Empty state', () => {
    it('should show message when no rules configured', () => {
      render(
        <ApprovalRulesConfig
          rules={[]}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      expect(screen.getByText('No approval rules configured.')).toBeInTheDocument();
      expect(screen.getByText('Click "New Rule" to create one.')).toBeInTheDocument();
      expect(screen.getByText('📋')).toBeInTheDocument();
    });
  });

  describe('Processing state', () => {
    it('should disable buttons when processing', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
          processing={true}
        />
      );

      expect(screen.getByText('+ New Rule')).toBeDisabled();
    });
  });

  describe('Modal close behavior', () => {
    it('should close modal when clicking overlay', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));
      expect(screen.getByText('New Approval Rule')).toBeInTheDocument();

      // Click overlay (the modal overlay div)
      const overlay = screen.getByText('New Approval Rule').closest('.fixed')!;
      fireEvent.click(overlay);

      expect(screen.queryByText('New Approval Rule')).not.toBeInTheDocument();
    });

    it('should close modal when cancel clicked', () => {
      render(
        <ApprovalRulesConfig
          rules={mockRules}
          onCreateRule={mockOnCreateRule}
          onUpdateRule={mockOnUpdateRule}
          onDeleteRule={mockOnDeleteRule}
        />
      );

      fireEvent.click(screen.getByText('+ New Rule'));
      fireEvent.click(screen.getByText('Cancel'));

      expect(screen.queryByText('New Approval Rule')).not.toBeInTheDocument();
    });
  });
});
