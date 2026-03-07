import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { ReactElement } from 'react';
import DashboardNavigation from '../../../../components/DashboardNavigation';
import MarkdownRenderer from '../../../../lib/markdown';
import {
  INTEGRATION_SERVICES,
  type ServiceDefinition as IntegrationServiceDefinition,
  resolveService,
} from '../../../../lib/services';
import {
  SERVICE_CATALOG,
  type ServiceDefinition as CatalogServiceDefinition,
} from '../../../../lib/serviceCatalog';

interface ServicePageParams {
  service: string;
}

type ServicePageProps = {
  params: ServicePageParams | Promise<ServicePageParams>;
};

async function resolveParams(
  params: ServicePageProps['params']
): Promise<ServicePageParams> {
  if (params && typeof (params as Promise<ServicePageParams>).then === 'function') {
    return params as Promise<ServicePageParams>;
  }
  return params as ServicePageParams;
}

async function readServiceMarkdown(docPath: string): Promise<string> {
  const absolutePath = path.join(process.cwd(), docPath);
  try {
    const file = await fs.readFile(absolutePath, 'utf-8');
    return file;
  } catch (error) {
    console.error(`[services] Failed to read markdown at ${absolutePath}`, error);
    throw error;
  }
}

function resolveCatalogService(slug: string): CatalogServiceDefinition | undefined {
  return SERVICE_CATALOG.find((service) => service.slug === slug);
}

function CatalogFallback({
  service,
}: {
  service: CatalogServiceDefinition;
}) {
  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="text-xl font-semibold text-slate-900">Service Overview</h2>
        <p className="mt-2 text-sm text-slate-700">{service.summary}</p>
        <dl className="mt-4 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
          <div>
            <dt className="font-semibold text-slate-800">Slug</dt>
            <dd>{service.slug}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-800">Category</dt>
            <dd>{service.category}</dd>
          </div>
          {service.profile ? (
            <div>
              <dt className="font-semibold text-slate-800">Compose Profile</dt>
              <dd>{service.profile}</dd>
            </div>
          ) : null}
          {service.healthCheck ? (
            <div>
              <dt className="font-semibold text-slate-800">Health Check</dt>
              <dd className="break-all">{service.healthCheck}</dd>
            </div>
          ) : null}
        </dl>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="text-xl font-semibold text-slate-900">Endpoints</h2>
        {service.endpoints.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">No direct endpoints are registered for this service.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {service.endpoints.map((endpoint) => (
              <li
                key={`${endpoint.name}-${endpoint.port}-${endpoint.path}`}
                className="rounded border border-slate-200 px-3 py-2 text-sm text-slate-700"
              >
                <span className="font-semibold text-slate-900">{endpoint.name}</span>{' '}
                <span className="text-slate-500">({endpoint.type})</span>
                <div className="mt-1 font-mono text-xs">
                  {endpoint.port}
                  {endpoint.path}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {service.capabilities && service.capabilities.length > 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-slate-900">Capabilities</h2>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {service.capabilities.map((capability) => (
              <li key={capability}>{capability}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {service.dependencies && service.dependencies.length > 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-slate-900">Dependencies</h2>
          <p className="mt-2 text-sm text-slate-700">{service.dependencies.join(', ')}</p>
        </div>
      ) : null}

      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        No dedicated markdown runbook is mapped for this service slug yet. This fallback view is generated from the
        live UI service catalog.
      </div>
    </div>
  );
}

export function generateStaticParams() {
  const slugs = new Set<string>([
    ...INTEGRATION_SERVICES.map((service) => service.slug),
    ...SERVICE_CATALOG.map((service) => service.slug),
  ]);
  return Array.from(slugs).map((service) => ({ service }));
}

export async function generateMetadata({ params }: ServicePageProps): Promise<Metadata> {
  const resolvedParams = await resolveParams(params);
  const service = resolveService(resolvedParams.service);
  if (service) {
    return {
      title: `${service.title} service guide | PMOVES Console`,
      description: service.summary,
    };
  }

  const catalogService = resolveCatalogService(resolvedParams.service);
  if (catalogService) {
    return {
      title: `${catalogService.title} service | PMOVES Console`,
      description: catalogService.summary,
    };
  }

  return {
    title: 'Service not found | PMOVES Console',
  };
}

function renderServiceDoc(service: IntegrationServiceDefinition, markdown: string) {
  return (
    <>
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Link href="/dashboard/services" className="hover:text-slate-700">
            Services
          </Link>
          <span aria-hidden="true">/</span>
          <span className="font-medium text-slate-900">{service.title}</span>
        </div>
        <h1 className="text-3xl font-semibold text-slate-900">{service.title}</h1>
        <p className="text-sm text-slate-600">{service.summary}</p>
      </header>
      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white p-6">
        <MarkdownRenderer content={markdown} />
      </div>
    </>
  );
}

function renderCatalogService(service: CatalogServiceDefinition) {
  return (
    <>
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Link href="/dashboard/services" className="hover:text-slate-700">
            Services
          </Link>
          <span aria-hidden="true">/</span>
          <span className="font-medium text-slate-900">{service.title}</span>
        </div>
        <h1 className="text-3xl font-semibold text-slate-900">{service.title}</h1>
        <p className="text-sm text-slate-600">{service.summary}</p>
      </header>
      <CatalogFallback service={service} />
    </>
  );
}

export default async function ServiceDetailPage({ params }: ServicePageProps) {
  const resolvedParams = await resolveParams(params);
  const service = resolveService(resolvedParams.service);
  const catalogService = resolveCatalogService(resolvedParams.service);

  if (!service && !catalogService) {
    notFound();
  }

  let content: ReactElement;
  if (service) {
    try {
      const markdown = await readServiceMarkdown(service.docPath);
      content = renderServiceDoc(service, markdown);
    } catch {
      if (!catalogService) {
        notFound();
      }
      content = renderCatalogService(catalogService);
    }
  } else if (catalogService) {
    content = renderCatalogService(catalogService);
  } else {
    notFound();
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-8">
      <DashboardNavigation active="services" />
      {content}
    </div>
  );
}
