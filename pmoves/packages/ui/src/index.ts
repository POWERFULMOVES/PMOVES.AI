/**
 * @pmoves/ui — Shared Component Library
 *
 * Thread 8.4: Common UI components for PMOVES.AI frontend surfaces
 *
 * Components:
 * - HealthBadge: Service health status indicator
 * - AgentCard: Agent identity card with theme
 * - MetricChart: Real-time metric visualization
 * - SwarmPotential: Swarm potential gauge
 */

export { HealthBadge, type HealthBadgeProps } from './components/HealthBadge';
export { AgentCard, type AgentCardProps } from './components/AgentCard';
export { MetricChart, type MetricChartProps } from './components/MetricChart';
export { SwarmGauge, type SwarmGaugeProps } from './components/SwarmGauge';

// Utility exports
export { cn } from './lib/utils';
