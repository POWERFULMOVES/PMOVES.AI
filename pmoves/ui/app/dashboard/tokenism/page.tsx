/* ═══════════════════════════════════════════════════════════════════════════
   Tokenism Dashboard Page

   Token economy simulation with business model validation
   Powered by EVO Swarm Intelligence
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useState } from 'react';
import { SERVICE_CATALOG } from '@/lib/serviceCatalog';
import DashboardShell from '@/components/DashboardShell';
import DashboardHeader from '@/components/DashboardHeader';
import ServiceCard from '@/components/ServiceCard';
import TokenismSimulationPanel from '@/components/tokenism/SimulationPanel';
import TokenismResultsPanel from '@/components/tokenism/ResultsPanel';
import TokenismGeometricView from '@/components/tokenism/GeometricView';
import { SimulationResult } from '@/lib/tokenismClient';

export const metadata = {
  title: 'Tokenism | PMOVES',
  description: 'Token economy simulation with business model validation powered by EVO swarm intelligence',
};

export default function TokenismPage() {
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);

  const tokenismService = SERVICE_CATALOG.find(s => s.slug === 'tokenism');
  const tokenismUIService = SERVICE_CATALOG.find(s => s.slug === 'tokenism-ui');

  return (
    <DashboardShell active="tokenism">
      <DashboardHeader
        title="Tokenism"
        subtitle="Token economy simulation with business model validation"
        active="tokenism"
      />

      <div className="space-y-6 p-6">
        {/* Service Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tokenismService && <ServiceCard service={tokenismService} />}
          {tokenismUIService && <ServiceCard service={tokenismUIService} />}
        </div>

        {/* Simulation Interface */}
        <section className="border-2 border-gold-500/30 bg-black/50 p-4">
          <h2 className="text-xl font-pixel text-gold-400 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 bg-gold-400 animate-pulse" />
            Simulation Console
          </h2>
          <TokenismSimulationPanel onSimulationComplete={setSimulationResult} />
        </section>

        {/* Results Dashboard */}
        <section className="border-2 border-gold-500/30 bg-black/50 p-4">
          <h2 className="text-xl font-pixel text-gold-400 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 bg-green-400 animate-pulse" />
            Results Analysis
          </h2>
          <TokenismResultsPanel result={simulationResult} />
        </section>

        {/* Geometric Intelligence View */}
        <section className="border-2 border-violet-500/30 bg-black/50 p-4">
          <h2 className="text-xl font-pixel text-violet-400 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 bg-violet-400 animate-pulse" />
            CHIT Geometric Visualization
          </h2>
          <p className="text-sm text-gray-400 mb-4">
            Hyperbolic geometry representation of wealth distribution using Poincaré disk model
          </p>
          <TokenismGeometricView result={simulationResult} />
        </section>

        {/* Capabilities Info */}
        <section className="border-2 border-amber-500/30 bg-black/50 p-4">
          <h2 className="text-xl font-pixel text-amber-400 mb-4">Simulation Capabilities</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <CapabilityCard
              title="5 Contract Types"
              description="GroToken, FoodUSD, GroupPurchase, GroVault, CoopGovernor"
              color="gold"
            />
            <CapabilityCard
              title="Scenarios"
              description="Optimistic, Baseline, Pessimistic, Stress Test, Custom"
              color="cyan"
            />
            <CapabilityCard
              title="EVO Swarm"
              description="Evolutionary optimization for parameter calibration"
              color="green"
            />
            <CapabilityCard
              title="Risk Analysis"
              description="Gini coefficient, poverty rate, systemic risk scoring"
              color="red"
            />
            <CapabilityCard
              title="CHIT Geometry"
              description="Hyperbolic wealth visualization via Geometry Bus"
              color="violet"
            />
            <CapabilityCard
              title="NATS Integration"
              description="Publishes to tokenism.* subjects for real-time monitoring"
              color="blue"
            />
          </div>
        </section>

        {/* API Documentation */}
        <section className="border-2 border-gray-700/50 bg-black/30 p-4">
          <h2 className="text-xl font-pixel text-gray-300 mb-4">API Endpoints</h2>
          <div className="font-mono text-sm space-y-2">
            <ApiEndpoint
              method="POST"
              endpoint="/api/v1/simulate"
              description="Run a token economy simulation"
            />
            <ApiEndpoint
              method="GET"
              endpoint="/api/v1/scenarios"
              description="List available simulation scenarios"
            />
            <ApiEndpoint
              method="GET"
              endpoint="/api/v1/contracts"
              description="List available contract types"
            />
            <ApiEndpoint
              method="GET"
              endpoint="/metrics"
              description="Prometheus metrics"
            />
          </div>
        </section>
      </div>
    </DashboardShell>
  );
}

// ============================================================================
// Components
// ============================================================================

interface CapabilityCardProps {
  title: string;
  description: string;
  color: string;
}

function CapabilityCard({ title, description, color }: CapabilityCardProps) {
  const colorClasses = {
    gold: 'border-gold-500/50 text-gold-400',
    cyan: 'border-cyan-500/50 text-cyan-400',
    green: 'border-green-500/50 text-green-400',
    red: 'border-red-500/50 text-red-400',
    violet: 'border-violet-500/50 text-violet-400',
    blue: 'border-blue-500/50 text-blue-400',
  };

  const classes = colorClasses[color as keyof typeof colorClasses] || colorClasses.gold;

  return (
    <div className={`border ${classes} p-4 bg-black/30`}>
      <h3 className="font-pixel text-lg mb-2">{title}</h3>
      <p className="text-sm text-gray-400">{description}</p>
    </div>
  );
}

interface ApiEndpointProps {
  method: string;
  endpoint: string;
  description: string;
}

function ApiEndpoint({ method, endpoint, description }: ApiEndpointProps) {
  const methodColors = {
    GET: 'text-green-400',
    POST: 'text-blue-400',
    PUT: 'text-yellow-400',
    DELETE: 'text-red-400',
  };

  return (
    <div className="flex items-center gap-4 p-2 bg-black/50 rounded">
      <span className={`font-bold ${methodColors[method as keyof typeof methodColors] || 'text-gray-400'}`}>
        {method}
      </span>
      <span className="text-gray-300">{endpoint}</span>
      <span className="text-gray-500 text-sm flex-1">{description}</span>
    </div>
  );
}
