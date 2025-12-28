/* ═══════════════════════════════════════════════════════════════════════════
   Bulk Approval Actions Component Tests
   Tests bulk selection and actions for ingestion queue items
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { BulkApprovalActions, BulkSelectionCheckbox } from './BulkApprovalActions';
import type { IngestionQueueItem } from '@/lib/realtimeClient';

const mockItems: IngestionQueueItem[] = [
  {
    id: '1',
    owner_id: null,
    source_type: 'youtube',
    source_url: 'https://youtube.com/watch?v=abc123',
    source_id: 'abc123',
    title: 'Test Video 1',
    description: null,
    thumbnail_url: null,
    duration_seconds: null,
    source_meta: {},
    status: 'pending',
    priority: 5,
    approved_by: null,
    approved_at: null,
    rejection_reason: null,
    created_at: '2025-01-15T10:00:00Z',
    updated_at: '2025-01-15T10:00:00Z',
  },
  {
    id: '2',
    owner_id: null,
    source_type: 'youtube',
    source_url: 'https://youtube.com/watch?v=def456',
    source_id: 'def456',
    title: 'Test Video 2',
    description: null,
    thumbnail_url: null,
    duration_seconds: null,
    source_meta: {},
    status: 'pending',
    priority: 5,
    approved_by: null,
    approved_at: null,
    rejection_reason: null,
    created_at: '2025-01-15T09:30:00Z',
    updated_at: '2025-01-15T09:30:00Z',
  },
  {
    id: '3',
    owner_id: null,
    source_type: 'pdf',
    source_url: 'https://example.com/paper.pdf',
    source_id: null,
    title: 'Test PDF',
    description: null,
    thumbnail_url: null,
    duration_seconds: null,
    source_meta: {},
    status: 'approved',
    priority: 5,
    approved_by: null,
    approved_at: null,
    rejection_reason: null,
    created_at: '2025-01-14T14:00:00Z',
    updated_at: '2025-01-14T14:00:00Z',
  },
  {
    id: '4',
    owner_id: null,
    source_type: 'youtube',
    source_url: 'https://youtube.com/watch?v=ghi789',
    source_id: 'ghi789',
    title: 'Test Video 3',
    description: null,
    thumbnail_url: null,
    duration_seconds: null,
    source_meta: {},
    status: 'rejected',
    priority: 5,
    approved_by: null,
    approved_at: null,
    rejection_reason: null,
    created_at: '2025-01-14T10:00:00Z',
    updated_at: '2025-01-14T10:00:00Z',
  },
  {
    id: '5',
    owner_id: null,
    source_type: 'youtube',
    source_url: 'https://youtube.com/watch?v=jkl012',
    source_id: 'jkl012',
    title: 'Test Video 4',
    description: null,
    thumbnail_url: null,
    duration_seconds: null,
    source_meta: {},
    status: 'processing',
    priority: 5,
    approved_by: null,
    approved_at: null,
    rejection_reason: null,
    created_at: '2025-01-14T08:00:00Z',
    updated_at: '2025-01-14T08:00:00Z',
  },
];

describe('BulkApprovalActions', () => {
  const mockOnSelectionChange = jest.fn();
  const mockOnApprove = jest.fn().mockResolvedValue(undefined);
  const mockOnReject = jest.fn().mockResolvedValue(undefined);
  const mockOnExport = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Visibility', () => {
    it('should hide when no items selected', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set()}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      expect(screen.queryByText(/items selected/)).not.toBeInTheDocument();
    });

    it('should show when items are selected', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1', '2'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      expect(screen.getByText('2 items selected')).toBeInTheDocument();
    });
  });

  describe('Selection summary', () => {
    it('should show selected count', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1', '2', '3'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      expect(screen.getByText('3 items selected')).toBeInTheDocument();
    });

    it('should show singular "item" when one selected', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      expect(screen.getByText('1 item selected')).toBeInTheDocument();
    });

    it('should show pending count when some selected are pending', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1', '3'])} // 1 is pending, 3 is approved
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      expect(screen.getByText('(1 can be approved)')).toBeInTheDocument();
    });
  });

  describe('Selection controls', () => {
    it('should select all visible items', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Select All Visible'));

      const expectedIds = new Set(mockItems.map(item => item.id));
      expect(mockOnSelectionChange).toHaveBeenCalledWith(expectedIds);
    });

    it('should select only pending items', () => {
      // Component only renders when at least one item is selected
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['3'])} // Start with one non-pending item selected
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Select Pending'));

      const pendingIds = new Set(['1', '2']); // Only pending items
      expect(mockOnSelectionChange).toHaveBeenCalledWith(pendingIds);
    });

    it('should clear selection', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1', '2', '3'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Clear'));

      expect(mockOnSelectionChange).toHaveBeenCalledWith(new Set());
    });
  });

  describe('Bulk approve', () => {
    it('should call onApprove with selected IDs and priority', async () => {
      const { container } = render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1', '2'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      // Click approve button to expand options
      fireEvent.click(screen.getByText(/Approve \(/));

      // Change priority - use querySelector since label has no htmlFor
      const prioritySlider = container.querySelector('input[type="range"]') as HTMLInputElement;
      fireEvent.change(prioritySlider, { target: { value: '8' } });

      // Click approve
      fireEvent.click(screen.getByText('Approve'));

      expect(mockOnApprove).toHaveBeenCalledWith(['1', '2'], { priority: 8 });
    });

    it('should use default priority of 5', async () => {
      const { container } = render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      // Click approve button to expand options first
      fireEvent.click(screen.getByText(/Approve \(1\)/));

      // Then click approve in the panel
      fireEvent.click(screen.getByText('Approve'));

      expect(mockOnApprove).toHaveBeenCalledWith(['1'], { priority: 5 });
    });

    it('should clear selection after approve', async () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      // Click approve button to expand options
      fireEvent.click(screen.getByText(/Approve \(1\)/));

      // Click approve in panel - wrap in act for async operation
      await act(async () => {
        fireEvent.click(screen.getByText('Approve'));
        await Promise.resolve();
      });

      expect(mockOnSelectionChange).toHaveBeenCalledWith(new Set());
    });

    it('should not approve non-pending items', () => {
      const nonPending = new Set(['3', '4']); // approved and rejected

      const { container } = render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={nonPending}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      // Approve button should not show when there are no pending items selected
      // The component only renders the approve button when pendingSelected.length > 0
      expect(container.textContent).not.toContain('Approve');
      expect(container.textContent).toContain('Reject (2)'); // Reject button still shows
    });

    it('should disable approve when processing', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
          processing={true}
        />
      );

      const approveButton = screen.getByText('Processing...');
      expect(approveButton).toBeDisabled();
    });
  });

  describe('Bulk reject', () => {
    it('should call onReject with selected IDs and reason', async () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1', '2'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Reject (2)'));

      // Enter custom reason
      const reasonTextarea = screen.getByPlaceholderText('e.g., Duplicate content, Low quality...');
      fireEvent.change(reasonTextarea, { target: { value: 'Low quality content' } });

      fireEvent.click(screen.getByText('Reject'));

      expect(mockOnReject).toHaveBeenCalledWith(['1', '2'], 'Low quality content');
    });

    it('should use default rejection reason when none provided', async () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Reject (1)'));
      fireEvent.click(screen.getByText('Reject'));

      expect(mockOnReject).toHaveBeenCalledWith(['1'], 'Bulk rejected');
    });

    it('should clear selection and reason after reject', async () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Reject (1)'));

      const reasonTextarea = screen.getByPlaceholderText('e.g., Duplicate content, Low quality...');
      fireEvent.change(reasonTextarea, { target: { value: 'Test reason' } });

      // Wrap async action in act
      await act(async () => {
        fireEvent.click(screen.getByText('Reject'));
        // Wait for the async operation to complete
        await Promise.resolve();
      });

      expect(mockOnSelectionChange).toHaveBeenCalledWith(new Set());
    });
  });

  describe('Quick rejection reasons', () => {
    it('should pre-fill quick rejection reasons', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Reject (1)'));

      expect(screen.getByText('Duplicate')).toBeInTheDocument();
      expect(screen.getByText('Low quality')).toBeInTheDocument();
      expect(screen.getByText('Irrelevant')).toBeInTheDocument();
      expect(screen.getByText('NSFW')).toBeInTheDocument();
      expect(screen.getByText('Copyright')).toBeInTheDocument();
    });

    it('should set reason when quick reason clicked', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Reject (1)'));
      fireEvent.click(screen.getByText('Duplicate'));

      const reasonTextarea = screen.getByPlaceholderText('e.g., Duplicate content, Low quality...');
      expect(reasonTextarea).toHaveValue('Duplicate');
    });

    it('should show character count for custom reason', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Reject (1)'));

      const reasonTextarea = screen.getByPlaceholderText('e.g., Duplicate content, Low quality...');
      fireEvent.change(reasonTextarea, { target: { value: 'Test' } });

      expect(screen.getByText('4 / 500')).toBeInTheDocument();
    });

    it('should enforce max length of 500', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Reject (1)'));

      const reasonTextarea = screen.getByPlaceholderText('e.g., Duplicate content, Low quality...');
      expect(reasonTextarea).toHaveAttribute('maxLength', '500');
    });
  });

  describe('Export to CSV', () => {
    it('should call onExport when export clicked', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1', '2'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
          onExport={mockOnExport}
        />
      );

      fireEvent.click(screen.getByText('Export CSV'));

      expect(mockOnExport).toHaveBeenCalledWith(['1', '2']);
    });

    it('should not show export button when onExport not provided', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      expect(screen.queryByText('Export CSV')).not.toBeInTheDocument();
    });
  });

  describe('Priority slider', () => {
    it('should show priority range labels', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      // Expand approve options
      fireEvent.click(screen.getByText(/Approve \(/));

      expect(screen.getByText('Low')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
    });

    it('should enforce min value of 1', () => {
      const { container } = render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText(/Approve \(/));

      const slider = container.querySelector('input[type="range"]');
      expect(slider).toHaveAttribute('min', '1');
    });

    it('should enforce max value of 10', () => {
      const { container } = render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText(/Approve \(/));

      const slider = container.querySelector('input[type="range"]');
      expect(slider).toHaveAttribute('max', '10');
    });
  });

  describe('Modal close behavior', () => {
    it('should close approve options when cancel clicked', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      // Expand options
      fireEvent.click(screen.getByText(/Approve \(/));

      expect(screen.getByText('Approval Options')).toBeInTheDocument();

      // Click cancel
      fireEvent.click(screen.getAllByText('Cancel')[0]);

      expect(screen.queryByText('Approval Options')).not.toBeInTheDocument();
    });

    it('should close reject options when cancel clicked', () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Reject (1)'));
      expect(screen.getByText('Reject Items')).toBeInTheDocument();

      // Only one Cancel button visible when reject panel is open (approve panel is closed)
      fireEvent.click(screen.getAllByText('Cancel')[0]);

      expect(screen.queryByText('Reject Items')).not.toBeInTheDocument();
    });

    it('should close reject options on close modal callback', async () => {
      render(
        <BulkApprovalActions
          items={mockItems}
          selectedIds={new Set(['1'])}
          onSelectionChange={mockOnSelectionChange}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      );

      fireEvent.click(screen.getByText('Reject (1)'));
      expect(screen.getByText('Reject Items')).toBeInTheDocument();

      // After successful rejection, modal should close - wrap in act for async operation
      await act(async () => {
        fireEvent.click(screen.getByText('Reject'));
        await Promise.resolve();
      });

      expect(screen.queryByText('Reject Items')).not.toBeInTheDocument();
    });
  });
});

describe('BulkSelectionCheckbox', () => {
  const mockOnToggle = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render checked state', () => {
    render(
      <BulkSelectionCheckbox checked={true} onToggle={mockOnToggle} />
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeChecked();
  });

  it('should render unchecked state', () => {
    render(
      <BulkSelectionCheckbox checked={false} onToggle={mockOnToggle} />
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).not.toBeChecked();
  });

  it('should call onToggle when clicked', () => {
    render(
      <BulkSelectionCheckbox checked={false} onToggle={mockOnToggle} />
    );

    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    expect(mockOnToggle).toHaveBeenCalledTimes(1);
  });

  it('should be disabled when not selectable', () => {
    render(
      <BulkSelectionCheckbox checked={false} selectable={false} onToggle={mockOnToggle} />
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeDisabled();
  });

  it('should have proper ARIA label', () => {
    const { rerender } = render(
      <BulkSelectionCheckbox checked={false} onToggle={mockOnToggle} />
    );

    expect(screen.getByLabelText('Select item')).toBeInTheDocument();

    rerender(<BulkSelectionCheckbox checked={true} onToggle={mockOnToggle} />);

    expect(screen.getByLabelText('Deselect item')).toBeInTheDocument();
  });
});
