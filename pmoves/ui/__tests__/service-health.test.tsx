/* ═══════════════════════════════════════════════════════════════════════════
   Tests: ServiceHealthIndicator
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen } from '@testing-library/react';
import { ServiceHealthIndicator } from '../components/services/ServiceHealthIndicator';

describe('ServiceHealthIndicator', () => {
  describe('Status Display', () => {
    it('renders healthy status with green color', () => {
      const { container } = render(<ServiceHealthIndicator status="healthy" size="md" />);
      const indicator = container.querySelector('.bg-cata-forest');
      expect(indicator).toBeInTheDocument();
    });

    it('renders unhealthy status with red color', () => {
      const { container } = render(<ServiceHealthIndicator status="unhealthy" size="md" />);
      const indicator = container.querySelector('.bg-cata-ember');
      expect(indicator).toBeInTheDocument();
    });

    it('renders unknown status with gray color', () => {
      const { container } = render(<ServiceHealthIndicator status="unknown" size="md" />);
      const indicator = container.querySelector('.bg-ink-muted');
      expect(indicator).toBeInTheDocument();
    });

    it('renders checking status with yellow color and spin animation', () => {
      const { container } = render(<ServiceHealthIndicator status="checking" size="md" />);
      const indicator = container.querySelector('.bg-cata-gold.animate-spin');
      expect(indicator).toBeInTheDocument();
    });
  });

  describe('Size Variants', () => {
    it('renders small size indicator', () => {
      const { container } = render(<ServiceHealthIndicator status="healthy" size="sm" />);
      // Escape the dot in Tailwind class for querySelector
      const dot = container.querySelector('.w-1\\.5.h-1\\.5');
      expect(dot).toBeInTheDocument();
    });

    it('renders medium size indicator', () => {
      const { container } = render(<ServiceHealthIndicator status="healthy" size="md" />);
      const dot = container.querySelector('.w-2.h-2');
      expect(dot).toBeInTheDocument();
    });

    it('renders large size indicator', () => {
      const { container } = render(<ServiceHealthIndicator status="healthy" size="lg" />);
      const dot = container.querySelector('.w-3.h-3');
      expect(dot).toBeInTheDocument();
    });
  });

  describe('Pulse Animation', () => {
    it('shows pulse animation when showPulse is true and status is healthy', () => {
      const { container } = render(
        <ServiceHealthIndicator status="healthy" size="md" showPulse={true} />
      );
      const pulse = container.querySelector('.animate-pulse');
      expect(pulse).toBeInTheDocument();
    });

    it('does not show pulse animation when showPulse is false', () => {
      const { container } = render(
        <ServiceHealthIndicator status="healthy" size="md" showPulse={false} />
      );
      const pulse = container.querySelector('.animate-pulse');
      expect(pulse).not.toBeInTheDocument();
    });

    it('shows ping animation when showPulse is true and status is healthy', () => {
      const { container } = render(
        <ServiceHealthIndicator status="healthy" size="md" showPulse={true} />
      );
      const ping = container.querySelector('.before\\:animate-ping');
      expect(ping).toBeInTheDocument();
    });

    it('does not show ping animation for unhealthy status', () => {
      const { container } = render(
        <ServiceHealthIndicator status="unhealthy" size="md" showPulse={true} />
      );
      const indicator = container.firstChild as HTMLElement;
      expect(indicator.className).not.toContain('before:animate-ping');
    });
  });

  describe('Accessibility', () => {
    it('includes accessible label for screen readers', () => {
      render(<ServiceHealthIndicator status="healthy" size="md" />);
      const indicator = screen.getByLabelText(/service status: healthy/i);
      expect(indicator).toBeInTheDocument();
    });

    it('updates aria-label based on status', () => {
      const { rerender } = render(<ServiceHealthIndicator status="healthy" size="md" />);
      expect(screen.getByLabelText(/service status: healthy/i)).toBeInTheDocument();

      rerender(<ServiceHealthIndicator status="unhealthy" size="md" />);
      expect(screen.getByLabelText(/service status: unhealthy/i)).toBeInTheDocument();
    });
  });
});
