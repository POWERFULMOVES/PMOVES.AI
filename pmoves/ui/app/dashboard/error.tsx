'use client';

import { useEffect } from 'react';
import Link from 'next/link';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[DashboardError]', error);
  }, [error]);

  return (
    <div className="min-h-[400px] flex items-center justify-center p-6">
      <div className="max-w-md text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-cata-ember/10 flex items-center justify-center">
          <span className="text-2xl">!</span>
        </div>
        <h2 className="text-xl font-display font-semibold text-ink-primary mb-2">
          Dashboard Error
        </h2>
        <p className="text-ink-muted mb-6 text-sm">
          {error.message || 'Failed to load this section'}
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="px-4 py-2 bg-cata-cyan text-void rounded-md text-sm font-medium hover:bg-cata-cyan/90 transition-colors"
          >
            Retry
          </button>
          <Link
            href="/dashboard"
            className="px-4 py-2 border border-border-subtle rounded-md text-sm font-medium text-ink-secondary hover:bg-void-elevated transition-colors"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
