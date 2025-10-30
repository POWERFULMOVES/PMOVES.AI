# PMOVES Operator Console UI

This package contains the Next.js front end that surfaces ingestion workflows, video review tooling, and integration runbooks for PMOVES operators.

## Development quickstart

```bash
npm install
npm run dev
```

The development server runs on [http://localhost:3000](http://localhost:3000). Any changes under `app/`, `components/`, or `lib/` trigger automatic reloads.

## Services dashboard workflow

The dashboard now includes a **Services** section under `/dashboard/services` that highlights the external integrations bundled with PMOVES:

- Open Notebook
- PMOVES.YT
- Jellyfin
- Wger
- Firefly

Use the pills at the top of the ingestion, video, and services pages to move between dashboards. Each service card links to a dedicated page (for example `/dashboard/services/open-notebook`) that renders the markdown runbook from `pmoves/docs/services/<service>/README.md` via a shared Markdown renderer.

## Testing

Run the full suite before publishing changes:

```bash
npm run lint
npm run test
npm run test:e2e
```

The Jest coverage exercises the new services index and detail routes to ensure they render without auth prompts. The Playwright run boots the dev server and validates that the integration list and markdown pages load successfully.
