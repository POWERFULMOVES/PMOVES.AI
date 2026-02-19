import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# Data for the containerized business models
data = {
    "Bulk-Purchase-Delivery": {"Investment": 8000, "Monthly_Profit": 8800, "ROI": 1320.0, "Community_Savings": 24000},
    "Shuttle-Transport": {"Investment": 15000, "Monthly_Profit": 17800, "ROI": 1424.0, "Community_Savings": 24000},
    "Food-Hub-Delivery": {"Investment": 3000, "Monthly_Profit": 19200, "ROI": 7680.0, "Community_Savings": 36000},
    "Tool-Equipment-Share": {"Investment": 5000, "Monthly_Profit": 800, "ROI": 192.0, "Community_Savings": 240000},
    "Repair-Maintenance-Mobile": {"Investment": 6000, "Monthly_Profit": 1900, "ROI": 380.0, "Community_Savings": 57600},
    "Childcare-Collective": {"Investment": 4000, "Monthly_Profit": 3000, "ROI": 900.0, "Community_Savings": 108000}
}

# Brand colors
colors = ['#1FB8CD', '#DB4545', '#2E8B57', '#5D878F', '#D2BA4C', '#B4413C']

# Create grid positions for containers (2x3 grid)
grid_positions = [(0, 2), (1, 2), (2, 2), (0, 1), (1, 1), (2, 1)]

# Create data for plotting
plot_data = []
model_names = list(data.keys())

for i, (model_name, metrics) in enumerate(data.items()):
    x_pos, y_pos = grid_positions[i]
    
    # Create short name for display
    short_name = model_name.replace('-', ' ')
    if len(short_name) > 15:
        parts = short_name.split(' ')
        short_name = parts[0][:15]
    
    # Scale factors for deployment scaling
    for scale_idx, scale in enumerate([1, 2, 3]):
        scaled_investment = metrics['Investment'] * scale
        scaled_profit = metrics['Monthly_Profit'] * scale
        scaled_savings = metrics['Community_Savings'] * scale
        
        # Position containers with slight offset for scaling
        x_offset = scale_idx * 0.15
        y_offset = scale_idx * 0.05
        
        # Format numbers with k/m abbreviations
        inv_str = f"{scaled_investment/1000:.0f}k" if scaled_investment >= 1000 else str(scaled_investment)
        profit_str = f"{scaled_profit/1000:.0f}k" if scaled_profit >= 1000 else str(scaled_profit)
        savings_str = f"{scaled_savings/1000:.0f}k" if scaled_savings >= 1000 else str(scaled_savings)
        
        hover_text = f"<b>{short_name}</b><br>" + \
                    f"Scale: {scale}x<br>" + \
                    f"Invest: ${inv_str}<br>" + \
                    f"Profit: ${profit_str}<br>" + \
                    f"ROI: {metrics['ROI']:.0f}%<br>" + \
                    f"Savings: ${savings_str}"
        
        plot_data.append({
            'x': x_pos + x_offset,
            'y': y_pos + y_offset,
            'model': short_name,
            'scale': f"{scale}x",
            'roi': metrics['ROI'],
            'investment': scaled_investment,
            'profit': scaled_profit,
            'savings': scaled_savings,
            'color': colors[i],
            'hover_text': hover_text,
            'size': min(max(scaled_profit / 1000, 20), 80)  # Size based on profit
        })

# Create DataFrame
df = pd.DataFrame(plot_data)

# Create the figure
fig = go.Figure()

# Add traces for each model (to show in legend)
for i, model_name in enumerate(model_names):
    short_name = model_name.replace('-', ' ')
    if len(short_name) > 15:
        parts = short_name.split(' ')
        short_name = parts[0][:15]
    
    model_data = df[df['model'] == short_name]
    
    fig.add_trace(go.Scatter(
        x=model_data['x'],
        y=model_data['y'],
        mode='markers',
        name=short_name,
        marker=dict(
            color=colors[i],
            size=model_data['size'],
            symbol='square',
            line=dict(color='white', width=2)
        ),
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=model_data['hover_text'],
        cliponaxis=False
    ))

# Update layout
fig.update_layout(
    title="Deploy Business Containers",
    xaxis_title="Container Grid",
    yaxis_title="Deploy Scale",
    legend=dict(orientation='h', yanchor='bottom', y=1.05, xanchor='center', x=0.5),
    showlegend=True
)

# Update axes to show grid-like appearance
fig.update_xaxes(
    tickmode='array',
    tickvals=[0, 1, 2],
    ticktext=['Col 1', 'Col 2', 'Col 3'],
    range=[-0.5, 2.8]
)

fig.update_yaxes(
    tickmode='array',
    tickvals=[1, 2],
    ticktext=['Row 1', 'Row 2'],
    range=[0.5, 2.5]
)

# Update traces
fig.update_traces(cliponaxis=False)

# Save the chart
fig.write_image("business_model_containers.png", width=800, height=600, scale=2)