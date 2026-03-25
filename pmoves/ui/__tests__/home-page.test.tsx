import { render, screen } from '@testing-library/react';
import HomePage from '@/app/page';

// Mock Next.js Link component to avoid router dependency
jest.mock('next/link', () => {
  const MockLink = ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  );
  MockLink.displayName = 'MockLink';
  return MockLink;
});

// Mock SystemHubSection to isolate home page rendering
jest.mock('@/components/hub/SystemHubSection', () => ({
  SystemHubSection: () => <div data-testid="system-hub-section">Hub</div>,
}));

describe('HomePage', () => {
  it('renders the main heading', () => {
    render(<HomePage />);
    expect(screen.getByText('POWERFUL')).toBeInTheDocument();
    expect(screen.getByText('MOVES')).toBeInTheDocument();
  });

  it('provides navigation to the ingestion dashboard', () => {
    render(<HomePage />);
    const link = screen.getByRole('link', { name: /launch console/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', expect.stringContaining('/login'));
  });

  it('renders pipeline steps', () => {
    render(<HomePage />);
    expect(screen.getByText('Create')).toBeInTheDocument();
    expect(screen.getByText('Webhook')).toBeInTheDocument();
    expect(screen.getByText('Approve')).toBeInTheDocument();
    expect(screen.getByText('Publish')).toBeInTheDocument();
  });

  it('renders agent personas', () => {
    render(<HomePage />);
    expect(screen.getByText('Archon')).toBeInTheDocument();
    expect(screen.getByText('Catalyst')).toBeInTheDocument();
    expect(screen.getByText('Ledger')).toBeInTheDocument();
  });
});
