import { NextRequest, NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

import { checkAllServices, getHealthPercentage } from "@/lib/serviceHealth";
import { ownerFromJwt } from "@/lib/jwtUtils";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type ExecutiveMetrics = Record<string, string>;

interface AuditBlocker {
  id: string;
  blocker: string;
  severity: string;
  status: string;
  nextAction: string;
}

interface ReleaseGate {
  id: string;
  status: string;
  notes: string;
}

interface PrMonitorSummary {
  available: boolean;
  source: string | null;
  count: number;
  totalBlockers: number;
  totalPendingChecks: number;
  totalFailedChecks: number;
}

interface GraphitiSummary {
  available: boolean;
  source: string | null;
  generatedAt: string | null;
}

interface RuntimeHealthSummary {
  total: number;
  healthy: number;
  unhealthy: number;
  unknown: number;
  percentage: number;
  timestamp: Date;
}

interface PrMonitorItemShape {
  blockers?: unknown;
  checks?: {
    pending?: number;
    failed?: number;
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

async function exists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function findDocsRoot(): Promise<string | null> {
  const cwd = process.cwd();
  const candidates = [
    path.resolve(cwd, "../docs"), // when running from pmoves/ui
    path.resolve(cwd, "pmoves/docs"), // when running from repo root
    path.resolve(cwd, "docs"), // fallback
  ];

  for (const candidate of candidates) {
    if (await exists(candidate)) {
      return candidate;
    }
  }
  return null;
}

async function readText(filePath: string): Promise<string | null> {
  try {
    return await fs.readFile(filePath, "utf8");
  } catch {
    return null;
  }
}

async function readJson<T>(filePath: string): Promise<T | null> {
  const text = await readText(filePath);
  if (!text) return null;
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

function parseLabelValue(markdown: string, label: string): string | null {
  const pattern = new RegExp(`\\*\\*${label}:\\*\\*\\s*([^\\n]+)`, "i");
  const match = markdown.match(pattern);
  if (!match) return null;
  return match[1].replace(/`/g, "").trim();
}

function parseMetricTable(markdown: string): ExecutiveMetrics {
  const metrics: ExecutiveMetrics = {};
  for (const line of markdown.split(/\r?\n/)) {
    if (!line.startsWith("|")) continue;
    const cols = line
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cols.length < 2) continue;
    if (cols[0].toLowerCase() === "metric") continue;
    if (cols[0].startsWith("---")) continue;
    if (!cols[0] || !cols[1]) continue;
    metrics[cols[0]] = cols[1];
  }
  return metrics;
}

function parseActiveBlockers(markdown: string): AuditBlocker[] {
  const blockers: AuditBlocker[] = [];
  const lines = markdown.split(/\r?\n/);
  let inTable = false;

  for (const line of lines) {
    if (line.startsWith("| ID | Blocker |")) {
      inTable = true;
      continue;
    }
    if (!inTable) continue;
    if (!line.startsWith("|")) break;
    if (line.includes("---")) continue;

    const cols = line
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cols.length < 6) continue;
    if (!/^AB-\d+$/i.test(cols[0])) continue;

    blockers.push({
      id: cols[0],
      blocker: cols[1],
      severity: cols[3].replace(/\*/g, ""),
      status: cols[4],
      nextAction: cols[5],
    });
  }

  return blockers;
}

function parseReleaseGateRows(markdown: string): ReleaseGate[] {
  const gates: ReleaseGate[] = [];
  for (const line of markdown.split(/\r?\n/)) {
    if (!line.startsWith("| RG-")) continue;
    const cols = line
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cols.length < 3) continue;
    gates.push({
      id: cols[0],
      status: cols[1],
      notes: cols[2],
    });
  }
  return gates;
}

async function latestReleaseGatePath(docsRoot: string): Promise<string | null> {
  const auditDir = path.join(docsRoot, "audit");
  if (!(await exists(auditDir))) return null;
  const files = await fs.readdir(auditDir);
  const matches = files.filter((name) => /^RELEASE_GATE_CHECK_\d{4}-\d{2}-\d{2}\.md$/i.test(name));
  if (!matches.length) return null;
  matches.sort((a, b) => b.localeCompare(a));
  return path.join(auditDir, matches[0]);
}

async function readPrMonitorSummary(docsRoot: string): Promise<PrMonitorSummary> {
  const primary = path.join(docsRoot, "logs", "pr_monitor_latest.json");
  let source: string | null = null;
  let payload: unknown = null;

  if (await exists(primary)) {
    payload = await readJson<unknown>(primary);
    source = primary;
  } else {
    const fallbackDir = path.join(docsRoot, "evidence", "pr_monitor");
    if (await exists(fallbackDir)) {
      const files = (await fs.readdir(fallbackDir)).filter((f) => f.endsWith("-latest.json"));
      files.sort((a, b) => b.localeCompare(a));
      if (files.length > 0) {
        source = path.join(fallbackDir, files[0]);
        payload = await readJson<unknown>(source);
      }
    }
  }

  if (!payload || !source) {
    return {
      available: false,
      source: null,
      count: 0,
      totalBlockers: 0,
      totalPendingChecks: 0,
      totalFailedChecks: 0,
    };
  }

  const payloadRecord = asRecord(payload);
  const items = Array.isArray(payloadRecord?.items) ? (payloadRecord.items as PrMonitorItemShape[]) : [];
  if (items.length > 0) {
    return {
      available: true,
      source,
      count: items.length,
      totalBlockers: items.reduce(
        (acc: number, item) => acc + (Array.isArray(item?.blockers) ? item.blockers.length : 0),
        0,
      ),
      totalPendingChecks: items.reduce(
        (acc: number, item) => acc + asNumber(item?.checks?.pending),
        0,
      ),
      totalFailedChecks: items.reduce(
        (acc: number, item) => acc + asNumber(item?.checks?.failed),
        0,
      ),
    };
  }

  const summary = asRecord(payloadRecord?.summary);
  return {
    available: true,
    source,
    count: asNumber(summary?.checks_total) > 0 ? 1 : 0,
    totalBlockers: 0,
    totalPendingChecks: asNumber(summary?.checks_pending),
    totalFailedChecks: asNumber(summary?.checks_failed),
  };
}

async function readGraphitiSummary(docsRoot: string): Promise<GraphitiSummary> {
  const primary = path.join(docsRoot, "logs", "graphiti_signed_latest.json");
  const payload = await readJson<unknown>(primary);
  const payloadRecord = asRecord(payload);
  if (!payload) {
    return {
      available: false,
      source: null,
      generatedAt: null,
    };
  }
  return {
    available: true,
    source: primary,
    generatedAt: asString(payloadRecord?.generated_at ?? payloadRecord?.timestamp) || null,
  };
}

function parsePlanLastUpdated(markdown: string): string | null {
  const firstLine = markdown.split(/\r?\n/).find((line) => /last updated/i.test(line));
  if (!firstLine) return null;
  const cleaned = firstLine
    .replace(/^[_*\s]+|[_*\s]+$/g, "")
    .replace(/^[^:]+:\s*/i, "")
    .trim();
  return cleaned || null;
}

export async function GET(request: NextRequest) {
  const { ownerId, error: authError } = ownerFromJwt('audit/summary');
  if (authError || !ownerId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const includeHealth = request.nextUrl.searchParams.get("includeHealth") !== "false";
  const rawTimeout = parseInt(request.nextUrl.searchParams.get("timeout") || "3000", 10);
  const timeout = Number.isFinite(rawTimeout) && rawTimeout > 0 ? Math.min(Math.max(rawTimeout, 1000), 30000) : 3000;

  const warnings: string[] = [];
  const docsRoot = await findDocsRoot();
  if (!docsRoot) {
    return NextResponse.json(
      {
        generatedAt: new Date().toISOString(),
        warnings: ["docs root not found; expected pmoves/docs in working tree"],
      },
      { status: 500 },
    );
  }

  const dashboardPath = path.join(docsRoot, "PRODUCTION_AUDIT_DASHBOARD.md");
  const dashboardMarkdown = await readText(dashboardPath);
  if (!dashboardMarkdown) {
    warnings.push("missing PRODUCTION_AUDIT_DASHBOARD.md");
  }

  const releaseGatePath = await latestReleaseGatePath(docsRoot);
  const releaseGateMarkdown = releaseGatePath ? await readText(releaseGatePath) : null;
  if (!releaseGateMarkdown) {
    warnings.push("missing release gate check markdown");
  }

  const roadmapPath = path.join(docsRoot, "PMOVES.AI PLANS", "ROADMAP.md");
  const roadmapMarkdown = await readText(roadmapPath);
  const nextStepsPath = path.join(docsRoot, "NEXT_STEPS.md");
  const nextStepsMarkdown = await readText(nextStepsPath);

  const prMonitor = await readPrMonitorSummary(docsRoot);
  if (!prMonitor.available) {
    warnings.push("pr monitor artifact not found");
  }
  const graphiti = await readGraphitiSummary(docsRoot);
  if (!graphiti.available) {
    warnings.push("graphiti artifact not found");
  }

  let runtimeHealth: RuntimeHealthSummary | null = null;
  if (includeHealth) {
    try {
      const health = await checkAllServices(timeout);
      runtimeHealth = {
        total: health.total,
        healthy: health.healthy,
        unhealthy: health.unhealthy,
        unknown: health.unknown,
        percentage: getHealthPercentage(health),
        timestamp: health.timestamp,
      };
    } catch (error) {
      warnings.push(`runtime health check failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  return NextResponse.json(
    {
      generatedAt: new Date().toISOString(),
      warnings,
      productionAudit: {
        source: dashboardMarkdown ? path.basename(dashboardPath) : null,
        lastUpdated: dashboardMarkdown ? parseLabelValue(dashboardMarkdown, "Last Updated") : null,
        branch: dashboardMarkdown ? parseLabelValue(dashboardMarkdown, "Branch") : null,
        commit: dashboardMarkdown ? parseLabelValue(dashboardMarkdown, "Commit") : null,
        executiveMetrics: dashboardMarkdown ? parseMetricTable(dashboardMarkdown) : {},
        activeBlockers: dashboardMarkdown ? parseActiveBlockers(dashboardMarkdown) : [],
      },
      releaseGates: {
        source: releaseGateMarkdown && releaseGatePath ? path.basename(releaseGatePath) : null,
        items: releaseGateMarkdown ? parseReleaseGateRows(releaseGateMarkdown) : [],
      },
      planning: {
        roadmap: {
          source: roadmapMarkdown ? path.basename(roadmapPath) : null,
          lastUpdated: roadmapMarkdown ? parsePlanLastUpdated(roadmapMarkdown) : null,
        },
        nextSteps: {
          source: nextStepsMarkdown ? path.basename(nextStepsPath) : null,
          lastUpdated: nextStepsMarkdown ? parsePlanLastUpdated(nextStepsMarkdown) : null,
        },
      },
      prMonitor,
      graphiti,
      runtimeHealth,
    },
    {
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Content-Type": "application/json",
      },
    },
  );
}
