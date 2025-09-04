# Realtime Listener (Supabase)

For full Supabase (Auth, Realtime, Storage), use the Supabase CLI (recommended). Then you can listen to table changes with `@supabase/supabase-js`.

## Node.js Example
1) `npm init -y && npm i @supabase/supabase-js`
2) Create `listener.js`:
```
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = process.env.SUPABASE_URL || 'http://localhost:54321'
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
- This targets the Supabase CLI stack (URL `http://localhost:54321`). For the compose-based stack, additional configuration is required and not guaranteed to match `supabase-js` defaults; prefer the CLI for Realtime demos.
- Enable Realtime on tables in Supabase Studio (under “Database → Replication → Publications”).
