/**
 * Tokenism Simulator Client
 *
 * Provides HTTP interface to the Tokenism token economy simulation service.
 * Supports running simulations, retrieving scenarios, and accessing CGP geometry packets.
 *
 * @see .claude/context/tokenism.md for API reference
 *
 * @example
 * ```typescript
 * const tokenism = new TokenismClient();
 *
 * // Run a simulation
 * const result = await tokenism.runSimulation({
 *   contractType: 'GroToken',
 *   scenario: 'baseline',
 *   participants: 1000,
 *   weeks: 52,
 * });
 *
 * // Get geometric visualization
 * const cgp = await tokenism.getGeometry(result.simulationId);
 * ```
 */

/**
 * Convert snake_case keys to camelCase recursively.
 * The Tokenism API returns snake_case, but TypeScript interfaces use camelCase.
 */
function toCamelCase<T>(obj: unknown): T {
  if (obj === null || typeof obj !== 'object') {
    return obj as T;
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => toCamelCase(item)) as T;
  }

  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    // Convert snake_case to camelCase
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    result[camelKey] = toCamelCase(value);
  }
  return result as T;
}

export type ContractType =
  | 'GroToken'
  | 'FoodUSD'
  | 'GroupPurchase'
  | 'GroVault'
  | 'CoopGovernor';

export type ScenarioType =
  | 'optimistic'
  | 'baseline'
  | 'pessimistic'
  | 'stress_test'
  | 'custom';

export interface SimulationParameters {
  /** Contract type to simulate */
  contractType: ContractType;
  /** Economic scenario */
  scenario: ScenarioType;
  /** Number of participants */
  participants: number;
  /** Simulation duration in weeks */
  weeks: number;
  /** Initial token price (USD) */
  initialPrice?: number;
  /** Initial circulating supply */
  initialSupply?: number;
  /** Weekly transaction volume per participant */
  transactionVolume?: number;
  /** Custom parameters for scenario tweaking */
  customParams?: Record<string, number>;
}

export interface WeeklyMetrics {
  weekNumber: number;
  avgWealth: number;
  medianWealth: number;
  giniCoefficient: number;
  povertyRate: number;
  totalTransactions: number;
  totalVolume: number;
  activeParticipants: number;
  circulatingSupply: number;
}

export interface SimulationResult {
  simulationId: string;
  scenario: ScenarioType;
  contractType: ContractType;
  parameters: SimulationParameters;
  finalAvgWealth: number;
  finalGini: number;
  systemicRiskScore: number;
  weeklyMetrics: WeeklyMetrics[];
  createdAt: string;
  completedAt?: string;
}

export interface CGPGeometry {
  dimension: number;
  manifold: 'hyperbolic' | 'euclidean' | 'spherical';
  coordinates: 'poincare_disk' | 'cartesian' | 'spherical';
  points: number[][];
  edges: number[][];
  bounds: Record<string, number>;
  statistics?: Record<string, number>;
}

export interface CGPPacket {
  cgpVersion: string;
  packetType: string;
  simulationId: string;
  geometry: CGPGeometry;
  metadata: Record<string, unknown>;
}

export interface ScenarioInfo {
  name: ScenarioType;
  description: string;
  defaultParams: Partial<SimulationParameters>;
}

export interface ContractInfo {
  name: ContractType;
  description: string;
  features: string[];
}

/**
 * Client for Tokenism token economy simulation service.
 *
 * Provides interfaces for running simulations, retrieving results,
 * and accessing CHIT geometry packets for wealth visualization.
 */
import { logError } from './errorUtils';
import { ErrorIds } from './constants/errorIds';

export class TokenismClient {
  private readonly httpUrl: string;

  constructor(options?: { httpUrl?: string }) {
    // Server-side: use TOKENISM_URL (Docker internal hostname)
    // Client-side: use NEXT_PUBLIC_TOKENISM_URL (user-accessible URL)
    // Fallback: localhost for development
    this.httpUrl = options?.httpUrl
      || (typeof window === 'undefined' ? process.env.TOKENISM_URL : undefined)
      || process.env.NEXT_PUBLIC_TOKENISM_URL
      || 'http://localhost:8103';
  }

  /**
   * Run a token economy simulation.
   *
   * @param parameters - Simulation parameters
   * @returns Simulation result with weekly metrics
   * @throws {Error} If simulation request fails
   */
  async runSimulation(parameters: SimulationParameters): Promise<SimulationResult> {
    const response = await fetch(`${this.httpUrl}/api/v1/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parameters),
    });

    if (!response.ok) {
      const errorText = await response.text();
      const { contractType, scenario } = parameters;

      // Provide actionable error messages based on status code
      let userMessage = 'Simulation failed.';
      if (response.status === 404) {
        userMessage = 'Tokenism service not found. Ensure the backend is running.';
      } else if (response.status === 500 || response.status === 502) {
        userMessage = 'Tokenism service error. Check server logs.';
      } else if (response.status === 400) {
        userMessage = `Invalid parameters for ${contractType} / ${scenario}.`;
      }

      throw new Error(`${userMessage} (HTTP ${response.status}): ${errorText}`);
    }

    const data = await response.json();
    return toCamelCase<SimulationResult>(data);
  }

  /**
   * Get available simulation scenarios.
   *
   * @returns List of scenario configurations
   */
  async getScenarios(): Promise<ScenarioInfo[]> {
    const response = await fetch(`${this.httpUrl}/api/v1/scenarios`);

    if (!response.ok) {
      throw new Error(`Failed to fetch scenarios: ${response.status}`);
    }

    const data = await response.json();
    return toCamelCase<ScenarioInfo[]>(data);
  }

  /**
   * Get available contract types.
   *
   * @returns List of contract type information
   */
  async getContracts(): Promise<ContractInfo[]> {
    const response = await fetch(`${this.httpUrl}/api/v1/contracts`);

    if (!response.ok) {
      throw new Error(`Failed to fetch contracts: ${response.status}`);
    }

    const data = await response.json();
    return toCamelCase<ContractInfo[]>(data);
  }

  /**
   * Get simulation result by ID.
   *
   * @param simulationId - Simulation identifier
   * @returns Simulation result or null if not found
   */
  async getSimulation(simulationId: string): Promise<SimulationResult | null> {
    const response = await fetch(`${this.httpUrl}/api/v1/simulations/${simulationId}`);

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch simulation: ${response.status}`);
    }

    const data = await response.json();
    return toCamelCase<SimulationResult>(data);
  }

  /**
   * Get CHIT geometry packet for a simulation.
   *
   * @param simulationId - Simulation identifier
   * @param week - Optional specific week (defaults to final)
   * @returns CGP packet with hyperbolic geometry
   */
  async getGeometry(simulationId: string, week?: number): Promise<CGPPacket> {
    const url = week
      ? `${this.httpUrl}/api/v1/simulations/${simulationId}/geometry?week=${week}`
      : `${this.httpUrl}/api/v1/simulations/${simulationId}/geometry`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Failed to fetch geometry: ${response.status}`);
    }

    const data = await response.json();
    return toCamelCase<CGPPacket>(data);
  }

  /**
   * Get temporal evolution geometry for a simulation.
   *
   * @param simulationId - Simulation identifier
   * @returns CGP packet with 3D temporal path
   */
  async getTemporalGeometry(simulationId: string): Promise<CGPPacket> {
    const response = await fetch(
      `${this.httpUrl}/api/v1/simulations/${simulationId}/geometry/temporal`,
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch temporal geometry: ${response.status}`);
    }

    const data = await response.json();
    return toCamelCase<CGPPacket>(data);
  }

  /**
   * List recent simulations.
   *
   * @param limit - Maximum number of results
   * @returns List of simulation summaries
   */
  async listSimulations(limit = 10): Promise<SimulationResult[]> {
    const response = await fetch(`${this.httpUrl}/api/v1/simulations?limit=${limit}`);

    if (!response.ok) {
      throw new Error(`Failed to list simulations: ${response.status}`);
    }

    const data = await response.json();
    return toCamelCase<SimulationResult[]>(data);
  }

  /**
   * Check if Tokenism service is healthy.
   *
   * @returns true if service is healthy, false otherwise
   */
  async isHealthy(): Promise<boolean> {
    try {
      const response = await fetch(`${this.httpUrl}/healthz`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch (error) {
      // Distinguish network errors for better debugging
      const isNetworkError = error instanceof TypeError;
      const isTimeout = error instanceof DOMException && error.name === 'TimeoutError';

      logError(
        'Tokenism health check failed',
        error,
        'warning',
        {
          errorId: ErrorIds.TOKENISM_HEALTH_CHECK_FAILED,
          component: 'TokenismClient',
          url: this.httpUrl,
          isNetworkError,
          isTimeout,
        },
      );
      return false;
    }
  }
}

// Singleton instance
let defaultClient: TokenismClient | null = null;

/**
 * Get the default TokenismClient singleton instance.
 */
export function getTokenismClient(): TokenismClient {
  if (!defaultClient) {
    defaultClient = new TokenismClient();
  }
  return defaultClient;
}
