import plotly.graph_objects as go
import plotly.express as px

# Data from the provided JSON
data = {
    "AI-Enhanced Local Service Business": {"Risk_Adjusted_ROI": 1365.75, "Investment": 5000},
    "Sustainable Energy AI Consulting": {"Risk_Adjusted_ROI": 817.92, "Investment": 4000},
    "Community Token Pre-Order System": {"Risk_Adjusted_ROI": 349.84, "Investment": 3000},
    "Creative Content + Token Rewards": {"Risk_Adjusted_ROI": 349.84, "Investment": 3000},
    "Local Food Network with Tokens": {"Risk_Adjusted_ROI": 349.84, "Investment": 3000},
    "AI Tutoring + Community Currency": {"Risk_Adjusted_ROI": 349.84, "Investment": 3000},
    "Digital Art Creation + NFT Tokens": {"Risk_Adjusted_ROI": 349.84, "Investment": 3000},
    "Urban Agriculture + Token Economy": {"Risk_Adjusted_ROI": 349.84, "Investment": 3000}
}

# Prepare data for plotting
business_models = []
roi_values = []
investments = []

# Color mapping for investment tiers (using brand colors as specified)
color_map = {
    3000: '#1FB8CD',  # Strong cyan (light blue)
    4000: '#5D878F',  # Cyan (medium blue) 
    5000: '#13343B'   # Dark cyan (navy blue)
}

# Investment tier labels for legend
tier_labels = {
    3000: '$3k Tier',
    4000: '$4k Tier', 
    5000: '$5k Tier'
}

# Sort by ROI descending for better visualization
sorted_data = sorted(data.items(), key=lambda x: x[1]['Risk_Adjusted_ROI'], reverse=True)

for model, values in sorted_data:
    # Clearer abbreviations within 15 char limit
    if model == "AI-Enhanced Local Service Business":
        short_name = "AI Local Svc"
    elif model == "Sustainable Energy AI Consulting":
        short_name = "Energy AI"
    elif model == "Community Token Pre-Order System":
        short_name = "Token PreOrder"
    elif model == "Creative Content + Token Rewards":
        short_name = "Content Tokens"
    elif model == "Local Food Network with Tokens":
        short_name = "Food Network"
    elif model == "AI Tutoring + Community Currency":
        short_name = "AI Tutoring"
    elif model == "Digital Art Creation + NFT Tokens":
        short_name = "Digital Art"
    elif model == "Urban Agriculture + Token Economy":
        short_name = "Urban Farming"
    
    business_models.append(short_name)
    roi_values.append(values['Risk_Adjusted_ROI'])
    investments.append(values['Investment'])

# Create horizontal bar chart with separate traces for each investment tier
fig = go.Figure()

# Add bars for each investment tier separately to create proper legend
for investment_tier in sorted(set(investments), reverse=True):  # Sort tiers high to low
    # Filter data for this investment tier
    tier_models = []
    tier_rois = []
    
    for i, inv in enumerate(investments):
        if inv == investment_tier:
            tier_models.append(business_models[i])
            tier_rois.append(roi_values[i])
    
    if tier_models:  # Only add if there are models for this tier
        fig.add_trace(go.Bar(
            x=tier_rois,
            y=tier_models,
            orientation='h',
            marker_color=color_map[investment_tier],
            name=tier_labels[investment_tier],
            text=[f"{roi:.1f}" for roi in tier_rois],  # Show one decimal place
            textposition='inside',
            textfont=dict(color='white', size=11),
            showlegend=True
        ))

fig.update_traces(cliponaxis=False)

fig.update_layout(
    title="Risk-Adj ROI 2029",
    xaxis_title="ROI",
    yaxis_title="Business Model",
    legend=dict(orientation='h', yanchor='bottom', y=1.05, xanchor='center', x=0.5)
)

fig.update_xaxes(tickformat='.0f')
fig.update_yaxes(categoryorder='total ascending')  # Order by ROI value

# Save the chart
fig.write_image("risk_adjusted_roi_comparison.png")