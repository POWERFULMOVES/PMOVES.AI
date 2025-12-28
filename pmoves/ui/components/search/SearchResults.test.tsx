/* ═══════════════════════════════════════════════════════════════════════════
   Search Results Component Tests
   Tests Hi-RAG search results with source attribution and actions
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent } from '@testing-library/react';
import { SearchResults } from './SearchResults';
import type { HiragResult, HiragSource } from '@/lib/api/hirag';

// Mock clipboard API
const mockWriteText = jest.fn();
const mockClipboard = {
  writeText: mockWriteText,
  readText: jest.fn(),
};

// Use defineProperty to properly mock the readonly clipboard property
Object.defineProperty(navigator, 'clipboard', {
  value: mockClipboard,
  writable: true,
  configurable: true,
});

describe('SearchResults', () => {
  const mockOnExport = jest.fn();
  const mockOnCopy = jest.fn();

  const mockResults: HiragResult[] = [
    {
      id: '1',
      content: 'This is a test result about machine learning basics.',
      score: 0.95,
      source: 'youtube' as HiragSource,
      metadata: {
        video_id: 'abc123',
        title: 'Machine Learning 101',
        channel: 'Tech Channel',
        timestamp: '10:25',
        url: 'https://youtube.com/watch?v=abc123',
      },
    },
    {
      id: '2',
      content: 'Another result about deep learning.',
      score: 0.75,
      source: 'notebook' as HiragSource,
      metadata: {
        title: 'Deep Learning Notes',
        url: 'https://notebook.local/notes/123',
      },
    },
    {
      id: '3',
      content: 'Low relevance result.',
      score: 0.45,
      source: 'pdf' as HiragSource,
      metadata: {
        title: 'Research Paper',
        url: 'https://example.com/paper.pdf',
      },
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    mockWriteText.mockResolvedValue(undefined);
  });

  describe('Result display', () => {
    it('should render results with correct source badges', () => {
      render(<SearchResults results={mockResults} />);

      expect(screen.getByText('Machine Learning 101')).toBeInTheDocument();
      expect(screen.getByText('Deep Learning Notes')).toBeInTheDocument();
      expect(screen.getByText('Research Paper')).toBeInTheDocument();
    });

    it('should show source icons', () => {
      render(<SearchResults results={mockResults} />);

      expect(screen.getByText('📺')).toBeInTheDocument(); // YouTube
      expect(screen.getByText('📓')).toBeInTheDocument(); // Notebook
      expect(screen.getByText('📄')).toBeInTheDocument(); // PDF
    });

    it('should color-code scores: green (>90%)', () => {
      render(<SearchResults results={[mockResults[0]]} />);

      const score = screen.getByText('95%');
      expect(score.className).toContain('text-green-600');
    });

    it('should color-code scores: lime (70-90%)', () => {
      render(<SearchResults results={[mockResults[1]]} />);

      const score = screen.getByText('75%');
      expect(score.className).toContain('text-lime-600');
    });

    it('should color-code scores: yellow (<50%)', () => {
      render(<SearchResults results={[mockResults[2]]} />);

      const score = screen.getByText('45%');
      expect(score.className).toContain('text-yellow-600');
    });

    it('should show channel name for YouTube results', () => {
      render(<SearchResults results={mockResults} />);

      expect(screen.getByText('from Tech Channel')).toBeInTheDocument();
    });

    it('should show empty state when no results', () => {
      render(<SearchResults results={[]} />);

      expect(screen.getByText('No results found')).toBeInTheDocument();
      expect(screen.getByText(/Try adjusting your search query/)).toBeInTheDocument();
    });
  });

  describe('Expand/Collapse', () => {
    it('should expand/collapse on click', () => {
      render(<SearchResults results={mockResults} verbose />);

      const firstResultContent = screen.getByText(/This is a test result/);
      expect(firstResultContent.className).toContain('line-clamp-2');

      // Click expand button
      const expandButtons = screen.getAllByLabelText('Expand');
      fireEvent.click(expandButtons[0]);

      expect(firstResultContent.className).not.toContain('line-clamp-2');
    });

    it('should rotate expand icon when expanded', () => {
      render(<SearchResults results={mockResults} verbose />);

      const expandButton = screen.getAllByLabelText('Expand')[0];
      expect(expandButton.querySelector('svg')).not.toHaveClass('rotate-180');

      fireEvent.click(expandButton);

      expect(expandButton.querySelector('svg')).toHaveClass('rotate-180');
    });
  });

  describe('Clipboard operations', () => {
    it('should copy content to clipboard', async () => {
      render(<SearchResults results={mockResults} onCopy={mockOnCopy} />);

      const copyButtons = screen.getAllByLabelText('Copy to clipboard');
      fireEvent.click(copyButtons[0]);

      // Wait for async clipboard operation
      await mockWriteText.mock.results[0]?.value;

      expect(mockWriteText).toHaveBeenCalledWith(
        'This is a test result about machine learning basics.'
      );
      expect(mockOnCopy).toHaveBeenCalledWith(
        'This is a test result about machine learning basics.'
      );
    });

    it('should handle clipboard API errors silently', async () => {
      mockWriteText.mockRejectedValueOnce(new Error('Clipboard unavailable'));

      render(<SearchResults results={mockResults} onCopy={mockOnCopy} />);

      const copyButtons = screen.getAllByLabelText('Copy to clipboard');
      expect(() => fireEvent.click(copyButtons[0])).not.toThrow();
    });

    it('should not show copy button when onCopy not provided', () => {
      render(<SearchResults results={mockResults} />);

      expect(screen.queryByLabelText('Copy to clipboard')).not.toBeInTheDocument();
    });
  });

  describe('Export functionality', () => {
    it('should call onExport with result when export clicked', () => {
      render(<SearchResults results={mockResults} onExport={mockOnExport} />);

      const exportButtons = screen.getAllByLabelText('Export to notebook');
      fireEvent.click(exportButtons[0]);

      expect(mockOnExport).toHaveBeenCalledWith(mockResults[0]);
    });

    it('should not show export button when onExport not provided', () => {
      render(<SearchResults results={mockResults} />);

      expect(screen.queryByLabelText('Export to notebook')).not.toBeInTheDocument();
    });
  });

  describe('Source types', () => {
    it('should render YouTube icon for youtube source', () => {
      render(<SearchResults results={[mockResults[0]]} />);

      const badge = screen.getByText('youtube').parentElement;
      expect(badge?.textContent).toContain('📺');
      expect(badge?.textContent).toContain('youtube');
    });

    it('should render Notebook icon for notebook source', () => {
      render(<SearchResults results={[mockResults[1]]} />);

      const badge = screen.getByText('notebook').parentElement;
      expect(badge?.textContent).toContain('📓');
      expect(badge?.textContent).toContain('notebook');
    });

    it('should render PDF icon for pdf source', () => {
      render(<SearchResults results={[mockResults[2]]} />);

      const badge = screen.getByText('pdf').parentElement;
      expect(badge?.textContent).toContain('📄');
      expect(badge?.textContent).toContain('pdf');
    });

    it('should render unknown icon for unknown source', () => {
      const unknownResult: HiragResult = {
        id: '4',
        content: 'Unknown source',
        score: 0.5,
        source: 'unknown' as HiragSource,
        metadata: {},
      };

      render(<SearchResults results={[unknownResult]} />);

      expect(screen.getByText('❓')).toBeInTheDocument();
    });
  });

  describe('Results summary', () => {
    it('should show total count', () => {
      const { container } = render(<SearchResults results={mockResults} total={100} />);

      // Text is split across elements, query the container
      expect(container.textContent).toContain('Found 100 results');
    });

    it('should use results length when total not provided', () => {
      const { container } = render(<SearchResults results={mockResults} />);

      expect(container.textContent).toContain('Found 3 results');
    });

    it('should show query time when provided', () => {
      render(<SearchResults results={mockResults} queryTime={1234} />);

      expect(screen.getByText(/1234ms/)).toBeInTheDocument();
    });
  });

  describe('Verbose details', () => {
    it('should show additional metadata when verbose is true', () => {
      render(<SearchResults results={mockResults} verbose={true} />);

      const expandButton = screen.getAllByLabelText('Expand')[0];
      fireEvent.click(expandButton);

      // Verbose metadata is split across elements
      expect(screen.getByText('Video ID:')).toBeInTheDocument();
      expect(screen.getByText('abc123')).toBeInTheDocument();
      expect(screen.getByText('Timestamp:')).toBeInTheDocument();
      // 10:25 appears in both footer and verbose section
      expect(screen.getAllByText('10:25').length).toBeGreaterThan(0);
    });

    it('should show clickable URL when verbose', () => {
      render(<SearchResults results={mockResults} verbose={true} />);

      const expandButton = screen.getAllByLabelText('Expand')[0];
      fireEvent.click(expandButton);

      const link = screen.getByText('https://youtube.com/watch?v=abc123');
      expect(link).toBeInTheDocument();
      expect(link.closest('a')).toHaveAttribute('target', '_blank');
      expect(link.closest('a')).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });
});
