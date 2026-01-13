# Visualization Prompt — 5-Year ROI Growth

## Purpose
Document how to recreate the five-year ROI line chart that compares Cataclysm Studios’ priority business models without storing the rendered PNG.

## Data Source
- Script: `chart_script.py`
- Input data: `ai_tokenomics_business_projections.csv`
- Color palette: Cataclysm cyan (`#1FB8CD`), ember red (`#DB4545`), forest green (`#2E8B57`), slate blue (`#5D878F`)

## Regeneration Options
1. **Rebuild with Plotly**  
   `python "CATACLYSM_STUDIOS_INC/ABOUT/notes/5-Year Business Projections_ AI - Tokenomics Model/chart_script.py"`  
   Output file: `roi_growth_chart.png`
2. **Creator pipeline prompt**  
   ```
   Render a high-tech line chart on a dark canvas comparing five-year ROI projections between four Cataclysm Studios community business models: AI Local Service, Energy AI Consulting, Token Pre-Order, and Content + Tokens.  
   Use brand colors #1FB8CD, #DB4545, #2E8B57, #5D878F with glowing markers, years 2025-2029 on the x-axis, ROI percentages rising on the y-axis, and a horizontal legend centered above the plot. 
   Emphasize rapid compounding growth toward 2029.
   ```

## Notes
- Update the prompt numbers or labels whenever the CSV assumptions change.
- Tag regenerated assets with the execution date in `notes/CHART_REGEN_LOG.md` (create if needed).
