sequenceDiagram
    participant Webhook as External Webhook
    participant n8n as n8n Flow
    participant Supabase as Supabase REST
    participant Gateway as HiRAG Gateway
    participant PostgREST as PostgREST/View

    rect rgb(220,235,255)
    note over Webhook,n8n: Creator output → CGP pipeline (webhook)
    end

    Webhook->>n8n: POST creative payload
    n8n->>n8n: Prepare Records (validate, build studio_row)
    n8n->>Supabase: INSERT/UPSERT studio_row
    Supabase-->>n8n: studio_board_id
    n8n->>n8n: Map to CGP (constellation + points)
    n8n->>Gateway: POST /geometry/event (CGP envelope)
    Gateway->>PostgREST: geometry_cgp_v1 (viewable)
