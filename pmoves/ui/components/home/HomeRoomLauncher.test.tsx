import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HomeRoomLauncher, type HomeRoomOption } from './HomeRoomLauncher';

jest.mock('next/link', () => {
  const MockLink = ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  );
  MockLink.displayName = 'MockLink';
  return MockLink;
});

const ROOMS: HomeRoomOption[] = [
  {
    roomId: '4090-field.room.control',
    displayName: '4090 Field Control Room',
    agentId: '4090-claude',
    alter: '4090-field',
    summary: 'Scout/control room for review and handoff.',
    defaultRoute: '/dashboard/notebook/runtime',
    accentColor: '#065F46',
    glyph: '◎',
    pinnedApps: [{ appId: 'notebook-workbench', route: '/notebook-workbench' }],
  },
  {
    roomId: '5090-voice.room.studio',
    displayName: '5090 Voice Studio',
    agentId: '5090-claude',
    alter: '5090-voice',
    summary: 'Voice-first room for media and audition workflows.',
    defaultRoute: '/dashboard/services',
    accentColor: '#B45309',
    glyph: '◉',
    pinnedApps: [{ appId: 'voice-lab', route: '/dashboard/services' }],
  },
];

describe('HomeRoomLauncher', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('launches the first room by default', () => {
    render(<HomeRoomLauncher rooms={ROOMS} />);

    const launchLink = screen.getByRole('link', { name: /launch 4090 field control room/i });
    expect(launchLink).toHaveAttribute('href', '/login?room_id=4090-field.room.control');
    expect(screen.getByText('/dashboard/notebook/runtime')).toBeInTheDocument();
  });

  it('updates the launch target and persists the selected room', async () => {
    const user = userEvent.setup();
    render(<HomeRoomLauncher rooms={ROOMS} />);

    await user.click(screen.getByRole('button', { name: /5090 voice studio/i }));

    expect(screen.getByRole('link', { name: /launch 5090 voice studio/i })).toHaveAttribute(
      'href',
      '/login?room_id=5090-voice.room.studio'
    );
    expect(window.localStorage.getItem('pmoves.home.selectedRoom')).toBe('5090-voice.room.studio');
  });
});
