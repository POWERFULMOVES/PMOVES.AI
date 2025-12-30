/* ═══════════════════════════════════════════════════════════════════════════
   Tokenism Simulation Panel

   Form interface for running token economy simulations.
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useState, FormEvent } from 'react';
import { getTokenismClient, ContractType, ScenarioType, SimulationResult } from '@/lib/tokenismClient';

interface SimulationPanelProps {
  onSimulationComplete?: (result: SimulationResult) => void;
}

const CONTRACT_TYPES: { value: ContractType; label: string; description: string }[] = [
  {
    value: 'GroToken',
    label: 'GroToken',
    description: 'Grocery loyalty token with cashback rewards',
  },
  {
    value: 'FoodUSD',
    label: 'FoodUSD',
    description: 'Stablecoin pegged to food basket index',
  },
  {
    value: 'GroupPurchase',
    label: 'GroupPurchase',
    description: 'Bulk purchasing cooperative token',
  },
  {
    value: 'GroVault',
    label: 'GroVault',
    description: 'Yield-bearing savings protocol',
  },
  {
    value: 'CoopGovernor',
    label: 'CoopGovernor',
    description: 'Democratic governance token',
  },
];

const SCENARIOS: { value: ScenarioType; label: string; description: string }[] = [
  {
    value: 'optimistic',
    label: 'Optimistic',
    description: 'High growth, low volatility, strong adoption',
  },
  {
    value: 'baseline',
    label: 'Baseline',
    description: 'Realistic market conditions',
  },
  {
    value: 'pessimistic',
    label: 'Pessimistic',
    description: 'Low growth, high volatility, weak adoption',
  },
  {
    value: 'stress_test',
    label: 'Stress Test',
    description: 'Extreme market conditions',
  },
  {
    value: 'custom',
    label: 'Custom',
    description: 'Define your own parameters',
  },
];

export function TokenismSimulationPanel({ onSimulationComplete }: SimulationPanelProps) {
  const [contractType, setContractType] = useState<ContractType>('GroToken');
  const [scenario, setScenario] = useState<ScenarioType>('baseline');
  const [participants, setParticipants] = useState(1000);
  const [weeks, setWeeks] = useState(52);
  const [initialPrice, setInitialPrice] = useState(1.0);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<SimulationResult | null>(null);

  const tokenism = getTokenismClient();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsRunning(true);
    setError(null);

    try {
      const result = await tokenism.runSimulation({
        contractType,
        scenario,
        participants,
        weeks,
        initialPrice,
      });

      setLastResult(result);
      onSimulationComplete?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Simulation Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Contract Type Selection */}
        <div>
          <label className="block text-xs font-mono uppercase text-gold-400 mb-2">
            Contract Type
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {CONTRACT_TYPES.map((ct) => (
              <button
                key={ct.value}
                type="button"
                onClick={() => setContractType(ct.value)}
                className={`
                  p-3 text-left border transition-all duration-200
                  ${contractType === ct.value
                    ? 'border-gold-500 bg-gold-500/20 text-gold-300'
                    : 'border-gray-700 bg-black/50 text-gray-400 hover:border-gold-500/50'
                  }
                `}
              >
                <div className="font-pixel text-sm">{ct.label}</div>
                <div className="text-xs opacity-70 mt-1">{ct.description}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Scenario Selection */}
        <div>
          <label className="block text-xs font-mono uppercase text-cyan-400 mb-2">
            Economic Scenario
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
            {SCENARIOS.map((sc) => (
              <button
                key={sc.value}
                type="button"
                onClick={() => setScenario(sc.value)}
                className={`
                  p-2 text-center border transition-all duration-200
                  ${scenario === sc.value
                    ? 'border-cyan-500 bg-cyan-500/20 text-cyan-300'
                    : 'border-gray-700 bg-black/50 text-gray-400 hover:border-cyan-500/50'
                  }
                `}
              >
                <div className="font-pixel text-xs">{sc.label}</div>
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-2">
            {SCENARIOS.find((s) => s.value === scenario)?.description}
          </p>
        </div>

        {/* Parameters Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Participants */}
          <div>
            <label htmlFor="participants" className="block text-xs font-mono uppercase text-gray-400 mb-1">
              Participants
            </label>
            <input
              id="participants"
              type="number"
              min={100}
              max={100000}
              step={100}
              value={participants}
              onChange={(e) => setParticipants(Number(e.target.value))}
              className="w-full px-3 py-2 bg-black/50 border border-gray-700 font-mono text-sm text-gold-400 focus:border-gold-500 focus:outline-none"
              disabled={isRunning}
            />
          </div>

          {/* Duration */}
          <div>
            <label htmlFor="weeks" className="block text-xs font-mono uppercase text-gray-400 mb-1">
              Duration (weeks)
            </label>
            <input
              id="weeks"
              type="number"
              min={4}
              max={520}
              step={4}
              value={weeks}
              onChange={(e) => setWeeks(Number(e.target.value))}
              className="w-full px-3 py-2 bg-black/50 border border-gray-700 font-mono text-sm text-cyan-400 focus:border-cyan-500 focus:outline-none"
              disabled={isRunning}
            />
          </div>

          {/* Initial Price */}
          <div>
            <label htmlFor="price" className="block text-xs font-mono uppercase text-gray-400 mb-1">
              Initial Price (USD)
            </label>
            <input
              id="price"
              type="number"
              min={0.01}
              max={1000}
              step={0.01}
              value={initialPrice}
              onChange={(e) => setInitialPrice(Number(e.target.value))}
              className="w-full px-3 py-2 bg-black/50 border border-gray-700 font-mono text-sm text-green-400 focus:border-green-500 focus:outline-none"
              disabled={isRunning}
            />
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="p-3 border border-red-500/50 bg-red-500/10 text-red-400 text-sm">
            <span className="font-pixel">ERROR:</span> {error}
          </div>
        )}

        {/* Submit Button */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={isRunning}
            className={`
              px-6 py-3 font-pixel text-sm uppercase tracking-wider border transition-all duration-200
              ${isRunning
                ? 'border-gray-700 text-gray-500 cursor-not-allowed'
                : 'border-gold-500 text-gold-400 bg-gold-500/10 hover:bg-gold-500/20'
              }
            `}
          >
            {isRunning ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-gold-500 border-t-transparent rounded-full animate-spin" />
                Simulating...
              </span>
            ) : (
              'Run Simulation'
            )}
          </button>

          {lastResult && (
            <span className="text-xs text-gray-500 font-mono">
              Last: {lastResult.simulationId.slice(0, 8)}
            </span>
          )}
        </div>
      </form>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-gray-800">
        <div className="text-center">
          <div className="text-xs text-gray-500 font-mono uppercase">Contract</div>
          <div className="font-pixel text-gold-400">{contractType}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500 font-mono uppercase">Scenario</div>
          <div className="font-pixel text-cyan-400">{scenario}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500 font-mono uppercase">Participants</div>
          <div className="font-pixel text-green-400">{participants.toLocaleString()}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500 font-mono uppercase">Duration</div>
          <div className="font-pixel text-violet-400">{weeks} weeks</div>
        </div>
      </div>
    </div>
  );
}

export default TokenismSimulationPanel;
