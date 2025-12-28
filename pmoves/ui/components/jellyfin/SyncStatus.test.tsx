/* ═══════════════════════════════════════════════════════════════════════════
   Sync Status Component Tests
   Tests Jellyfin sync status with controls and real-time updates
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { SyncStatus } from './SyncStatus';
import type { JellyfinSyncStatusInfo } from '@/lib/api/jellyfin';

const mockSyncStatus: JellyfinSyncStatusInfo = {
  status: 'idle',
  lastSync: new Date(Date.now() - 1000 * 60 * 5).toISOString(), // 5 minutes ago
  videosLinked: 42,
  pendingBackfill: 15,
  errors: 0,
};

describe('SyncStatus', () => {
  const mockOnRefresh = jest.fn();
  const mockOnSync = jest.fn();
  const mockOnBackfill = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('Status display', () => {
    it('should display sync status with health indicator', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      expect(screen.getByText('Sync Status')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument(); // Videos Linked
      expect(screen.getByText('15')).toBeInTheDocument(); // Pending Backfill
      expect(screen.getByText('idle')).toBeInTheDocument(); // Status
    });

    it('should show pulse animation when status is idle/completed', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      // Check for pulse animation indicator
      const pulseElement = document.querySelector('.animate-ping');
      expect(pulseElement).toBeInTheDocument();
    });

    it('should not show pulse animation when status is syncing', () => {
      const syncingStatus: JellyfinSyncStatusInfo = {
        ...mockSyncStatus,
        status: 'syncing',
      };

      render(
        <SyncStatus
          status={syncingStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      const pulseElement = document.querySelector('.animate-ping');
      expect(pulseElement).not.toBeInTheDocument();
    });

    it('should show error message when errors > 0', () => {
      const errorStatus: JellyfinSyncStatusInfo = {
        ...mockSyncStatus,
        errors: 3,
        lastError: 'Connection timeout',
      };

      render(
        <SyncStatus
          status={errorStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      expect(screen.getByText(/3 error\(s\) detected/)).toBeInTheDocument();
      expect(screen.getByText(/Check logs for details/)).toBeInTheDocument();

      // Error count should have pulse animation
      const errorCount = screen.getByText('3');
      expect(errorCount.className).toContain('animate-pulse');
    });
  });

  describe('Time formatting', () => {
    it('should format relative time (just now, 2h ago, etc.)', () => {
      const justNow: JellyfinSyncStatusInfo = {
        ...mockSyncStatus,
        lastSync: new Date().toISOString(),
      };

      render(
        <SyncStatus
          status={justNow}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      expect(screen.getByText('Last: Just now')).toBeInTheDocument();
    });

    it('should show "2h ago" for 2 hours ago', () => {
      const twoHoursAgo: JellyfinSyncStatusInfo = {
        ...mockSyncStatus,
        lastSync: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
      };

      render(
        <SyncStatus
          status={twoHoursAgo}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      expect(screen.getByText('Last: 2h ago')).toBeInTheDocument();
    });

    it('should show date for older than 24 hours', () => {
      const oldDate: JellyfinSyncStatusInfo = {
        ...mockSyncStatus,
        lastSync: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
      };

      render(
        <SyncStatus
          status={oldDate}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      const formattedDate = new Date(oldDate.lastSync!).toLocaleDateString();
      expect(screen.getByText(`Last: ${formattedDate}`)).toBeInTheDocument();
    });

    it('should show "Never" when lastSync is null', () => {
      const neverSynced: JellyfinSyncStatusInfo = {
        ...mockSyncStatus,
        lastSync: null,
      };

      render(
        <SyncStatus
          status={neverSynced}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      expect(screen.getByText('Last: Never')).toBeInTheDocument();
    });
  });

  describe('Action buttons', () => {
    it('should call onRefresh when refresh clicked', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      const refreshButton = screen.getByLabelText('Refresh sync status');
      fireEvent.click(refreshButton);

      expect(mockOnRefresh).toHaveBeenCalledTimes(1);
    });

    it('should call onSync when sync clicked', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      const syncButton = screen.getByText('Sync Now');
      fireEvent.click(syncButton);

      expect(mockOnSync).toHaveBeenCalledTimes(1);
    });

    it('should call onBackfill with default limit (50) when backfill clicked', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      const backfillButton = screen.getByText('Run Backfill');
      fireEvent.click(backfillButton);

      expect(mockOnBackfill).toHaveBeenCalledWith(50);
    });

    it('should disable refresh button during syncing', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
          syncing={true}
        />
      );

      const refreshButton = screen.getByLabelText('Refresh sync status');
      expect(refreshButton).toBeDisabled();
    });

    it('should disable refresh button during backfilling', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
          backfilling={true}
        />
      );

      const refreshButton = screen.getByLabelText('Refresh sync status');
      expect(refreshButton).toBeDisabled();
    });
  });

  describe('Loading states', () => {
    it('should show loading state during sync', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
          syncing={true}
        />
      );

      expect(screen.getByText('Syncing...')).toBeInTheDocument();
      const syncButton = screen.getByText('Syncing...');
      expect(syncButton).toBeDisabled();
    });

    it('should show loading state during backfill', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
          backfilling={true}
        />
      );

      expect(screen.getByText('Backfilling...')).toBeInTheDocument();
      const backfillButton = screen.getByText('Backfilling...');
      expect(backfillButton).toBeDisabled();
    });
  });

  describe('Progress bar', () => {
    it('should show pending backfill count', () => {
      const statusWithBacklog = {
        ...mockSyncStatus,
        pendingBackfill: 20,
      };

      render(
        <SyncStatus
          status={statusWithBacklog}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      expect(screen.getByText('20 items pending')).toBeInTheDocument();
    });
  });

  describe('No status available', () => {
    it('should show message when status is null', () => {
      const { container } = render(
        <SyncStatus
          status={null}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      // Text is in a single div element
      expect(container.textContent).toContain('No sync status available');
      expect(container.textContent).toContain('Click Refresh to check');
    });
  });

  describe('Error display', () => {
    it('should show error message when error prop provided', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
          error="Failed to connect to Jellyfin"
        />
      );

      expect(screen.getByText('Failed to connect to Jellyfin')).toBeInTheDocument();
    });
  });

  describe('Pending items indicator', () => {
    it('should show pending count when backfill items exist', () => {
      render(
        <SyncStatus
          status={mockSyncStatus}
          onRefresh={mockOnRefresh}
          onSync={mockOnSync}
          onBackfill={mockOnBackfill}
        />
      );

      expect(screen.getByText('15 items pending')).toBeInTheDocument();
    });
  });
});
