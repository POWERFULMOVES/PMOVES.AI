import pandas as pd
import plotly.graph_objects as go

# Data processing
data = {
    "Security-Delivery-Hub": {"1x": {"ROI": 204.0, "Investment": 25000, "Community_Impact": 636636, "Payback": 5.0}, "3x": {"ROI": 235.3, "Investment": 55000, "Community_Impact": 1599240, "Payback": 5.1}, "5x": {"ROI": 336.0, "Investment": 85000, "Community_Impact": 2382720, "Payback": 3.6}, "10x": {"ROI": 524.3, "Investment": 160000, "Community_Impact": 6999240, "Payback": 2.3}},
    "Bulk-Purchase-Cooperative": {"1x": {"ROI": 123.0, "Investment": 15000, "Community_Impact": 372744, "Payback": 9.7}, "3x": {"ROI": 141.9, "Investment": 31000, "Community_Impact": 936588, "Payback": 8.5}, "5x": {"ROI": 202.9, "Investment": 47000, "Community_Impact": 1396800, "Payback": 5.9}, "10x": {"ROI": 502.4, "Investment": 87000, "Community_Impact": 5035392, "Payback": 2.4}},
    "Community-Shuttle-Network": {"1x": {"ROI": 164.6, "Investment": 35000, "Community_Impact": 867648, "Payback": 7.3}, "3x": {"ROI": 189.7, "Investment": 75000, "Community_Impact": 2179440, "Payback": 6.3}, "5x": {"ROI": 400.7, "Investment": 115000, "Community_Impact": 3345408, "Payback": 3.0}, "10x": {"ROI": 629.6, "Investment": 215000, "Community_Impact": 9827136, "Payback": 1.9}},
    "Token-Rewards-Platform": {"1x": {"ROI": 216.0, "Investment": 12000, "Community_Impact": 253440, "Payback": 5.6}, "3x": {"ROI": 421.2, "Investment": 24000, "Community_Impact": 628992, "Payback": 2.8}, "5x": {"ROI": 576.0, "Investment": 36000, "Community_Impact": 1290240, "Payback": 2.1}, "10x": {"ROI": 922.9, "Investment": 66000, "Community_Impact": 3790080, "Payback": 1.3}},
    "Neighborhood-Food-Hub": {"1x": {"ROI": 190.0, "Investment": 18000, "Community_Impact": 506952, "Payback": 6.3}, "3x": {"ROI": 219.1, "Investment": 42000, "Community_Impact": 1273104, "Payback": 5.5}, "5x": {"ROI": 414.5, "Investment": 66000, "Community_Impact": 2677632, "Payback": 2.9}, "10x": {"ROI": 637.9, "Investment": 126000, "Community_Impact": 7865544, "Payback": 1.9}}
}

# Create figure
fig = go.Figure()

# Colors as specified
colors = ['#1FB8CD', '#DB4545', '#2E8B57', '#5D878F', '#D2BA4C']

scales = [1, 3, 5, 10]
business_types = list(data.keys())

# Abbreviate business type names to fit 15 char limit
short_names = {
    "Security-Delivery-Hub": "Security Hub",
    "Bulk-Purchase-Cooperative": "Bulk Coop", 
    "Community-Shuttle-Network": "Shuttle Net",
    "Token-Rewards-Platform": "Token Platform",
    "Neighborhood-Food-Hub": "Food Hub"
}

for i, business_type in enumerate(business_types):
    roi_values = [data[business_type][f"{scale}x"]["ROI"] for scale in scales]
    investment_values = [data[business_type][f"{scale}x"]["Investment"]/1000 for scale in scales]  # Convert to k
    payback_values = [data[business_type][f"{scale}x"]["Payback"] for scale in scales]
    
    fig.add_trace(go.Scatter(
        x=scales,
        y=roi_values,
        mode='lines+markers',
        name=short_names[business_type],
        line=dict(color=colors[i % len(colors)], width=3),
        marker=dict(size=8),
        hovertemplate='<b>%{fullData.name}</b><br>' +
                     'Scale: %{x}x<br>' +
                     'ROI: %{y}%<br>' +
                     'Investment: $%{customdata[0]}k<br>' +
                     'Payback: %{customdata[1]} yrs' +
                     '<extra></extra>',
        customdata=list(zip(investment_values, payback_values))
    ))

fig.update_layout(
    title="ROI Scaling by Container Type",
    xaxis_title="Scale Factor",
    yaxis_title="ROI (%)",
    legend=dict(orientation='h', yanchor='bottom', y=1.05, xanchor='center', x=0.5)
)

fig.update_traces(cliponaxis=False)
fig.update_xaxes(tickvals=[1, 3, 5, 10], ticktext=['1x', '3x', '5x', '10x'])

fig.write_image("roi_scaling_chart.png")