// Dashboard routes are operational surfaces that read live env/services
// (Supabase, room catalog, service URLs). Several of their client pages
// throw during build-time prerender when that env is absent — which is
// exactly the case inside `docker build`, where no credentials exist.
// force-dynamic renders the whole segment at request time instead, so
// image builds never need live configuration.
export const dynamic = "force-dynamic";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
