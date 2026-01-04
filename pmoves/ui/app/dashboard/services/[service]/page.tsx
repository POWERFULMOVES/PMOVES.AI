import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import DashboardNavigation from '../../../../components/DashboardNavigation';
import MarkdownRenderer from '../../../../lib/markdown';
import { INTEGRATION_SERVICES, resolveService } from '../../../../lib/services';

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

export function generateStaticParams() {
  return INTEGRATION_SERVICES.map((service) => ({ service: service.slug }));
}

export async function generateMetadata({ params }: ServicePageProps): Promise<Metadata> {
  const resolvedParams = await resolveParams(params);
  const service = resolveService(resolvedParams.service);
  if (!service) {
    return {
      title: 'Service not found | PMOVES Console',
    };
  }

  return {
    title: `${service.title} service guide | PMOVES Console`,
    description: service.summary,
  };
}

export default async function ServiceDetailPage({ params }: ServicePageProps) {
  const resolvedParams = await resolveParams(params);
  const service = resolveService(resolvedParams.service);
  if (!service) {
    notFound();
  }

  let markdown = '';
  try {
    markdown = await readServiceMarkdown(service.docPath);
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-8">
      <DashboardNavigation active="services" />
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
    </div>
  );
}
