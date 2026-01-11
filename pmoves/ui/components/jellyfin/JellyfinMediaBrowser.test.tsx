/* ═══════════════════════════════════════════════════════════════════════════
   Jellyfin Media Browser Component Tests
   Tests media browsing with link management and responsive grid
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent } from '@testing-library/react';
import { JellyfinMediaBrowser } from './JellyfinMediaBrowser';
import type { JellyfinItem } from '@/lib/api/jellyfin';

const mockItems: JellyfinItem[] = [
  {
    id: '1',
    name: 'Test Movie',
    type: 'Movie',
    productionYear: 2024,
    imageUrl: 'http://example.com/image.jpg',
  },
  {
    id: '2',
    name: 'Test Series',
    type: 'Series',
    seriesName: 'Test Series',
    seasonNumber: 1,
    episodeNumber: '5',
  },
  {
    id: '3',
    name: 'Test Episode',
    type: 'Episode',
    seriesName: 'Another Series',
    seasonNumber: 2,
    episodeNumber: '3',
    youtubeId: 'abc123',
  },
  {
    id: '4',
    name: 'Season Test',
    type: 'Season',
    seriesName: 'Season Show',
    seasonNumber: 1,
  },
];

describe('JellyfinMediaBrowser', () => {
  const mockOnLink = jest.fn();
  const mockOnPlaybackUrl = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Responsive grid', () => {
    it('should render items in responsive grid', () => {
      const { container } = render(
        <JellyfinMediaBrowser items={mockItems} onLink={mockOnLink} onPlaybackUrl={mockOnPlaybackUrl} />
      );

      const grid = container.querySelector('.grid');
      expect(grid).toBeInTheDocument();
      expect(grid).toHaveClass('grid-cols-1');
      expect(grid).toHaveClass('md:grid-cols-2');
      expect(grid).toHaveClass('lg:grid-cols-3');
    });

    it('should render all items', () => {
      const { container } = render(
        <JellyfinMediaBrowser items={mockItems} onLink={mockOnLink} onPlaybackUrl={mockOnPlaybackUrl} />
      );

      expect(screen.getByText('Test Movie')).toBeInTheDocument();
      // Use container for items that may have text split across elements
      expect(container.textContent).toContain('Test Series');
      expect(container.textContent).toContain('Test Episode');
      expect(container.textContent).toContain('Season Test');
    });
  });

  describe('Media type badges', () => {
    it('should display correct badge for Movie type', () => {
      render(<JellyfinMediaBrowser items={[mockItems[0]]} />);

      const badge = screen.getByText('Movie');
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain('bg-purple-100');
      expect(badge.className).toContain('text-purple-800');
    });

    it('should display correct badge for Series type', () => {
      render(<JellyfinMediaBrowser items={[mockItems[1]]} />);

      const badge = screen.getByText('Series');
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain('bg-blue-100');
      expect(badge.className).toContain('text-blue-800');
    });

    it('should display correct badge for Episode type', () => {
      render(<JellyfinMediaBrowser items={[mockItems[2]]} />);

      const badge = screen.getByText('Episode');
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain('bg-green-100');
      expect(badge.className).toContain('text-green-800');
    });

    it('should display correct badge for Season type', () => {
      render(<JellyfinMediaBrowser items={[mockItems[3]]} />);

      const badge = screen.getByText('Season');
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain('bg-amber-100');
      expect(badge.className).toContain('text-amber-800');
    });

    it('should display generic badge for unknown type', () => {
      const unknownItem: JellyfinItem = {
        id: '5',
        name: 'Unknown Type',
        type: 'Unknown' as any,
      };

      render(<JellyfinMediaBrowser items={[unknownItem]} />);

      const badge = screen.getByText('Unknown');
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain('bg-gray-100');
      expect(badge.className).toContain('text-gray-800');
    });
  });

  describe('Image handling', () => {
    it('should show image when imageUrl is provided', () => {
      render(<JellyfinMediaBrowser items={[mockItems[0]]} />);

      const image = screen.getByAltText('Test Movie');
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', 'http://example.com/image.jpg');
    });

    it('should show placeholder when imageUrl is not provided', () => {
      const { container } = render(<JellyfinMediaBrowser items={[mockItems[1]]} />);

      const image = screen.queryByAltText('Test Series');
      expect(image).not.toBeInTheDocument();

      // Should show placeholder SVG - query directly from container
      const placeholder = container.querySelector('svg');
      expect(placeholder).toBeInTheDocument();
    });
  });

  describe('Item selection', () => {
    it('should highlight selected item with ring', () => {
      const { container } = render(
        <JellyfinMediaBrowser items={mockItems} onLink={mockOnLink} onPlaybackUrl={mockOnPlaybackUrl} />
      );

      // Click first item to select it - find the card div by its class
      const firstCard = container.querySelector('.rounded.border.border-neutral-200');
      fireEvent.click(firstCard!);

      // Should have ring-2 ring-blue-500
      expect(container.querySelector('.ring-2.ring-blue-500')).toBeInTheDocument();
    });

    it('should show selected item details panel', () => {
      const { container } = render(
        <JellyfinMediaBrowser items={mockItems} onLink={mockOnLink} onPlaybackUrl={mockOnPlaybackUrl} />
      );

      // Click an item - find card by class and click it
      const card = container.querySelector('.rounded.border.border-neutral-200');
      fireEvent.click(card!);

      // Details panel should appear - use container for split text
      expect(container.textContent).toContain('Test Movie');
      expect(container.textContent).toContain('Movie • 1');
      expect(container.textContent).toContain('Year: 2024');
    });

    it('should close details panel when close button clicked', () => {
      const { container } = render(
        <JellyfinMediaBrowser items={mockItems} onLink={mockOnLink} onPlaybackUrl={mockOnPlaybackUrl} />
      );

      // Select an item - find card by class
      const card = container.querySelector('.rounded.border.border-neutral-200');
      fireEvent.click(card!);

      // Click close button
      const closeButton = screen.getByLabelText('Close details');
      fireEvent.click(closeButton);

      // Details panel should be gone (but item name still in grid)
      expect(container.textContent).not.toContain('Year: 2024');
    });
  });

  describe('Link actions', () => {
    it('should call onLink when Link Video button clicked', () => {
      render(<JellyfinMediaBrowser items={[mockItems[0]]} onLink={mockOnLink} />);

      const linkButton = screen.getByText('Link Video');
      fireEvent.click(linkButton);

      expect(mockOnLink).toHaveBeenCalledWith(mockItems[0]);
    });

    it('should not show Link Video button when item already has youtubeId', () => {
      render(<JellyfinMediaBrowser items={[mockItems[2]]} onLink={mockOnLink} />);

      expect(screen.queryByText('Link Video')).not.toBeInTheDocument();
    });

    it('should show linked status when item has youtubeId', () => {
      render(<JellyfinMediaBrowser items={[mockItems[2]]} />);

      expect(screen.getByText(/Linked to abc123/)).toBeInTheDocument();
    });

    it('should call onPlaybackUrl when Playback URL button clicked', () => {
      render(<JellyfinMediaBrowser items={[mockItems[0]]} onPlaybackUrl={mockOnPlaybackUrl} />);

      const playbackButton = screen.getByText('Playback URL');
      fireEvent.click(playbackButton);

      expect(mockOnPlaybackUrl).toHaveBeenCalledWith(mockItems[0]);
    });
  });

  describe('Empty state', () => {
    it('should show no results message when items array is empty', () => {
      render(<JellyfinMediaBrowser items={[]} />);

      expect(screen.getByText('No items found')).toBeInTheDocument();
      expect(screen.getByText('Try a different search term or sync your Jellyfin library.')).toBeInTheDocument();
      expect(screen.getByText('🎬')).toBeInTheDocument();
    });
  });

  describe('Loading state', () => {
    it('should show loading indicator when loading is true', () => {
      const { container } = render(<JellyfinMediaBrowser items={[]} loading={true} />);

      expect(screen.getByText('Searching library...')).toBeInTheDocument();
      // The animate-spin class is on the svg element
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Error state', () => {
    it('should show error message when error prop provided', () => {
      render(<JellyfinMediaBrowser items={[]} error="Connection failed" />);

      expect(screen.getByText('Connection failed')).toBeInTheDocument();
      const errorContainer = screen.getByText('Connection failed').closest('div');
      expect(errorContainer).toHaveClass('border-red-300');
      expect(errorContainer).toHaveClass('bg-red-50');
    });
  });

  describe('Results count', () => {
    it('should show results count', () => {
      render(
        <JellyfinMediaBrowser items={mockItems} onLink={mockOnLink} onPlaybackUrl={mockOnPlaybackUrl} />
      );

      expect(screen.getByText('Found 4 items')).toBeInTheDocument();
    });

    it('should show singular "item" when only one result', () => {
      render(<JellyfinMediaBrowser items={[mockItems[0]]} />);

      expect(screen.getByText('Found 1 item')).toBeInTheDocument();
    });
  });

  describe('Series/Episode metadata', () => {
    it('should show series name for episodes', () => {
      render(<JellyfinMediaBrowser items={[mockItems[2]]} />);

      expect(screen.getByText('Another Series')).toBeInTheDocument();
    });

    it('should show season and episode numbers', () => {
      render(<JellyfinMediaBrowser items={[mockItems[2]]} />);

      expect(screen.getByText('S2')).toBeInTheDocument();
      expect(screen.getByText('E3')).toBeInTheDocument();
    });
  });
});
