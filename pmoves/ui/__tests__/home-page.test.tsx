import { render, screen } from '@testing-library/react';
import { Suspense } from 'react';
import HomePage from '@/app/page';

describe('HomePage', () => {
  it.skip('provides navigation to the ingestion dashboard', async () => {
    render(
      <Suspense fallback={null}>
        {/* HomePage is async in Next 16 */}
        <HomePage />
      </Suspense>
    );
    const link = await screen.findByRole('link', { name: /ingest/i }, { timeout: 5000 });
    expect(link).toBeInTheDocument();
  });
});
