# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - link "Skip to main content" [ref=e2] [cursor=pointer]:
    - /url: "#main-content"
  - alert [ref=e3]
  - alert [ref=e4]:
    - generic [ref=e5]:
      - generic [ref=e7]: "!"
      - heading "Something went wrong" [level=1] [ref=e8]
      - paragraph [ref=e9]: "SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) is not configured. Run `make supa-start` + `make supa-status` and sync the values into pmoves/.env.local."
      - button "Try again" [ref=e10] [cursor=pointer]
```