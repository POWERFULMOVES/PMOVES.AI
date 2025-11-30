import plotly.graph_objects as go
import pandas as pd

# Prepare the data
data = {
    "Recent Immigrants": {
        "Cultural Food Cooperative + Token Pre-Orders": {"ROI": 5159.8, "Retention": 0.85},
        "Multicultural Translation & Content Hub": {"ROI": 6842.4, "Retention": 0.75}
    },
    "Single Parents": {
        "Childcare Cooperative + Flexible Work Tokens": {"ROI": 6038.6, "Retention": 0.90},
        "Home Services Collective": {"ROI": 8260.0, "Retention": 0.80}
    },
    "Young Adults (18-25)": {
        "Digital Content Creator Collective": {"ROI": 7992.3, "Retention": 0.70},
        "Urban Agriculture + Tech Collective": {"ROI": 3651.7, "Retention": 0.88}
    },
    "Displaced Workers": {
        "Skilled Trades Cooperative + AI Matching": {"ROI": 5469.2, "Retention": 0.85},
        "Manufacturing Skills Training Hub": {"ROI": 2945.7, "Retention": 0.75}
    },
    "Retirees/Semi-Retired": {
        "Wisdom & Crafts Marketplace": {"ROI": 5663.6, "Retention": 0.95},
        "Community Knowledge Bank": {"ROI": 6397.4, "Retention": 0.85}
    },
    "Community College Students": {
        "Student Innovation Lab + Token Research": {"ROI": 4308.0, "Retention": 0.80},
        "Peer Learning Network": {"ROI": 6397.4, "Retention": 0.85}
    }
}

# Model name abbreviations (15 char limit)
model_abbreviations = {
    "Cultural Food Cooperative + Token Pre-Orders": "Cultural Coop",
    "Multicultural Translation & Content Hub": "Translation Hub",
    "Childcare Cooperative + Flexible Work Tokens": "Childcare Coop", 
    "Home Services Collective": "Home Services",
    "Digital Content Creator Collective": "Content Creator",
    "Urban Agriculture + Tech Collective": "Urban Ag+Tech",
    "Skilled Trades Cooperative + AI Matching": "Skilled Trades",
    "Manufacturing Skills Training Hub": "Mfg Skills Hub",
    "Wisdom & Crafts Marketplace": "Wisdom & Crafts",
    "Community Knowledge Bank": "Knowledge Bank",
    "Student Innovation Lab + Token Research": "Innovation Lab",
    "Peer Learning Network": "Peer Learning"
}

# Background abbreviations (15 char limit)
background_abbreviations = {
    "Recent Immigrants": "Recent Immig",
    "Single Parents": "Single Parents", 
    "Young Adults (18-25)": "Young Adults",
    "Displaced Workers": "Displaced Work",
    "Retirees/Semi-Retired": "Retirees",
    "Community College Students": "College Stud"
}

# Colors for each background group
colors = ['#1FB8CD', '#DB4545', '#2E8B57', '#5D878F', '#D2BA4C', '#B4413C']

fig = go.Figure()

# Create grouped bar chart structure
all_models = []
all_rois = []
all_retentions = []
all_backgrounds = []
group_positions = []
group_labels = []

current_pos = 0
for i, (background, models) in enumerate(data.items()):
    background_abbrev = background_abbreviations[background]
    
    # Add spacing between groups
    if i > 0:
        current_pos += 1
    
    for j, (model, metrics) in enumerate(models.items()):
        model_abbrev = model_abbreviations[model]
        all_models.append(model_abbrev)
        all_rois.append(metrics['ROI'])
        all_retentions.append(metrics['Retention'])
        all_backgrounds.append(background)
        
        group_positions.append(current_pos)
        group_labels.append(model_abbrev)
        current_pos += 1

# Create traces for each background group
background_list = list(data.keys())
for i, background in enumerate(background_list):
    background_abbrev = background_abbreviations[background]
    
    # Get data for this background
    bg_models = []
    bg_rois = []
    bg_retentions = []
    bg_positions = []
    
    for j, bg in enumerate(all_backgrounds):
        if bg == background:
            bg_models.append(all_models[j])
            bg_rois.append(all_rois[j])
            bg_retentions.append(all_retentions[j])
            bg_positions.append(group_positions[j])
    
    fig.add_trace(go.Bar(
        x=bg_rois,
        y=bg_positions,
        orientation='h',
        name=background_abbrev,
        marker_color=colors[i],
        text=[f"{ret:.0%}" for ret in bg_retentions],
        textposition='inside',
        textfont=dict(color='white', size=11),
        hovertemplate='<b>%{customdata}</b><br>ROI: %{x:.0f}%<br>Retention: %{text}<extra></extra>',
        customdata=bg_models
    ))

fig.update_traces(cliponaxis=False)

fig.update_layout(
    title='5-Year ROI by Enterprise Model',
    xaxis_title='ROI (%)',
    yaxis_title='Model',
    yaxis=dict(
        tickmode='array',
        tickvals=group_positions,
        ticktext=group_labels,
        tickfont=dict(size=10)
    ),
    legend=dict(
        orientation='h',
        yanchor='bottom',
        y=1.05,
        xanchor='center',
        x=0.5
    ),
    barmode='group'
)

# Format x-axis to show values properly
fig.update_xaxes(
    tickformat=',.0f',
    ticksuffix='%'
)

fig.write_image('enterprise_roi_chart.png')