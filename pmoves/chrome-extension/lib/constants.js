// PMOVES.AI Chrome Extension - Default Configuration
export const VERSION = '1.0.0';

export const DEFAULT_SERVICES = {
  tensorzero:      'http://localhost:3030',
  gpuOrchestrator: 'http://localhost:8200',
  hirag:           'http://localhost:8086',
  pmovesYt:        'http://localhost:8077',
  agentZero:       'http://localhost:8080',
  fluteGateway:    'http://localhost:8055',
  prometheus:      'http://localhost:9090',
  gateway:         'http://localhost:8085',
};

export const DEFAULT_CONFIG = {
  services: { ...DEFAULT_SERVICES },
  auth: {
    agentZeroToken: '',
    fluteApiKey: '',
  },
  features: {
    autoProcess: false,
    showFloatingButton: true,
    showThumbnailButtons: true,
    showNotifications: true,
    healthPollInterval: 30, // seconds
  },
};

export const HEALTH_ENDPOINTS = {
  tensorzero:      { path: '/v1/models',    method: 'GET' },
  gpuOrchestrator: { path: '/api/gpu/status', method: 'GET' },
  hirag:           { path: '/',              method: 'GET' },
  pmovesYt:        { path: '/healthz',       method: 'GET' },
  agentZero:       { path: '/healthz',       method: 'GET' },
  fluteGateway:    { path: '/healthz',       method: 'GET' },
  prometheus:      { path: '/-/healthy',     method: 'GET' },
  gateway:         { path: '/',              method: 'GET' },
};

// Badge colors for health status
export const BADGE_COLORS = {
  healthy:  '#4CAF50',
  degraded: '#FF9800',
  down:     '#F44336',
  unknown:  '#9E9E9E',
};
