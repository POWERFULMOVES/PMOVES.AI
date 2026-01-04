/* ═══════════════════════════════════════════════════════════════════════════
   Tests: SystemStatsBar, TierNavigation (basic rendering tests)
   ═══════════════════════════════════════════════════════════════════════════ */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SystemStatsBar } from '../components/hub/SystemStatsBar';
import { TierNavigation } from '../components/services/TierNavigation';
import type { ServiceCategory } from '../lib/serviceCatalog';

function createMockStats(overrides: Partial<{
  totalServices: number;
  healthyCount: number;
  unhealthyCount: number;
  unknownCount: number;
  percentage: number;
}> = {}) {
  return {
    totalServices: 94,
    healthyCount: 75,
    unhealthyCount: 5,
    unknownCount: 14,
    percentage: 80,
    ...overrides,
  };
}

describe('SystemStatsBar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('displays system health percentage', () => {
    const stats = createMockStats({ percentage: 85 });
    render(<SystemStatsBar {...stats} isChecking={false} />);

    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('shows correct color for healthy system (80%+)', () => {
    const stats = createMockStats({ percentage: 85 });
    const { container } = render(<SystemStatsBar {...stats} isChecking={false} />);

    expect(container.querySelector('.text-cata-forest')).toBeInTheDocument();
  });

  it('shows correct color for warning system (50-79%)', () => {
    const stats = createMockStats({ percentage: 65 });
    const { container } = render(<SystemStatsBar {...stats} isChecking={false} />);

    expect(container.querySelector('.text-cata-gold')).toBeInTheDocument();
  });

  it('shows correct color for unhealthy system (<50%)', () => {
    const stats = createMockStats({ percentage: 35 });
    const { container } = render(<SystemStatsBar {...stats} isChecking={false} />);

    expect(container.querySelector('.text-cata-ember')).toBeInTheDocument();
  });

  it('shows checking state when polling', () => {
    const stats = createMockStats();
    render(<SystemStatsBar {...stats} isChecking={true} />);

    expect(screen.getByText('Checking...')).toBeInTheDocument();
  });

  it('displays service breakdown counts', () => {
    const stats = createMockStats();
    render(<SystemStatsBar {...stats} isChecking={false} />);

    // Use more specific patterns to avoid ambiguous matches (e.g., "5" vs "75")
    expect(screen.getByText(/75 healthy/)).toBeInTheDocument();
    expect(screen.getByText(/5 down/)).toBeInTheDocument();
    expect(screen.getByText(/14 unknown/)).toBeInTheDocument();
    expect(screen.getByText(/of 94 services/)).toBeInTheDocument();
  });

  it('calls refresh when refresh button clicked', () => {
    const onRefresh = jest.fn();
    const stats = createMockStats();
    render(<SystemStatsBar {...stats} isChecking={false} onRefresh={onRefresh} />);

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    fireEvent.click(refreshButton);

    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('disables refresh button while checking', () => {
    const onRefresh = jest.fn();
    const stats = createMockStats();
    render(<SystemStatsBar {...stats} isChecking={true} onRefresh={onRefresh} />);

    const refreshButton = screen.getByRole('button', { name: /refreshing/i });
    expect(refreshButton).toBeDisabled();
  });
});

describe('TierNavigation', () => {
  it('renders all category buttons', () => {
    const activeTier: ServiceCategory | 'all' = 'all';
    const onTierChange = jest.fn();

    render(
      <TierNavigation
        activeTier={activeTier}
        onTierChange={onTierChange}
      />
    );

    expect(screen.getByRole('button', { name: /all services/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /observability/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /database/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /workers/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /agents/i })).toBeInTheDocument();
  });

  it('highlights active tier with ember color for workers', () => {
    const activeTier: ServiceCategory | 'all' = 'workers';
    const onTierChange = jest.fn();

    render(
      <TierNavigation
        activeTier={activeTier}
        onTierChange={onTierChange}
      />
    );

    const workersButton = screen.getByRole('button', { name: /workers/i });
    // Workers tier uses ember color (not forest)
    expect(workersButton.className).toContain('bg-cata-ember');
  });

  it('highlights active tier with cyan color for all', () => {
    const activeTier: ServiceCategory | 'all' = 'all';
    const onTierChange = jest.fn();

    render(
      <TierNavigation
        activeTier={activeTier}
        onTierChange={onTierChange}
      />
    );

    const allButton = screen.getByRole('button', { name: /all services/i });
    expect(allButton.className).toContain('bg-cata-cyan');
  });

  it('calls onTierChange when category clicked', () => {
    const activeTier: ServiceCategory | 'all' = 'all';
    const onTierChange = jest.fn();

    render(
      <TierNavigation
        activeTier={activeTier}
        onTierChange={onTierChange}
      />
    );

    const databaseButton = screen.getByRole('button', { name: /database/i });
    fireEvent.click(databaseButton);

    expect(onTierChange).toHaveBeenCalledWith('database');
  });

  it('displays service count only for active tier', () => {
    const activeTier: ServiceCategory | 'all' = 'workers';
    const onTierChange = jest.fn();
    const tierStats = [
      { tier: 'workers' as ServiceCategory, total: 15, healthy: 12, percentage: 80 },
      { tier: 'agents' as ServiceCategory, total: 8, healthy: 7, percentage: 88 },
    ];

    render(
      <TierNavigation
        activeTier={activeTier}
        onTierChange={onTierChange}
        tierStats={tierStats}
      />
    );

    // Health text shows as "12/15" when active (healthy/total)
    expect(screen.getByText('12/15')).toBeInTheDocument();
    // Agents is not active, so its count shouldn't be displayed
    expect(screen.queryByText('7/8')).not.toBeInTheDocument();
  });
});
