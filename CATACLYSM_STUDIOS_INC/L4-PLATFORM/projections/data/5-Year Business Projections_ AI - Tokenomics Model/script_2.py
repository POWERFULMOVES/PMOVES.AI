# Create scenario analysis and market condition impacts
import pandas as pd
import numpy as np

# Scenario analysis for different market conditions
print("=== DETAILED SCENARIO ANALYSIS ===")

base_models = [
    {"name": "AI-Enhanced Local Service Business", "base_roi": 1821.0, "success_prob": 0.75, "investment": 5000},
    {"name": "Sustainable Energy AI Consulting", "base_roi": 1363.2, "success_prob": 0.60, "investment": 4000},
    {"name": "Community Token Pre-Order System", "base_roi": 874.6, "success_prob": 0.40, "investment": 3000},
    {"name": "Creative Content + Token Rewards", "base_roi": 874.6, "success_prob": 0.40, "investment": 3000}
]

scenarios = {
    'Bull Market + High AI Adoption': {'roi_mult': 1.5, 'success_boost': 0.20, 'probability': 0.25},
    'Normal Growth': {'roi_mult': 1.0, 'success_boost': 0.0, 'probability': 0.50},
    'Economic Downturn': {'roi_mult': 0.6, 'success_boost': -0.25, 'probability': 0.20},
    'Crypto Winter + AI Skepticism': {'roi_mult': 0.4, 'success_boost': -0.35, 'probability': 0.05}
}

scenario_analysis = []

for model in base_models:
    for scenario_name, params in scenarios.items():
        adj_roi = model['base_roi'] * params['roi_mult']
        adj_success = max(0.1, min(0.95, model['success_prob'] + params['success_boost']))
        risk_adj_roi = adj_roi * adj_success
        expected_value = risk_adj_roi * params['probability']
        
        scenario_analysis.append({
            'Business_Model': model['name'],
            'Scenario': scenario_name,
            'Scenario_Probability': params['probability'],
            'Adjusted_ROI': round(adj_roi, 1),
            'Adjusted_Success_Rate': round(adj_success, 2),
            'Risk_Adjusted_ROI': round(risk_adj_roi, 1),
            'Expected_Value': round(expected_value, 1),
            'Investment_Required': model['investment']
        })

scenario_df = pd.DataFrame(scenario_analysis)

# Show expected values by model
print("Expected Value Analysis (Probability-Weighted Returns):")
expected_values = scenario_df.groupby('Business_Model')['Expected_Value'].sum().round(1).sort_values(ascending=False)
print(expected_values.to_string())

# Break-even analysis
print("\n=== BREAK-EVEN ANALYSIS ===")
breakeven_data = []

for model in base_models:
    # Calculate time to break-even based on different success scenarios
    monthly_profit_optimistic = (model['base_roi'] * model['investment'] / 100) / 60  # 5 years = 60 months
    monthly_profit_realistic = monthly_profit_optimistic * 0.7
    monthly_profit_conservative = monthly_profit_optimistic * 0.4
    
    breakeven_optimistic = model['investment'] / monthly_profit_optimistic if monthly_profit_optimistic > 0 else float('inf')
    breakeven_realistic = model['investment'] / monthly_profit_realistic if monthly_profit_realistic > 0 else float('inf')
    breakeven_conservative = model['investment'] / monthly_profit_conservative if monthly_profit_conservative > 0 else float('inf')
    
    breakeven_data.append({
        'Business_Model': model['name'],
        'Investment': model['investment'],
        'Breakeven_Optimistic_Months': round(breakeven_optimistic, 1),
        'Breakeven_Realistic_Months': round(breakeven_realistic, 1),
        'Breakeven_Conservative_Months': round(breakeven_conservative, 1),
        'Success_Probability': model['success_prob']
    })

breakeven_df = pd.DataFrame(breakeven_data)
print(breakeven_df.to_string(index=False))

# Risk assessment matrix
print("\n=== RISK ASSESSMENT MATRIX ===")
risk_factors = {
    'AI-Enhanced Local Service Business': {
        'Technology Risk': 'Medium', 'Market Risk': 'Low', 'Competition Risk': 'Medium',
        'Regulatory Risk': 'Low', 'Scalability': 'High', 'Capital Requirements': 'Medium'
    },
    'Sustainable Energy AI Consulting': {
        'Technology Risk': 'Medium', 'Market Risk': 'Low', 'Competition Risk': 'Low',
        'Regulatory Risk': 'Medium', 'Scalability': 'High', 'Capital Requirements': 'Medium'
    },
    'Community Token Pre-Order System': {
        'Technology Risk': 'High', 'Market Risk': 'High', 'Competition Risk': 'Medium',
        'Regulatory Risk': 'High', 'Scalability': 'Medium', 'Capital Requirements': 'Low'
    },
    'Creative Content + Token Rewards': {
        'Technology Risk': 'Medium', 'Market Risk': 'Medium', 'Competition Risk': 'High',
        'Regulatory Risk': 'Medium', 'Scalability': 'High', 'Capital Requirements': 'Low'
    }
}

risk_df = pd.DataFrame(risk_factors).T
print(risk_df.to_string())

# Save comprehensive analysis
scenario_df.to_csv('scenario_analysis.csv', index=False)
breakeven_df.to_csv('breakeven_analysis.csv', index=False)
print(f"\nAnalysis saved to 'scenario_analysis.csv' and 'breakeven_analysis.csv'")