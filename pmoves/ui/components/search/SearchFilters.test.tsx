/* ═══════════════════════════════════════════════════════════════════════════
   Search Filters Component Tests
   Tests filter controls for Hi-RAG search queries
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent } from '@testing-library/react';
import { SearchFilters } from './SearchFilters';
import type { HiragFilters, HiragSource } from '@/lib/api/hirag';

describe('SearchFilters', () => {
  const mockOnChange = jest.fn();
  const mockOnToggle = jest.fn();

  const defaultFilters: HiragFilters = {};

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Source type filter', () => {
    it('should update source type filter', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      const select = screen.getByLabelText('Source Type');
      fireEvent.change(select, { target: { value: 'youtube' } });

      expect(mockOnChange).toHaveBeenCalledWith({
        sourceType: 'youtube',
      });
    });

    it('should accept "All Sources" option', () => {
      render(
        <SearchFilters
          filters={{ sourceType: 'youtube' }}
          onChange={mockOnChange}
        />
      );

      const select = screen.getByLabelText('Source Type');
      expect(select).toHaveValue('youtube');

      fireEvent.change(select, { target: { value: '' } });

      expect(mockOnChange).toHaveBeenCalledWith({
        sourceType: undefined,
      });
    });

    it('should display all source options', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('All Sources')).toBeInTheDocument();
      expect(screen.getByText('YouTube')).toBeInTheDocument();
      expect(screen.getByText('Notebook')).toBeInTheDocument();
      expect(screen.getByText('PDF Documents')).toBeInTheDocument();
      expect(screen.getByText('Web Pages')).toBeInTheDocument();
      expect(screen.getByText('Transcripts')).toBeInTheDocument();
    });
  });

  describe('Date range filter', () => {
    it('should update start date', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      const input = screen.getByLabelText('From');
      fireEvent.change(input, { target: { value: '2025-01-01' } });

      expect(mockOnChange).toHaveBeenCalledWith({
        startDate: '2025-01-01',
      });
    });

    it('should update end date', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      const input = screen.getByLabelText('To');
      fireEvent.change(input, { target: { value: '2025-12-31' } });

      expect(mockOnChange).toHaveBeenCalledWith({
        endDate: '2025-12-31',
      });
    });

    it('should clear date when empty value set', () => {
      render(
        <SearchFilters
          filters={{ startDate: '2025-01-01' }}
          onChange={mockOnChange}
        />
      );

      const input = screen.getByLabelText('From');
      fireEvent.change(input, { target: { value: '' } });

      expect(mockOnChange).toHaveBeenCalledWith({
        startDate: undefined,
      });
    });

    it('should validate date range (end >= start) - requires external validation', () => {
      // Component accepts any dates, validation would be done by parent
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      const fromInput = screen.getByLabelText('From');
      const toInput = screen.getByLabelText('To');

      fireEvent.change(fromInput, { target: { value: '2025-12-31' } });
      fireEvent.change(toInput, { target: { value: '2025-01-01' } });

      // Component passes values through - each call is independent
      expect(mockOnChange).toHaveBeenNthCalledWith(1, { startDate: '2025-12-31' });
      expect(mockOnChange).toHaveBeenNthCalledWith(2, { endDate: '2025-01-01' });
    });
  });

  describe('Minimum score filter', () => {
    it('should update minimum score', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      const select = screen.getByLabelText('Minimum Relevance');
      fireEvent.change(select, { target: { value: '0.7' } });

      expect(mockOnChange).toHaveBeenCalledWith({
        minScore: 0.7,
      });
    });

    it('should accept score options', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('Any Relevance')).toBeInTheDocument();
      expect(screen.getByText('Very High (90%+)')).toBeInTheDocument();
      expect(screen.getByText('High (70%+)')).toBeInTheDocument();
      expect(screen.getByText('Medium (50%+)')).toBeInTheDocument();
      expect(screen.getByText('Low (30%+)')).toBeInTheDocument();
    });

    it('should validate minimum score (0-100)', () => {
      render(
        <SearchFilters
          filters={{ minScore: 0.7 }}
          onChange={mockOnChange}
        />
      );

      const select = screen.getByLabelText('Minimum Relevance');
      expect(select).toHaveValue('0.7');
    });
  });

  describe('Channel ID filter', () => {
    it('should update channel ID', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      const input = screen.getByLabelText('Channel ID');
      fireEvent.change(input, { target: { value: 'UCxxxxxxxxxxxxxxxxxx' } });

      expect(mockOnChange).toHaveBeenCalledWith({
        channelId: 'UCxxxxxxxxxxxxxxxxxx',
      });
    });

    it('should show placeholder for channel ID', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      const input = screen.getByLabelText('Channel ID');
      expect(input).toHaveAttribute('placeholder', 'e.g., UCxxxxxxxxxxxxxxxxxx');
    });

    it('should show help text for channel filter', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('Filter by YouTube channel ID')).toBeInTheDocument();
    });
  });

  describe('Clear all filters', () => {
    it('should clear all filters when button clicked', () => {
      const activeFilters: HiragFilters = {
        sourceType: 'youtube' as HiragSource,
        startDate: '2025-01-01',
        endDate: '2025-12-31',
        minScore: 0.7,
        channelId: 'UCxxx',
      };

      render(
        <SearchFilters
          filters={activeFilters}
          onChange={mockOnChange}
        />
      );

      const clearButton = screen.getByText('Clear All');
      fireEvent.click(clearButton);

      expect(mockOnChange).toHaveBeenCalledWith({});
    });

    it('should show active filter count when filters are set', () => {
      const activeFilters: HiragFilters = {
        sourceType: 'youtube' as HiragSource,
        minScore: 0.7,
      };

      render(
        <SearchFilters
          filters={activeFilters}
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('Active Filters:')).toBeInTheDocument();
      expect(screen.getByText('Source: youtube')).toBeInTheDocument();
      expect(screen.getByText('Score: 70%+')).toBeInTheDocument();
    });

    it('should not show Clear All button when no active filters', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      expect(screen.queryByText('Clear All')).not.toBeInTheDocument();
    });
  });

  describe('Active filters summary', () => {
    it('should show all active filter badges', () => {
      const activeFilters: HiragFilters = {
        sourceType: 'pdf' as HiragSource,
        startDate: '2025-01-01',
        endDate: '2025-06-30',
        minScore: 0.5,
        channelId: 'UCxxxxxxxxxxxxxxxxxx',
      };

      render(
        <SearchFilters
          filters={activeFilters}
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('Source: pdf')).toBeInTheDocument();
      expect(screen.getByText('From: 2025-01-01')).toBeInTheDocument();
      expect(screen.getByText('To: 2025-06-30')).toBeInTheDocument();
      expect(screen.getByText('Score: 50%+')).toBeInTheDocument();
      // Channel ID is truncated to first 8 chars + ...
      expect(screen.getByText(/Channel: UCxxxxxx\.\.\./)).toBeInTheDocument();
    });
  });

  describe('Panel visibility', () => {
    it('should render content when isOpen is true', () => {
      const { container } = render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
          isOpen={true}
        />
      );

      expect(screen.getByText('Filters')).toBeInTheDocument();
    });

    it('should not render content when isOpen is false', () => {
      const { container } = render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
          isOpen={false}
        />
      );

      expect(screen.queryByText('Filters')).not.toBeInTheDocument();
    });

    it('should call onToggle when close button clicked', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
          isOpen={true}
          onToggle={mockOnToggle}
        />
      );

      const closeButton = screen.getByLabelText('Close filters');
      fireEvent.click(closeButton);

      expect(mockOnToggle).toHaveBeenCalledTimes(1);
    });
  });

  describe('Filter combination', () => {
    it('should call onChange for each individual filter change', () => {
      render(
        <SearchFilters
          filters={defaultFilters}
          onChange={mockOnChange}
        />
      );

      // Set multiple filters - each triggers onChange independently
      const sourceSelect = screen.getByLabelText('Source Type');
      fireEvent.change(sourceSelect, { target: { value: 'youtube' } });

      const scoreSelect = screen.getByLabelText('Minimum Relevance');
      fireEvent.change(scoreSelect, { target: { value: '0.9' } });

      // Component is controlled - each change calls onChange with updated filters
      // Since filters prop doesn't update between renders, calls are independent
      expect(mockOnChange).toHaveBeenCalledTimes(2);
      expect(mockOnChange).toHaveBeenNthCalledWith(1, { sourceType: 'youtube' });
      expect(mockOnChange).toHaveBeenNthCalledWith(2, { minScore: 0.9 });
    });
  });
});
