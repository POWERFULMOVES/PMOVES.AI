# Mermaid Diagram Fixes (October 2, 2025)

Scope: pmoves/docs/pmoves_enhanced_diagrams.md, pmoves/docs/PMOVES_Enhanced_Visual_Architecture_Diagrams.md

Summary
- Replaced unsupported multi-source edge shorthand (e.g., `A & B --> C`) with explicit edges.
- Converted `mindmap` diagrams to widely supported flowcharts. Preserved the original mindmap blocks but fenced them as `text` so they render as code (no Mermaid parsing errors).

Details
- In “Data Processing Pipeline” diagrams, expanded:
  - `A1 & A2 & A3 --> B1` to individual lines `A1 --> B1`, `A2 --> B1`, `A3 --> B1`.
  - `C1 & C2 --> B3` to `C1 --> B3` and `C2 --> B3`.
  - `B3 --> D1 & D2 & D3` to separate `B3 --> D1`, `B3 --> D2`, `B3 --> D3`.
- In “Deployment Architecture” diagrams, expanded:
  - `WS1 & WS2 & WS3 --> SB` and `... --> N8N` to one edge per workstation.
  - `ED1 & ED2 --> LLM2` and `... --> CV` to one edge per edge device.
  - `WS2 & WS3 --> LLM1` to one edge per workstation.

Rationale
- Some Mermaid renderers (including GitHub’s) do not support the multi-source edge shorthand, which caused parse errors. Explicit edges are universally supported in Mermaid v9+ and v10.
- Mermaid `mindmap` is not supported by many renderers. Flowcharts (`graph TD`) are broadly compatible and easy to read.

Known Follow-ups
- If you prefer to remove the preserved `text`-fenced mindmap blocks entirely, let me know and I’ll delete them to reduce noise.

Reviewer Notes
- No content meaning was changed—only syntax made compatible.
