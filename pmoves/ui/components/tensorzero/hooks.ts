/* ═══════════════════════════════════════════════════════════════════════════
   TensorZero React Query Hooks
   ═══════════════════════════════════════════════════════════════════════════ */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  TensorZeroConfig,
  TestRequest,
  TestResponse,
  ValidationResult,
} from './types';
import {
  fetchConfig,
  updateConfig,
  validateConfig,
  testRequest,
  fetchMetrics,
  checkHealth,
} from './api';

/**
 * Query keys for TensorZero data
 */
export const tensorzeroKeys = {
  all: ['tensorzero'] as const,
  config: () => [...tensorzeroKeys.all, 'config'] as const,
  health: () => [...tensorzeroKeys.all, 'health'] as const,
  metrics: (range: string) => [...tensorzeroKeys.all, 'metrics', range] as const,
  validation: () => [...tensorzeroKeys.all, 'validation'] as const,
};

/**
 * Hook to fetch TensorZero configuration
 */
export function useTensorZeroConfig() {
  return useQuery({
    queryKey: tensorzeroKeys.config(),
    queryFn: fetchConfig,
    staleTime: 60000, // 1 minute
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

/**
 * Hook to update TensorZero configuration
 */
export function useUpdateConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (config: TensorZeroConfig) => updateConfig(config),
    onSuccess: () => {
      // Invalidate and refetch config
      queryClient.invalidateQueries({ queryKey: tensorzeroKeys.config() });
    },
  });
}

/**
 * Hook to validate TensorZero configuration
 */
export function useValidateConfig() {
  return useMutation({
    mutationFn: (config: TensorZeroConfig) => validateConfig(config),
  });
}

/**
 * Hook to send test request
 */
export function useTestRequest() {
  return useMutation({
    mutationFn: (request: TestRequest) => testRequest(request),
  });
}

/**
 * Hook to fetch metrics
 */
export function useMetrics(timeRange: string = '1h') {
  return useQuery({
    queryKey: tensorzeroKeys.metrics(timeRange),
    queryFn: () => fetchMetrics(timeRange),
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // Refetch every minute
    retry: 2,
    enabled: false, // Don't auto-fetch, user must trigger
  });
}

/**
 * Hook to check TensorZero health
 */
export function useTensorZeroHealth() {
  return useQuery({
    queryKey: tensorzeroKeys.health(),
    queryFn: checkHealth,
    staleTime: 10000, // 10 seconds
    refetchInterval: 30000, // Check every 30 seconds
    retry: 1,
  });
}

/**
 * Hook to manually trigger metrics refresh
 */
export function useRefetchMetrics() {
  const queryClient = useQueryClient();

  return (timeRange: string = '1h') => {
    return queryClient.refetchQueries({
      queryKey: tensorzeroKeys.metrics(timeRange),
    });
  };
}
