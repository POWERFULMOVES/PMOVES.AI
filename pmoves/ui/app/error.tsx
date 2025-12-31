'use client';

import { useEffect } from 'react';
import { logError } from '@/lib/errorUtils';
import { ErrorIds } from '@/lib/constants/errorIds';

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logError('Root error boundary caught error', error, 'critical', {
      errorId: ErrorIds.ROOT_ERROR_BOUNDARY,
      component: 'RootErrorBoundary',
      digest: error.digest,
    });
  }, [error]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="min-h-screen bg-void flex items-center justify-center p-6"
    >
      <div className="max-w-md text-center">
        <div
          className="w-16 h-16 mx-auto mb-4 rounded-full bg-cata-ember/10 flex items-center justify-center"
          aria-hidden="true"
        >
          <span className="text-2xl text-cata-ember">!</span>
        </div>
        <h1 className="text-2xl font-display font-bold text-ink-primary mb-4">
          Something went wrong
        </h1>
        <p className="text-ink-muted mb-6">
          {error.message || 'An unexpected error occurred'}
        </p>
        <button
          onClick={reset}
          className="px-4 py-2 bg-cata-cyan text-void rounded-md font-medium hover:bg-cata-cyan/90 transition-colors"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
