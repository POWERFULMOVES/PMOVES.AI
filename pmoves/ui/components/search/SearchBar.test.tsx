/* ═══════════════════════════════════════════════════════════════════════════
   Search Bar Component Tests
   Tests debounced search input with keyboard shortcuts and history
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SearchBar } from './SearchBar';

// Helper to get form element (forms without names can't use getByRole)
const getForm = (container: HTMLElement) => container.querySelector('form') as HTMLFormElement;

// Mock timers for debouncing tests
beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
});

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();

Object.defineProperty(global, 'localStorage', { value: localStorageMock });

describe('SearchBar', () => {
  const mockOnSearch = jest.fn();
  const mockOnToggleFilters = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock.clear();
  });

  describe('Debouncing', () => {
    it('should debounce search input (300ms delay)', async () => {
      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      fireEvent.change(input, { target: { value: 'test query' } });

      // Should not call onSearch immediately
      expect(mockOnSearch).not.toHaveBeenCalled();

      // Fast-forward 299ms - still not called
      jest.advanceTimersByTime(299);
      expect(mockOnSearch).not.toHaveBeenCalled();

      // Fast-forward past 300ms - now called
      jest.advanceTimersByTime(10);
      expect(mockOnSearch).toHaveBeenCalledTimes(1);
      expect(mockOnSearch).toHaveBeenCalledWith('test query');
    });

    it('should debounce only final value when typing rapidly', async () => {
      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');

      fireEvent.change(input, { target: { value: 't' } });
      jest.advanceTimersByTime(100);
      fireEvent.change(input, { target: { value: 'te' } });
      jest.advanceTimersByTime(100);
      fireEvent.change(input, { target: { value: 'test' } });
      jest.advanceTimersByTime(100);
      fireEvent.change(input, { target: { value: 'test query' } });

      // Still not called at 400ms total because debounce resets
      expect(mockOnSearch).not.toHaveBeenCalled();

      jest.advanceTimersByTime(300);

      expect(mockOnSearch).toHaveBeenCalledTimes(1);
      expect(mockOnSearch).toHaveBeenCalledWith('test query');
    });
  });

  describe('Keyboard shortcuts', () => {
    it('should focus on Cmd+K keydown', () => {
      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      expect(input).not.toHaveFocus();

      fireEvent.keyDown(window, { key: 'k', metaKey: true });

      expect(input).toHaveFocus();
    });

    it('should focus on Ctrl+K keydown', () => {
      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      expect(input).not.toHaveFocus();

      fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

      expect(input).toHaveFocus();
    });

    it('should show history dropdown on keyboard shortcut focus', () => {
      localStorageMock.setItem('pmoves_search_history', JSON.stringify([
        { query: 'previous search', timestamp: Date.now() }
      ]));

      render(<SearchBar onSearch={mockOnSearch} />);

      fireEvent.keyDown(window, { key: 'k', metaKey: true });

      expect(screen.getByText('Recent Searches')).toBeInTheDocument();
    });

    it('should blur input on Escape keydown', () => {
      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      input.focus();

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(input).not.toHaveFocus();
    });

    it('should hide history on Escape keydown', () => {
      localStorageMock.setItem('pmoves_search_history', JSON.stringify([
        { query: 'previous search', timestamp: Date.now() }
      ]));

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      fireEvent.focus(input);

      expect(screen.getByText('Recent Searches')).toBeInTheDocument();

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(screen.queryByText('Recent Searches')).not.toBeInTheDocument();
    });
  });

  describe('Search history', () => {
    it('should load and display search history from localStorage', () => {
      const history = [
        { query: 'first search', timestamp: Date.now() - 100000 },
        { query: 'second search', timestamp: Date.now() - 50000 },
      ];
      localStorageMock.setItem('pmoves_search_history', JSON.stringify(history));

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      fireEvent.focus(input);

      expect(screen.getByText('Recent Searches')).toBeInTheDocument();
      expect(screen.getByText('first search')).toBeInTheDocument();
      expect(screen.getByText('second search')).toBeInTheDocument();
    });

    it('should add new searches to history (max 10)', async () => {
      const { container } = render(<SearchBar onSearch={mockOnSearch} />);

      const form = getForm(container);
      const input = screen.getByPlaceholderText('Search knowledge base...');

      // Submit 11 searches
      for (let i = 1; i <= 11; i++) {
        fireEvent.change(input, { target: { value: `search ${i}` } });
        fireEvent.submit(form);
        jest.runAllTimers();
      }

      const stored = localStorageMock.getItem('pmoves_search_history');
      expect(stored).toBeTruthy();

      const history = JSON.parse(stored!);
      expect(history).toHaveLength(10);
      expect(history[0].query).toBe('search 11'); // Most recent first
      expect(history[9].query).toBe('search 2'); // Oldest within limit
      expect(history.find((h: any) => h.query === 'search 1')).toBeUndefined();
    });

    it('should remove duplicate queries from history', async () => {
      const existingHistory = [
        { query: 'existing', timestamp: Date.now() },
        { query: 'duplicate', timestamp: Date.now() },
      ];
      localStorageMock.setItem('pmoves_search_history', JSON.stringify(existingHistory));

      const { container } = render(<SearchBar onSearch={mockOnSearch} />);

      const form = getForm(container);
      const input = screen.getByPlaceholderText('Search knowledge base...');

      fireEvent.change(input, { target: { value: 'duplicate' } });
      fireEvent.submit(form);
      jest.runAllTimers();

      const stored = localStorageMock.getItem('pmoves_search_history');
      const history = JSON.parse(stored!);

      const duplicates = history.filter((h: any) => h.query === 'duplicate');
      expect(duplicates).toHaveLength(1);
      expect(history[0].query).toBe('duplicate'); // Moved to top
    });

    it('should clear history when clear button clicked', () => {
      const history = [
        { query: 'old search', timestamp: Date.now() },
      ];
      localStorageMock.setItem('pmoves_search_history', JSON.stringify(history));

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      fireEvent.focus(input);

      const clearButton = screen.getByText('Clear');
      fireEvent.click(clearButton);

      expect(screen.queryByText('old search')).not.toBeInTheDocument();

      const stored = localStorageMock.getItem('pmoves_search_history');
      expect(stored).toBeNull();
    });

    it('should search clicked history item', () => {
      const history = [
        { query: 'history item', timestamp: Date.now() },
      ];
      localStorageMock.setItem('pmoves_search_history', JSON.stringify(history));

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      fireEvent.focus(input);

      const historyButton = screen.getByText('history item');
      fireEvent.click(historyButton);

      expect(mockOnSearch).toHaveBeenCalledWith('history item');
      expect(screen.queryByText('Recent Searches')).not.toBeInTheDocument();
    });

    it('should handle localStorage errors gracefully', () => {
      // Make localStorage throw error
      jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });

      // Should not throw, just silently fail
      expect(() => {
        render(<SearchBar onSearch={mockOnSearch} />);
      }).not.toThrow();

      const input = screen.getByPlaceholderText('Search knowledge base...');
      expect(input).toBeInTheDocument();
    });
  });

  describe('Form submission', () => {
    it('should call onSearch with query on form submit', () => {
      const { container } = render(<SearchBar onSearch={mockOnSearch} />);

      const form = getForm(container);
      const input = screen.getByPlaceholderText('Search knowledge base...');

      fireEvent.change(input, { target: { value: 'manual search' } });
      fireEvent.submit(form);

      expect(mockOnSearch).toHaveBeenCalledWith('manual search');
    });

    it('should prevent empty query submission', () => {
      const { container } = render(<SearchBar onSearch={mockOnSearch} />);

      const form = getForm(container);
      const input = screen.getByPlaceholderText('Search knowledge base...');

      fireEvent.change(input, { target: { value: '   ' } });
      fireEvent.submit(form);

      expect(mockOnSearch).not.toHaveBeenCalled();
    });

    it('should trim whitespace from query', () => {
      const { container } = render(<SearchBar onSearch={mockOnSearch} />);

      const form = getForm(container);
      const input = screen.getByPlaceholderText('Search knowledge base...');

      fireEvent.change(input, { target: { value: '  padded query  ' } });
      fireEvent.submit(form);

      expect(mockOnSearch).toHaveBeenCalledWith('padded query');
    });

    it('should hide keyboard shortcut hint when typing', () => {
      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      const hint = screen.getByText(/⌘/);

      expect(hint).toBeInTheDocument();

      fireEvent.change(input, { target: { value: 'test' } });

      expect(hint).not.toBeInTheDocument();
    });
  });

  describe('Loading state', () => {
    it('should show loading state when loading prop is true', () => {
      render(<SearchBar onSearch={mockOnSearch} loading={true} />);

      expect(screen.getByText('Searching...')).toBeInTheDocument();
    });

    it('should disable input during loading', () => {
      render(<SearchBar onSearch={mockOnSearch} loading={true} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      expect(input).toBeDisabled();
    });

    it('should disable submit button when query is empty', () => {
      render(<SearchBar onSearch={mockOnSearch} />);

      const submitButton = screen.getByRole('button', { name: 'Search' });
      expect(submitButton).toBeDisabled();
    });

    it('should disable submit button during loading', () => {
      render(<SearchBar onSearch={mockOnSearch} loading={true} />);

      // getByText returns the span, so we need to get the button via role
      const submitButton = screen.getByRole('button', { name: /searching/i });
      expect(submitButton).toBeDisabled();
    });
  });

  describe('Filter toggle', () => {
    it('should render filter toggle button when onToggleFilters provided', () => {
      render(<SearchBar onSearch={mockOnSearch} onToggleFilters={mockOnToggleFilters} />);

      const filterButton = screen.getByLabelText('Toggle filters');
      expect(filterButton).toBeInTheDocument();
    });

    it('should call onToggleFilters when filter button clicked', () => {
      render(<SearchBar onSearch={mockOnSearch} onToggleFilters={mockOnToggleFilters} />);

      const filterButton = screen.getByLabelText('Toggle filters');
      fireEvent.click(filterButton);

      expect(mockOnToggleFilters).toHaveBeenCalledTimes(1);
    });

    it('should highlight filter button when hasActiveFilters is true', () => {
      const { rerender } = render(
        <SearchBar onSearch={mockOnSearch} onToggleFilters={mockOnToggleFilters} hasActiveFilters={false} />
      );

      const filterButton = screen.getByLabelText('Toggle filters');
      expect(filterButton.className).not.toContain('bg-blue-50');
      expect(filterButton.className).not.toContain('border-blue-500');

      rerender(
        <SearchBar onSearch={mockOnSearch} onToggleFilters={mockOnToggleFilters} hasActiveFilters={true} />
      );

      expect(filterButton.className).toContain('bg-blue-50');
      expect(filterButton.className).toContain('border-blue-500');
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<SearchBar onSearch={mockOnSearch} onToggleFilters={mockOnToggleFilters} />);

      // Input uses placeholder as accessible name
      const input = screen.getByPlaceholderText('Search knowledge base...');
      expect(input).toBeInTheDocument();

      const filterButton = screen.getByLabelText('Toggle filters');
      expect(filterButton).toBeInTheDocument();

      const submitButton = screen.getByRole('button', { name: 'Search' });
      expect(submitButton).toBeInTheDocument();
    });

    it('should be keyboard navigable', () => {
      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      input.focus();

      fireEvent.keyDown(input, { key: 'Enter' });

      // Empty query should not submit
      expect(mockOnSearch).not.toHaveBeenCalled();
    });
  });

  describe('Default value', () => {
    it('should initialize with default value', () => {
      render(<SearchBar onSearch={mockOnSearch} defaultValue="initial query" />);

      const input = screen.getByPlaceholderText('Search knowledge base...');
      expect(input).toHaveValue('initial query');
    });
  });

  describe('Custom placeholder', () => {
    it('should use custom placeholder when provided', () => {
      render(<SearchBar onSearch={mockOnSearch} placeholder="Search videos..." />);

      expect(screen.getByPlaceholderText('Search videos...')).toBeInTheDocument();
    });
  });
});
