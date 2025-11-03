#!/usr/bin/env node

const parseArgs = (argv) => {
  const opts = {};
  for (const raw of argv) {
    if (!raw.startsWith("--")) continue;
    const [key, value = "true"] = raw.slice(2).split("=");
    opts[key] = value;
  }
  return opts;
};

const fail = (message) => {
  console.error(`✖ ${message}`);
  process.exitCode = 1;
};

const log = (message) => {
  console.log(`• ${message}`);
};

(async () => {
  const args = parseArgs(process.argv.slice(2));
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;
  const restUrlEnv =
    process.env.NEXT_PUBLIC_SUPABASE_REST_URL || process.env.SUPABASE_REST_URL || (supabaseUrl ? `${supabaseUrl.replace(/\/$/, "")}/rest/v1` : undefined);

  let threadId = args.thread || process.env.NOTEBOOK_SMOKE_THREAD_ID || process.env.NOTEBOOK_WORKBENCH_THREAD_ID || "";
  const limitRaw = args.limit || process.env.NOTEBOOK_SMOKE_LIMIT || "1";
  const limit = Number.parseInt(limitRaw, 10);

  const missing = [];
  if (!supabaseUrl) missing.push("NEXT_PUBLIC_SUPABASE_URL or SUPABASE_URL");
  if (!anonKey) missing.push("NEXT_PUBLIC_SUPABASE_ANON_KEY or SUPABASE_ANON_KEY");
  if (!restUrlEnv) missing.push("NEXT_PUBLIC_SUPABASE_REST_URL or SUPABASE_REST_URL");

  if (missing.length > 0) {
    fail(`Missing required Supabase env vars: ${missing.join(", ")}`);
    return;
  }

  const restUrl = restUrlEnv.replace(/\/$/, "");

  log(`Supabase REST endpoint: ${restUrl}`);

  if (!threadId) {
    log("No thread ID supplied (set NOTEBOOK_SMOKE_THREAD_ID or pass --thread=<uuid> to query data).");
    log("Environment check complete.");
    return;
  }

  if (Number.isNaN(limit) || limit <= 0) {
    fail(`Invalid limit value: ${limitRaw}`);
    return;
  }

  const headers = {
    apikey: anonKey,
    Authorization: `Bearer ${anonKey}`,
    accept: "application/json",
  };

  const url = `${restUrl}/chat_messages?thread_id=eq.${encodeURIComponent(threadId)}&select=id&limit=${limit}`;

  try {
    log(`Fetching ${url}`);
    const response = await fetch(url, { headers });
    if (!response.ok) {
      const text = await response.text();
      fail(`Supabase REST request failed (${response.status} ${response.statusText}): ${text}`);
      return;
    }
    const data = await response.json();
    const count = Array.isArray(data) ? data.length : 0;
    if (count === 0) {
      fail(`No chat_messages rows returned for thread ${threadId}.`);
      return;
    }
    log(`Rows returned: ${count}`);
    log("Notebook Workbench smoke succeeded.");
  } catch (error) {
    fail(`Unexpected error: ${error instanceof Error ? error.message : String(error)}`);
  }
})();
