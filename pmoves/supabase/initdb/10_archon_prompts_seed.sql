-- Minimal default prompts for Archon.
-- Keeps initial UX functional without pulling the full upstream seed set.

insert into archon_prompts (prompt_name, prompt, description)
values
  (
    'status.sync',
    'Summarize the latest crawl or ingest task in under 3 sentences. Highlight blockers and the next action if one exists.',
    'Default status update prompt for Archon dashboards'
  ),
  (
    'discovery.kickoff',
    'Ask up to three clarifying questions that help scope a new content crawl. Reference any supplied metadata. Close by restating what you will deliver once answers arrive.',
    'Lightweight discovery prompt used when spinning up new crawls'
  )
on conflict (prompt_name) do update
set
  prompt = excluded.prompt,
  description = excluded.description,
  updated_at = timezone('utc', now());
