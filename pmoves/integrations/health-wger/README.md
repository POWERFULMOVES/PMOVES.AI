# Health – Wger n8n Flows

Drop exported n8n workflow JSON files in `n8n/flows/`. The integration watcher and import scripts
mount this directory and sync any `*.json` updates into the local n8n instance when the integrations
compose profiles are running.
