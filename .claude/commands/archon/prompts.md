List and query Archon-managed prompt templates stored in Supabase.

Archon manages prompt templates and agent configurations in Supabase. This command provides access to browse, search, and inspect prompt templates.

## Usage

Run this command to:
- List all available prompt templates
- Search for prompts by name or tag
- View prompt template details and variables
- Check which agents use specific prompts

## Implementation

Execute the following steps:

1. **Check Archon health first:**
   ```bash
   curl -sf http://localhost:8091/healthz | jq .status
   ```

   If not healthy, inform user and stop.

2. **List prompt templates:**
   ```bash
   curl -sf http://localhost:8091/api/prompts | jq '.[] | {id, name, tags, updated_at}'
   ```

   Displays all registered prompt templates with their metadata.

3. **Search for specific prompt (if user provides query):**
   ```bash
   curl -sf "http://localhost:8091/api/prompts?search=<query>" | jq .
   ```

4. **Get prompt details (if user provides ID):**
   ```bash
   curl -sf "http://localhost:8091/api/prompts/<prompt_id>" | jq .
   ```

   Shows full template content, variables, and usage metadata.

5. **Report results to user:**
   - Number of prompt templates found
   - Template names and descriptions
   - Relevant template details if searched

## Notes

- Prompts are stored in Supabase `archon_prompts` table
- Template variables use `{{variable_name}}` syntax
- Archon API: `http://localhost:8091`
- Archon UI for visual editing: `http://localhost:3737`
