# Realtime Listener (Supabase)

For full Supabase (Auth, Realtime, Storage), use the Supabase CLI (recommended). Then you can listen to table changes with `@supabase/supabase-js`.

## Node.js Example
1) `npm init -y && npm i @supabase/supabase-js`
2) Create `listener.js`:
```
import { createClient } from '@supabase/supabase-js'

// Supabase CLI stack default (PMOVES single-env): REST/API on 65421
const SUPABASE_URL = process.env.SUPABASE_URL || 'http://localhost:65421'
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  realtime: { params: { eventsPerSecond: 2 } },
})

async function main(){
  const ch1 = supabase
    .channel('studio_board_changes')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'studio_board' }, payload => {
      console.log('studio_board change:', payload)
    })
    .subscribe()

  const ch2 = supabase
    .channel('it_errors_changes')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'it_errors' }, payload => {
      console.log('it_errors change:', payload)
    })
    .subscribe()
}

main().catch(console.error)
```
3) `SUPABASE_ANON_KEY=<anon-key-from-cli> node listener.js`

Notes:
- This targets the Supabase CLI stack (URL `http://localhost:65421`). For the compose-based stack, additional configuration is required and not guaranteed to match `supabase-js` defaults; prefer the CLI for Realtime demos.
- Enable Realtime on tables in Supabase Studio (under “Database → Replication → Publications”).

## Bridging Realtime → n8n (webhook trigger)
If you want n8n to react immediately (instead of polling Supabase REST on a cron), you can forward the Realtime payload to an n8n webhook.

Add this inside your `postgres_changes` handler:
```js
const N8N_WEBHOOK_URL = process.env.N8N_WEBHOOK_URL; // e.g. http://localhost:5678/webhook/<id>/webhook/<slug>

async function forwardToN8n(payload) {
  if (!N8N_WEBHOOK_URL) return;
  const res = await fetch(N8N_WEBHOOK_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    console.warn('n8n webhook failed', res.status, await res.text());
  }
}
```

Operational notes:
- Keep the Realtime listener **separate from n8n**. n8n can run on SQLite locally, and on Postgres on your VPS (`N8N_DB=postgres`).
- Realtime is best-effort delivery; you still want a **poller fallback** for missed events and for initial backfills.
