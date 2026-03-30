Start PMOVES services on the 5090 node.

## Implementation

Core data + workers:

```bash
SUPABASE_RUNTIME=cli make -C pmoves up
```

GPU services (5090 primary):

```bash
make -C pmoves up-gpu
```

Agents (published images):

```bash
SUPABASE_RUNTIME=cli make -C pmoves up-agents-published
```

Full bring-up with smoke:

```bash
SUPABASE_RUNTIME=cli make -C pmoves up && make -C pmoves smoke
```

## Notes

- Supabase CLI must be running first: `make -C pmoves supa-start`
- Bootstrap data: `make -C pmoves bootstrap-data`
- Monitoring: `make -C pmoves up-monitoring`
- Use `/health` after bring-up to verify
