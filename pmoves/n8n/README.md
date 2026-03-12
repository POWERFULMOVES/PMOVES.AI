# PMOVES n8n Mirror

`pmoves/n8n/flows/` is now a compatibility mirror.

Canonical n8n workflow ownership lives in [`PMOVES-n8n/workflows/`](../../PMOVES-n8n/workflows). The parent repo keeps this mirror so older docs, UI links, and operator muscle memory do not break during the transition.

Canonical edit path:

```bash
make -C pmoves n8n-sync-submodule-flows
make -C pmoves n8n-import-flows
make -C pmoves n8n-activate-flows
```
