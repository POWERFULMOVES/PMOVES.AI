# Visualization Prompt — Enterprise ROI by Resident Background

## Purpose
Provide a text blueprint for the grouped horizontal bar chart that highlights ROI and retention across demographic-led enterprise models.

## Data Source
- Script: `chart_script.py`
- CSV inputs: `community_economic_impact.csv`, `resident_upskilling_analysis.csv`, `resource_allocation_by_background.csv`

## Regeneration Options
1. **Plotly rebuild**  
   `python "CATACLYSM_STUDIOS_INC/ABOUT/notes/Community Wealth Building Through Diverse Resident/chart_script.py"`  
   Restores `enterprise_roi_chart.png`
2. **Creator pipeline prompt**  
   ```
   Craft a horizontal grouped bar visualization comparing enterprise ROI across resident backgrounds: Recent Immig, Single Parents, Young Adults, Displaced Work, Retirees, College Stud. 
   Each group contains two initiatives labeled with abbreviations (e.g., Cultural Coop, Translation Hub) and displays ROI percentages as bar lengths. 
   Overlay white retention percentages inside the bars, keep Cataclysm palette accents, and float a centered legend aligning colors to background groups.
   ```

## Notes
- Encourage designers to reference the CSVs for exact ROI/retention values when rendering magazine-ready art.
