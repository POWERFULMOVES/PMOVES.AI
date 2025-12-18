import React from 'react';
import { render, screen } from '@testing-library/react';
import ServicesIndexPage from '@/app/dashboard/services/page';
import ServiceDetailPage from '@/app/dashboard/services/[service]/page';
import { INTEGRATION_SERVICES } from '@/lib/services';
import { notFound } from 'next/navigation';

jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('remark-gfm', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('next/navigation', () => ({
  __esModule: true,
  notFound: jest.fn(() => {
    throw new Error('not found');
  }),
  usePathname: jest.fn(() => '/dashboard/services'),
  useRouter: jest.fn(() => ({ push: jest.fn(), replace: jest.fn() })),
}));

describe('Services dashboards', () => {
  const mockedNotFound = jest.mocked(notFound);

  beforeEach(() => {
    mockedNotFound.mockClear();
  });

  it('lists all operator integrations on the index route', () => {
    render(<ServicesIndexPage />);

    expect(
      screen.getByRole('heading', { name: /integration services/i })
    ).toBeInTheDocument();

    // Use getAllByRole since the new design may have multiple links per service
    // (service card + quick links section)
    INTEGRATION_SERVICES.forEach((service) => {
      const links = screen.getAllByRole('link', { name: new RegExp(service.title, 'i') });
      expect(links.length).toBeGreaterThan(0);
    });
  });

  it('renders markdown for a known service without invoking notFound', async () => {
    const element = await ServiceDetailPage({
      params: { service: 'open-notebook' },
    });

    render(element);

    expect(
      screen.getByRole('heading', { name: /open notebook/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/Service Guide/i)).toBeInTheDocument();
    expect(mockedNotFound).not.toHaveBeenCalled();
  });

  it('delegates to Next.js notFound for unknown services', async () => {
    await expect(
      ServiceDetailPage({ params: { service: 'does-not-exist' } })
    ).rejects.toThrow('not found');
    expect(mockedNotFound).toHaveBeenCalled();
  });
});
