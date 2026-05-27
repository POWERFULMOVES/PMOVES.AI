---
name: claude-d3js
description: Generate D3.js data visualizations (charts, graphs, networks, geographic maps). Use when the user asks to visualize data, render a graph/chart, or build an interactive viz. Sourced from skills/Pmoves-claude-d3js-skill/ (fork of chrisvoncsefalvay/claude-d3js-skill).
---

# Claude-D3.js Skill (Activation Pointer)

This skill is sourced from `skills/Pmoves-claude-d3js-skill/`. Read that submodule's `SKILL.md` for full usage.

## Why activated for PMOVES.AI

Multiple PMOVES surfaces want visualization: CHIT trail graphs, NATS subject topology, GEOMETRY_BUS dimensions, Hyperdim renderers, FlOO$ DAG layouts. D3.js is the lowest-common-denominator client-side renderer.

## When Claude should invoke

- User asks for a chart, graph, network diagram, or geo map.
- A response would be clearer as an interactive viz than a table.
- Generating one-off SVG/HTML for `pmoves/ui/` components.

## Cross-references

- `hyperdim:render` / `hyperdim:animate` — PMOVES-native hyperdimensional renderer.
- `chit:visualize` — CHIT trail visualizer.
- `playground:playground` — interactive HTML explorer skill (often pairs with this one).
