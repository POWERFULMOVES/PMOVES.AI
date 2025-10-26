import plotly.graph_objects as go
import plotly.io as pio

# Data from the provided JSON
data = {
    "AI-Enhanced Local Service Business": {"2025": 155.0, "2026": 384.8, "2027": 715.8, "2028": 1181.1, "2029": 1821.0},
    "Sustainable Energy AI Consulting": {"2025": 130.0, "2026": 314.2, "2027": 568.1, "2028": 910.6, "2029": 1363.2},
    "Community Token Pre-Order System": {"2025": 105.0, "2026": 239.7, "2027": 409.2, "2028": 618.9, "2029": 874.6},
    "Creative Content + Token Rewards": {"2025": 105.0, "2026": 239.7, "2027": 409.2, "2028": 618.9, "2029": 874.6}
}

# Brand colors in order
colors = ['#1FB8CD', '#DB4545', '#2E8B57', '#5D878F']

# Create figure
fig = go.Figure()

# Years for x-axis
years = [2025, 2026, 2027, 2028, 2029]

# Abbreviated model names for legend (keeping under reasonable length)
model_names = {
    "AI-Enhanced Local Service Business": "AI Local Service",
    "Sustainable Energy AI Consulting": "Energy AI Consult",
    "Community Token Pre-Order System": "Token Pre-Order",
    "Creative Content + Token Rewards": "Content + Tokens"
}

# Add traces for each business model
for i, (full_name, model_data) in enumerate(data.items()):
    roi_values = [model_data[str(year)] for year in years]
    
    fig.add_trace(go.Scatter(
        x=years,
        y=roi_values,
        mode='lines+markers',
        name=model_names[full_name],
        line=dict(color=colors[i], width=3),
        marker=dict(size=8)
    ))

# Update layout
fig.update_layout(
    title="5-Year ROI Growth by Model",
    xaxis_title="Year",
    yaxis_title="ROI %",
    legend=dict(orientation='h', yanchor='bottom', y=1.05, xanchor='center', x=0.5)
)

# Update traces
fig.update_traces(cliponaxis=False)

# Save the chart
fig.write_image("roi_growth_chart.png")