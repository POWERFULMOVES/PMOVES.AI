/* ═══════════════════════════════════════════════════════════════════════════
   Backfill Controls Component Tests
   Tests configuration and management of Jellyfin backfill operations
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent } from '@testing-library/react';
import { BackfillControls } from './BackfillControls';

describe('BackfillControls', () => {
  const mockOnStart = jest.fn();
  const mockOnCancel = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Expand/collapse options panel', () => {
    it('should be collapsed by default', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      // Expanded options should not be visible
      expect(screen.queryByLabelText('Batch Size')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Priority')).not.toBeInTheDocument();
    });

    it('should expand when toggle button clicked', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      const toggleButton = screen.getByLabelText('Expand');
      fireEvent.click(toggleButton);

      expect(screen.getByLabelText('Batch Size')).toBeInTheDocument();
      expect(screen.getByLabelText('Priority')).toBeInTheDocument();
    });

    it('should collapse when already expanded', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      const toggleButton = screen.getByLabelText('Expand');
      fireEvent.click(toggleButton); // Expand
      fireEvent.click(toggleButton); // Collapse

      expect(screen.queryByLabelText('Batch Size')).not.toBeInTheDocument();
    });

    it('should rotate chevron icon when expanded', () => {
      const { container } = render(<BackfillControls onStart={mockOnStart} />);

      const chevron = container.querySelector('svg');
      expect(chevron).not.toHaveClass('rotate-180');

      fireEvent.click(screen.getByLabelText('Expand'));

      expect(chevron).toHaveClass('rotate-180');
    });
  });

  describe('Limit (batch size) validation', () => {
    it('should validate limit from preset options', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      const select = screen.getByLabelText('Batch Size');
      expect(select).toHaveValue('50'); // Default

      fireEvent.change(select, { target: { value: '100' } });
      expect(select).toHaveValue('100');

      fireEvent.change(select, { target: { value: '500' } });
      expect(select).toHaveValue('500');
    });

    it('should update start button text with new limit', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      expect(screen.getByText('Start Backfill (50 items)')).toBeInTheDocument();

      fireEvent.click(screen.getByLabelText('Expand'));
      fireEvent.change(screen.getByLabelText('Batch Size'), { target: { value: '100' } });

      expect(screen.getByText('Start Backfill (100 items)')).toBeInTheDocument();
    });
  });

  describe('Priority selection', () => {
    it('should select priority option', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      const select = screen.getByLabelText('Priority');
      expect(select).toHaveValue('normal'); // Default

      fireEvent.change(select, { target: { value: 'high' } });
      expect(select).toHaveValue('high');

      fireEvent.change(select, { target: { value: 'low' } });
      expect(select).toHaveValue('low');
    });
  });

  describe('Skip linked checkbox', () => {
    it('should be checked by default', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      const checkbox = screen.getByLabelText('Skip already linked items');
      expect(checkbox).toBeChecked();
    });

    it('should toggle when clicked', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      const checkbox = screen.getByLabelText('Skip already linked items');
      fireEvent.click(checkbox);

      expect(checkbox).not.toBeChecked();
    });
  });

  describe('Date range inputs', () => {
    it('should accept date from input', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      const input = screen.getByLabelText('From Date');
      fireEvent.change(input, { target: { value: '2025-01-01' } });

      expect(input).toHaveValue('2025-01-01');
    });

    it('should accept date to input', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      const input = screen.getByLabelText('To Date');
      fireEvent.change(input, { target: { value: '2025-12-31' } });

      expect(input).toHaveValue('2025-12-31');
    });

    it('should clear date when empty value set', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      const input = screen.getByLabelText('From Date');
      fireEvent.change(input, { target: { value: '2025-01-01' } });
      fireEvent.change(input, { target: { value: '' } });

      expect(input).toHaveValue('');
    });
  });

  describe('Start action', () => {
    it('should call onStart with options when start clicked', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      // Change some options
      fireEvent.change(screen.getByLabelText('Batch Size'), { target: { value: '100' } });
      fireEvent.change(screen.getByLabelText('Priority'), { target: { value: 'high' } });

      // Start backfill
      fireEvent.click(screen.getByText('Start Backfill (100 items)'));

      expect(mockOnStart).toHaveBeenCalledWith({
        limit: 100,
        priority: 'high',
        skipLinked: true,
        dateFrom: undefined,
        dateTo: undefined,
      });
    });

    it('should include date range in options when set', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      fireEvent.change(screen.getByLabelText('From Date'), { target: { value: '2025-01-01' } });
      fireEvent.change(screen.getByLabelText('To Date'), { target: { value: '2025-06-30' } });

      fireEvent.click(screen.getByText('Start Backfill (50 items)'));

      expect(mockOnStart).toHaveBeenCalledWith({
        limit: 50,
        priority: 'normal',
        skipLinked: true,
        dateFrom: '2025-01-01',
        dateTo: '2025-06-30',
      });
    });
  });

  describe('Progress bar during backfill', () => {
    it('should show progress bar when running', () => {
      const { container } = render(<BackfillControls onStart={mockOnStart} running={true} progress={65} />);

      expect(screen.getByText('Processing...')).toBeInTheDocument();
      expect(screen.getByText('65%')).toBeInTheDocument();

      // Query the progress bar by its styling class
      const progressBar = container.querySelector('.bg-blue-600.h-2.rounded-full') as HTMLElement;
      expect(progressBar?.style.width).toBe('65%');
    });

    it('should show processed/queued counts', () => {
      render(
        <BackfillControls onStart={mockOnStart} running={true} progress={50} processed={25} queued={50} />
      );

      expect(screen.getByText('25 of 50 items processed')).toBeInTheDocument();
    });

    it('should not show processed count when 0', () => {
      render(<BackfillControls onStart={mockOnStart} running={true} progress={30} queued={100} />);

      expect(screen.queryByText(/of .* items processed/)).not.toBeInTheDocument();
    });
  });

  describe('Inputs disabled while running', () => {
    it('should disable inputs when running is true', () => {
      render(<BackfillControls onStart={mockOnStart} running={true} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      expect(screen.getByLabelText('Batch Size')).toBeDisabled();
      expect(screen.getByLabelText('Priority')).toBeDisabled();
      expect(screen.getByLabelText('Skip already linked items')).toBeDisabled();
      expect(screen.getByLabelText('From Date')).toBeDisabled();
      expect(screen.getByLabelText('To Date')).toBeDisabled();
    });

    it('should enable inputs when running is false', () => {
      render(<BackfillControls onStart={mockOnStart} running={false} />);

      fireEvent.click(screen.getByLabelText('Expand'));

      expect(screen.getByLabelText('Batch Size')).not.toBeDisabled();
      expect(screen.getByLabelText('Priority')).not.toBeDisabled();
    });
  });

  describe('Cancel button', () => {
    it('should show cancel button when running', () => {
      render(<BackfillControls onStart={mockOnStart} onCancel={mockOnCancel} running={true} />);

      expect(screen.getByText('Cancel Backfill')).toBeInTheDocument();
      expect(screen.queryByText('Start Backfill')).not.toBeInTheDocument();
    });

    it('should call onCancel when cancel clicked', () => {
      render(<BackfillControls onStart={mockOnStart} onCancel={mockOnCancel} running={true} />);

      fireEvent.click(screen.getByText('Cancel Backfill'));

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
    });

    it('should show cancel button when running even without onCancel handler', () => {
      render(<BackfillControls onStart={mockOnStart} running={true} />);

      // Cancel button displays but click handler won't do anything if onCancel is not provided
      expect(screen.getByText('Cancel Backfill')).toBeInTheDocument();
    });
  });

  describe('Info text', () => {
    it('should show info about backfill', () => {
      render(<BackfillControls onStart={mockOnStart} />);

      expect(
        screen.getByText('Backfill matches unlinked YouTube videos to Jellyfin library items.')
      ).toBeInTheDocument();
    });
  });
});
