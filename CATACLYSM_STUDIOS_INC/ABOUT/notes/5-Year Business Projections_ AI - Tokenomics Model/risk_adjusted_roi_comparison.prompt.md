# Visualization Prompt — Risk-Adjusted ROI Comparison (2029)

## Purpose
Capture the logic for the horizontal bar chart ranking 2029 risk-adjusted ROI by business model, replacing the binary export with reproducible instructions.

## Data Source
- Script: `chart_script_1.py`
- Inputs: `business_model_summary_2029.csv` (derived from `ai_tokenomics_business_projections.csv`)
- Color legend keyed to investment tiers (`$3k`, `$4k`, `$5k`) using brand hues.

## Regeneration Options
1. **Scripted chart**  
   `python "CATACLYSM_STUDIOS_INC/ABOUT/notes/5-Year Business Projections_ AI - Tokenomics Model/chart_script_1.py"`  
   Generates `risk_adjusted_roi_comparison.png`
2. **Creator pipeline prompt**  
   ```
   Produce a horizontal bar chart on a charcoal background ranking eight Cataclysm Studios community business models by risk-adjusted ROI for 2029. 
   Group bars by investment tier: $5k in deep navy (#13343B), $4k in medium slate (#5D878F), $3k in bright cyan (#1FB8CD). 
   Include concise labels such as "AI Local Svc", "Energy AI", "Content Tokens". 
   Place value callouts inside the bars and keep the legend centered above the plot.
   ```

## Notes
- If investment tiers or palette shift, mirror those changes both in the script and the prompt.
