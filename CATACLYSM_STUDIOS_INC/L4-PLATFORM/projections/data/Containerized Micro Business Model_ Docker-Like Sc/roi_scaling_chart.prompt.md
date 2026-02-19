# Visualization Prompt — ROI Scaling by Container Type

## Purpose
Describe how to recreate the multi-line chart comparing ROI across deployment scales (1×, 3×, 5×, 10×) for each containerized business archetype.

## Data Source
- Script: `chart_script.py`
- Dataset: `micro_business_container_scaling.csv` plus associated CSVs for investment, impact, and payback metrics.

## Regeneration Options
1. **Plotly reproduction**  
   `python "CATACLYSM_STUDIOS_INC/ABOUT/notes/Containerized Micro Business Model_ Docker-Like Sc/chart_script.py"`  
   Outputs `roi_scaling_chart.png`
2. **Creator pipeline prompt**  
   ```
   Illustrate a neon line chart with four scale markers (1x, 3x, 5x, 10x) on the x-axis and ROI percentage on the y-axis. 
   Draw five lines labeled Security Hub, Bulk Coop, Shuttle Net, Token Platform, Food Hub using Cataclysm brand colors. 
   Add tooltip-style callouts hinting at investment levels (in $k) and payback periods for each point. 
   Keep the legend horizontal above the chart and use a dark, futuristic background grid.
   ```

## Notes
- Adjust model names and color assignments to match any future CSV updates.
