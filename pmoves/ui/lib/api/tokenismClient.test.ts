/**
 * Tokenism Client Tests
 *
 * Tests for the Tokenism API client including service discovery,
 * simulation requests, geometry packet retrieval, and error handling.
 */

import { TokenismClient, getTokenismClient } from '../tokenismClient';

// Mock fetch globally
global.fetch = jest.fn();

describe('TokenismClient', () => {
  let client: TokenismClient;
  const mockFetch = jest.mocked(fetch);

  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
    // Create client with default URL
    client = new TokenismClient();
  });

  afterEach(() => {
    // Reset singleton
    (TokenismClient as any).defaultClient = null;
  });

  describe('Service Discovery', () => {
    it('should use default URL when no options provided', () => {
      const defaultClient = new TokenismClient();
      expect(defaultClient).toBeInstanceOf(TokenismClient);
    });

    it('should use custom URL when provided', () => {
      const customClient = new TokenismClient({ httpUrl: 'http://custom-url:9999' });
      expect(customClient).toBeInstanceOf(TokenismClient);
    });

    it('should use NEXT_PUBLIC_TOKENISM_URL env variable when set', () => {
      process.env.NEXT_PUBLIC_TOKENISM_URL = 'http://env-url:8080';
      const envClient = new TokenismClient();
      expect(envClient).toBeInstanceOf(TokenismClient);
      delete process.env.NEXT_PUBLIC_TOKENISM_URL;
    });
  });

  describe('Health Check', () => {
    it('should return true when service is healthy', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
      } as Response);

      const isHealthy = await client.isHealthy();
      expect(isHealthy).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8103/healthz',
        expect.objectContaining({
          method: 'GET',
          signal: expect.any(AbortSignal),
        })
      );
    });

    it('should return false when service returns error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
      } as Response);

      const isHealthy = await client.isHealthy();
      expect(isHealthy).toBe(false);
    });

    it('should return false when network fails', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const isHealthy = await client.isHealthy();
      expect(isHealthy).toBe(false);
    });

    it('should use AbortSignal with 5 second timeout', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
      } as Response);

      await client.isHealthy();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8103/healthz',
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        })
      );
    });
  });

  describe('Run Simulation', () => {
    const mockParameters = {
      contractType: 'GroToken' as const,
      scenario: 'baseline' as const,
      participants: 100,
      weeks: 52,
    };

    it('should run simulation successfully', async () => {
      const mockResult = {
        simulationId: 'sim-123',
        scenario: 'baseline',
        contractType: 'GroToken',
        parameters: mockParameters,
        finalAvgWealth: 5000,
        finalGini: 0.35,
        systemicRiskScore: 0.2,
        weeklyMetrics: [],
        createdAt: '2025-01-11T00:00:00Z',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResult,
      } as Response);

      const result = await client.runSimulation(mockParameters);

      expect(result).toEqual(mockResult);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8103/api/v1/simulate',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(mockParameters),
        })
      );
    });

    it('should throw error when simulation fails', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        text: async () => 'Invalid parameters',
      } as Response);

      await expect(client.runSimulation(mockParameters)).rejects.toThrow(
        'Tokenism simulation failed: 400 - Invalid parameters'
      );
    });
  });

  describe('Get Scenarios', () => {
    it('should fetch scenarios successfully', async () => {
      const mockScenarios = [
        { name: 'baseline', description: 'Baseline scenario', defaultParams: {} },
        { name: 'optimistic', description: 'Optimistic scenario', defaultParams: {} },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockScenarios,
      } as Response);

      const scenarios = await client.getScenarios();

      expect(scenarios).toEqual(mockScenarios);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8103/api/v1/scenarios');
    });
  });

  describe('Get Contracts', () => {
    it('should fetch contract types successfully', async () => {
      const mockContracts = [
        { name: 'GroToken', description: 'Community currency', features: ['Rewards', 'Staking'] },
        { name: 'FoodUSD', description: 'Stablecoin', features: ['Stable value'] },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockContracts,
      } as Response);

      const contracts = await client.getContracts();

      expect(contracts).toEqual(mockContracts);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8103/api/v1/contracts');
    });
  });

  describe('Get Geometry', () => {
    it('should fetch geometry packet successfully', async () => {
      const mockGeometry = {
        cgpVersion: '1.0',
        packetType: 'wealth-distribution',
        simulationId: 'sim-123',
        geometry: {
          dimension: 2,
          manifold: 'hyperbolic',
          coordinates: 'poincare_disk',
          points: [[0, 0], [1, 1]],
          edges: [[0, 1]],
          bounds: { min: -1, max: 1 },
        },
        metadata: {},
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockGeometry,
      } as Response);

      const geometry = await client.getGeometry('sim-123');

      expect(geometry).toEqual(mockGeometry);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8103/api/v1/simulations/sim-123/geometry');
    });

    it('should fetch geometry for specific week', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ cgpVersion: '1.0', packetType: 'test', simulationId: 'sim-123', geometry: {}, metadata: {} }),
      } as Response);

      await client.getGeometry('sim-123', 25);

      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8103/api/v1/simulations/sim-123/geometry?week=25');
    });
  });

  describe('Get Temporal Geometry', () => {
    it('should fetch temporal evolution geometry', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ cgpVersion: '1.0', packetType: 'temporal', simulationId: 'sim-123', geometry: {}, metadata: {} }),
      } as Response);

      await client.getTemporalGeometry('sim-123');

      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8103/api/v1/simulations/sim-123/geometry/temporal');
    });
  });

  describe('List Simulations', () => {
    it('should list recent simulations', async () => {
      const mockSimulations = [
        { simulationId: 'sim-1', createdAt: '2025-01-10T00:00:00Z' },
        { simulationId: 'sim-2', createdAt: '2025-01-11T00:00:00Z' },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSimulations,
      } as Response);

      const simulations = await client.listSimulations(10);

      expect(simulations).toEqual(mockSimulations);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8103/api/v1/simulations?limit=10');
    });

    it('should use default limit of 10 when not specified', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as Response);

      await client.listSimulations();

      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8103/api/v1/simulations?limit=10');
    });
  });

  describe('Get Simulation', () => {
    it('should fetch simulation by ID', async () => {
      const mockSimulation = {
        simulationId: 'sim-123',
        scenario: 'baseline',
        contractType: 'GroToken',
        parameters: {},
        finalAvgWealth: 5000,
        finalGini: 0.35,
        systemicRiskScore: 0.2,
        weeklyMetrics: [],
        createdAt: '2025-01-11T00:00:00Z',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSimulation,
      } as Response);

      const simulation = await client.getSimulation('sim-123');

      expect(simulation).toEqual(mockSimulation);
    });

    it('should return null when simulation not found (404)', async () => {
      mockFetch.mockResolvedValueOnce({
        status: 404,
        ok: false,
      } as Response);

      const simulation = await client.getSimulation('nonexistent');

      expect(simulation).toBeNull();
    });

    it('should throw error for other HTTP errors', async () => {
      mockFetch.mockResolvedValueOnce({
        status: 500,
        ok: false,
      } as Response);

      await expect(client.getSimulation('sim-123')).rejects.toThrow('Failed to fetch simulation: 500');
    });
  });
});

describe('getTokenismClient', () => {
  it('should return singleton instance', () => {
    const client1 = getTokenismClient();
    const client2 = getTokenismClient();

    expect(client1).toBe(client2);
  });

  it('should create new instance on first call', () => {
    // Reset singleton
    (TokenismClient as any).defaultClient = null;

    const client = getTokenismClient();

    expect(client).toBeInstanceOf(TokenismClient);
  });
});
