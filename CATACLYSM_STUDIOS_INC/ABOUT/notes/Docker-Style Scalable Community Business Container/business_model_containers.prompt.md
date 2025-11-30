# Visualization Prompt — Deploy Business Containers

## Purpose
Translate the “Deploy Business Containers” bubble grid into a reusable brief for motion graphics or static hero art once the ROI projections and scripts inside this folder are validated.

## Data Source
- Generated from `chart_script.py` using metrics in `docker_container_business_models.csv`.
- Underlying assumptions documented across the accompanying CSVs (investment, monthly profit, ROI, and community savings).

## Regeneration Options
1. **Plotly rerender**  
   Activate the project virtualenv and run:  
   `python "CATACLYSM_STUDIOS_INC/ABOUT/notes/Docker-Style Scalable Community Business Container/chart_script.py"`  
   The script will recreate the original scatter grid as `business_model_containers.png`.
2. **Creator pipeline prompt**  
   ```
   Design a 2x3 grid infographic showing six shipping-container style business pods. 
   Each pod has a distinct Cataclysm Studios brand color (#1FB8CD, #DB4545, #2E8B57, #5D878F, #D2BA4C, #B4413C) and displays its label: 
   Bulk Purchase Delivery, Shuttle Transport, Food Hub Delivery, Tool & Equipment Share, Repair & Maintenance Mobile, Childcare Collective. 
   Overlay subtle callouts indicating scale multipliers (1x, 2x, 3x) with investment, monthly profit, ROI %, and community savings values. 
   Style the scene like a systems blueprint: dark background grid, glowing outlines, clean sans-serif typography.
   ```

## Notes
- Keep this prompt near the scripts so designers can regenerate visuals without committing binary blobs.
- Update investment or ROI numbers inside the prompt whenever the CSV inputs change.
