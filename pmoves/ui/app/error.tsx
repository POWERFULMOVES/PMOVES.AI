'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to error reporting service
    console.error('[GlobalError]', error);
  }, [error]);

  return (
    <html>
      <body className="min-h-screen bg-void flex items-center justify-center p-6">
        <div className="max-w-md text-center">
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
      </body>
    </html>
  );
}
