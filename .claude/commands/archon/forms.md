Manage agent forms in Supabase via Archon's API.

Archon manages agent registration forms that define agent capabilities, parameters, and Supabase-backed state. This command provides access to browse and inspect agent form configurations.

## Usage

Run this command to:
- List registered agent forms
- View form field definitions and validation rules
- Check agent registration status
- Inspect form submission history

## Implementation

Execute the following steps:

1. **Check Archon health first:**
   ```bash
   curl -sf http://localhost:8091/healthz | jq .status
   ```

   If not healthy, inform user and stop.

2. **List agent forms:**
   ```bash
   curl -sf http://localhost:8091/api/forms | jq '.[] | {id, name, agent_type, status}'
   ```

   Shows all registered agent forms and their states.

3. **Get form details (if user provides ID):**
   ```bash
   curl -sf "http://localhost:8091/api/forms/<form_id>" | jq .
   ```

   Shows field definitions, validation rules, and default values.

4. **List form submissions (if user requests):**
   ```bash
   curl -sf "http://localhost:8091/api/forms/<form_id>/submissions" | jq '.[] | {id, status, submitted_at}'
   ```

5. **Report results to user:**
   - Number of registered forms
   - Form names and agent types
   - Field details if specific form requested

## Notes

- Agent forms are stored in Supabase
- Forms define the contract between Archon and Agent Zero
- Archon API: `http://localhost:8091`
- Archon UI for visual form management: `http://localhost:3737`
- Form data flows: Archon (form) -> Agent Zero (MCP execute) -> Task result
