import React from 'react';
import { render, screen } from '@testing-library/react';
import ServicesIndexPage from '@/app/dashboard/services/page';
import ServiceDetailPage from '@/app/dashboard/services/[service]/page';
import { INTEGRATION_SERVICES } from '@/lib/services';
import { SERVICE_CATALOG } from '@/lib/serviceCatalog';
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

    // TAC 1: The centralized UI uses "Services" as the page title
    expect(
      screen.getByRole('heading', { name: /services/i })
    ).toBeInTheDocument();

    // TAC 1: The new centralized UI displays services from SERVICE_CATALOG
    // Check that a sample of key services are present
    const sampleServices = ['Prometheus', 'Grafana', 'Agent Zero', 'Archon', 'TensorZero'];
    sampleServices.forEach((title) => {
      const links = screen.getAllByRole('link', { name: new RegExp(title, 'i') });
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
