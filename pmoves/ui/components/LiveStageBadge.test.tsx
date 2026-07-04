import { render, screen, waitFor } from '@testing-library/react';
import { LiveStageBadge } from './LiveStageBadge';

describe('LiveStageBadge', () => {
  afterEach(() => {
    delete document.documentElement.dataset.stage;
  });

  it('renders nothing when live={false}', () => {
    render(<LiveStageBadge live={false} />);
    expect(screen.queryByTestId('live-stage-badge')).toBeNull();
  });

  it('renders the LIVE pill with the signature mark when live={true}', () => {
    const { container } = render(<LiveStageBadge live={true} />);
    const badge = screen.getByTestId('live-stage-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent('LIVE');
    expect(container.querySelector('.pm-live-mark')).not.toBeNull();
  });

  it('derives live state from data-stage="live" on <html> when no live prop is given', async () => {
    document.documentElement.dataset.stage = 'live';
    render(<LiveStageBadge />);
    await waitFor(() => {
      expect(screen.getByTestId('live-stage-badge')).toBeInTheDocument();
    });
  });

  it('renders nothing when no live prop and stage is not live', () => {
    render(<LiveStageBadge />);
    expect(screen.queryByTestId('live-stage-badge')).toBeNull();
  });
});
