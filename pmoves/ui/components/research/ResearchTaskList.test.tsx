/* ═══════════════════════════════════════════════════════════════════════════
   Research Task List Component Tests
   Tests task display with filtering and status tracking
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent } from '@testing-library/react';
import { ResearchTaskList } from './ResearchTaskList';
import type { ResearchTask, ResearchStatus } from '@/lib/api/research';

const mockTasks: ResearchTask[] = [
  {
    id: '1',
    query: 'What is quantum computing?',
    status: 'pending',
    mode: 'tensorzero',
    createdAt: '2025-01-15T10:00:00Z',
  },
  {
    id: '2',
    query: 'Explain machine learning basics',
    status: 'running',
    mode: 'openrouter',
    createdAt: '2025-01-15T09:30:00Z',
    iterations: 5,
  },
  {
    id: '3',
    query: 'History of the Roman Empire',
    status: 'completed',
    mode: 'local',
    createdAt: '2025-01-14T14:00:00Z',
    iterations: 12,
  },
  {
    id: '4',
    query: 'Failed research task',
    status: 'failed',
    mode: 'tensorzero',
    createdAt: '2025-01-14T10:00:00Z',
    errorMessage: 'API rate limit exceeded',
  },
  {
    id: '5',
    query: 'Cancelled task',
    status: 'cancelled',
    mode: 'hybrid',
    createdAt: '2025-01-13T16:00:00Z',
  },
];

describe('ResearchTaskList', () => {
  const mockOnSelect = jest.fn();
  const mockOnCancel = jest.fn();
  const mockOnRefresh = jest.fn();
  const mockOnStatusFilter = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Task display', () => {
    it('should render all tasks', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      expect(screen.getByText('What is quantum computing?')).toBeInTheDocument();
      expect(screen.getByText('Explain machine learning basics')).toBeInTheDocument();
      expect(screen.getByText('History of the Roman Empire')).toBeInTheDocument();
      expect(screen.getByText('Failed research task')).toBeInTheDocument();
      expect(screen.getByText('Cancelled task')).toBeInTheDocument();
    });

    it('should show task count', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      expect(screen.getByText('5 of 5')).toBeInTheDocument();
    });
  });

  describe('Status badges', () => {
    it('should show correct badge for pending status', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[0]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      const badge = screen.getByText('pending');
      expect(badge.className).toContain('bg-gray-100');
      expect(badge.className).toContain('text-gray-800');
    });

    it('should show correct badge for running status', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[1]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      const badge = screen.getByText('running');
      expect(badge.className).toContain('bg-blue-100');
      expect(badge.className).toContain('text-blue-800');
      expect(badge.className).toContain('animate-pulse');
    });

    it('should show correct badge for completed status', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[2]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      const badge = screen.getByText('completed');
      expect(badge.className).toContain('bg-green-100');
      expect(badge.className).toContain('text-green-800');
    });

    it('should show correct badge for failed status', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[3]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      const badge = screen.getByText('failed');
      expect(badge.className).toContain('bg-red-100');
      expect(badge.className).toContain('text-red-800');
    });

    it('should show correct badge for cancelled status', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[4]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      const badge = screen.getByText('cancelled');
      expect(badge.className).toContain('bg-yellow-100');
      expect(badge.className).toContain('text-yellow-800');
    });

    it('should show status icons', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      expect(screen.getByText('⏳')).toBeInTheDocument(); // pending
      expect(screen.getByText('🔄')).toBeInTheDocument(); // running
      expect(screen.getByText('✅')).toBeInTheDocument(); // completed
      expect(screen.getByText('❌')).toBeInTheDocument(); // failed
      expect(screen.getByText('⏹️')).toBeInTheDocument(); // cancelled
    });
  });

  describe('Filter by status', () => {
    it('should filter tasks by status', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          statusFilter="running"
          onStatusFilter={mockOnStatusFilter}
        />
      );

      // Should only show running task
      expect(screen.getByText('Explain machine learning basics')).toBeInTheDocument();
      expect(screen.queryByText('What is quantum computing?')).not.toBeInTheDocument();
    });

    it('should show all tasks when filter is "all"', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          statusFilter="all"
          onStatusFilter={mockOnStatusFilter}
        />
      );

      expect(screen.getByText('5 of 5')).toBeInTheDocument();
    });

    it('should update filter when select changed', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          statusFilter="all"
          onStatusFilter={mockOnStatusFilter}
        />
      );

      const select = screen.getByDisplayValue('All');
      fireEvent.change(select, { target: { value: 'completed' } });

      expect(mockOnStatusFilter).toHaveBeenCalledWith('completed');
    });

    it('should show correct count for filtered results', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          statusFilter="completed"
          onStatusFilter={mockOnStatusFilter}
        />
      );

      expect(screen.getByText('1 of 5')).toBeInTheDocument();
    });
  });

  describe('Task selection', () => {
    it('should highlight selected task', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          selectedId="1"
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      const selectedCard = screen.getByText('What is quantum computing?').closest('.cursor-pointer');
      expect(selectedCard).toHaveClass('bg-blue-50');
      expect(selectedCard).toHaveClass('border-blue-500');
    });

    it('should call onSelect when task clicked', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      fireEvent.click(screen.getByText('What is quantum computing?').closest('.cursor-pointer')!);

      expect(mockOnSelect).toHaveBeenCalledWith(mockTasks[0]);
    });
  });

  describe('Cancel running task', () => {
    it('should show cancel button for running tasks', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[1]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          onCancel={mockOnCancel}
        />
      );

      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });

    it('should call onCancel when cancel clicked', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[1]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          onCancel={mockOnCancel}
        />
      );

      const cancelButton = screen.getByText('Cancel');
      fireEvent.click(cancelButton);

      expect(mockOnCancel).toHaveBeenCalledWith('2');
    });

    it('should not show cancel button for non-running tasks', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[0]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          onCancel={mockOnCancel}
        />
      );

      expect(screen.queryByText('Cancel')).not.toBeInTheDocument();
    });

    it('should not show cancel button when onCancel not provided', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[1]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      expect(screen.queryByText('Cancel')).not.toBeInTheDocument();
    });
  });

  describe('Error display', () => {
    it('should show error message for failed tasks', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[3]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      expect(screen.getByText('API rate limit exceeded')).toBeInTheDocument();
      const errorContainer = screen.getByText('API rate limit exceeded').closest('div');
      expect(errorContainer).toHaveClass('bg-red-50');
    });
  });

  describe('Time formatting', () => {
    it('should format relative time correctly', () => {
      // Create a task with recent timestamp
      const recentTask: ResearchTask = {
        id: 'recent',
        query: 'Recent task',
        status: 'pending',
        mode: 'tensorzero',
        createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 minutes ago
      };

      render(
        <ResearchTaskList
          tasks={[recentTask]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      expect(screen.getByText('5m ago')).toBeInTheDocument();
    });

    it('should show "Just now" for very recent tasks', () => {
      const recentTask: ResearchTask = {
        id: 'recent',
        query: 'Recent task',
        status: 'pending',
        mode: 'tensorzero',
        createdAt: new Date().toISOString(),
      };

      render(
        <ResearchTaskList
          tasks={[recentTask]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      expect(screen.getByText('Just now')).toBeInTheDocument();
    });
  });

  describe('Refresh button', () => {
    it('should call onRefresh when refresh clicked', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      const refreshButton = screen.getByLabelText('Refresh tasks');
      fireEvent.click(refreshButton);

      expect(mockOnRefresh).toHaveBeenCalledTimes(1);
    });

    it('should show spinner when refreshing', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          refreshing={true}
        />
      );

      const spinner = screen.getByLabelText('Refresh tasks').querySelector('svg');
      expect(spinner).toHaveClass('animate-spin');
    });

    it('should disable refresh button when refreshing', () => {
      render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          refreshing={true}
        />
      );

      const refreshButton = screen.getByLabelText('Refresh tasks');
      expect(refreshButton).toBeDisabled();
    });
  });

  describe('Empty state', () => {
    it('should show empty state when no tasks', () => {
      render(
        <ResearchTaskList
          tasks={[]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      expect(screen.getByText('No research tasks yet.')).toBeInTheDocument();
      expect(screen.getByText('Start one above!')).toBeInTheDocument();
      expect(screen.getByText('🔬')).toBeInTheDocument();
    });

    it('should show filter empty state when filter matches nothing', () => {
      // Provide tasks but none match the "running" filter
      const nonRunningTasks = mockTasks.filter(t => t.status !== 'running');
      const { container } = render(
        <ResearchTaskList
          tasks={nonRunningTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
          statusFilter="running"
          onStatusFilter={mockOnStatusFilter}
        />
      );

      // Should show "No tasks match this filter." when filter yields no results
      expect(container.textContent).toContain('No tasks match this filter.');
    });
  });

  describe('Mode display', () => {
    it('should show task mode', () => {
      const { container } = render(
        <ResearchTaskList
          tasks={mockTasks}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      // Use container to avoid multiple element errors (modes appear in badges and dropdown)
      expect(container.textContent).toContain('tensorzero');
      expect(container.textContent).toContain('openrouter');
      expect(container.textContent).toContain('local');
      expect(container.textContent).toContain('hybrid');
    });
  });

  describe('Iterations display', () => {
    it('should show iterations when present', () => {
      const { container } = render(
        <ResearchTaskList
          tasks={[mockTasks[1]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      // Text is split across elements (e.g., "• 5 iterations")
      expect(container.textContent).toContain('5 iterations');
    });

    it('should not show iterations when not present', () => {
      render(
        <ResearchTaskList
          tasks={[mockTasks[0]]}
          onSelect={mockOnSelect}
          onRefresh={mockOnRefresh}
        />
      );

      expect(screen.queryByText(/\d+ iterations/)).not.toBeInTheDocument();
    });
  });
});
