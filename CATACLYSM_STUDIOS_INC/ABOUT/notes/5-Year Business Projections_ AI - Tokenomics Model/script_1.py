# Create summary statistics and key insights
import pandas as pd

df = pd.read_csv('ai_tokenomics_business_projections.csv')

# Summary by business model for Year 5 (2029)
year5_summary = df[df['Year'] == 2029].copy()
year5_summary = year5_summary.sort_values('ROI_Percent', ascending=False)

print("=== YEAR 5 (2029) PERFORMANCE RANKING ===")
print(year5_summary[['Business_Model', 'Revenue', 'Net_Profit', 'ROI_Percent', 'Success_Probability']].to_string(index=False))

# Calculate risk-adjusted returns
year5_summary['Risk_Adjusted_ROI'] = year5_summary['ROI_Percent'] * year5_summary['Success_Probability']
year5_summary = year5_summary.sort_values('Risk_Adjusted_ROI', ascending=False)

print("\n=== RISK-ADJUSTED ROI RANKING (Year 5) ===")
print(year5_summary[['Business_Model', 'ROI_Percent', 'Success_Probability', 'Risk_Adjusted_ROI']].to_string(index=False))

# Investment tiers analysis
print("\n=== INVESTMENT TIER ANALYSIS ===")
investment_tiers = year5_summary.groupby('Initial_Investment').agg({
    'ROI_Percent': 'mean',
    'Risk_Adjusted_ROI': 'mean',
    'Business_Model': 'count'
}).round(1)
investment_tiers.columns = ['Avg_ROI', 'Avg_Risk_Adj_ROI', 'Model_Count']
print(investment_tiers)

# Create detailed breakdown for top 3 models
print("\n=== TOP 3 MODELS - 5 YEAR TRAJECTORY ===")
top_3_models = year5_summary.head(3)['Business_Model'].tolist()

for model in top_3_models:
    model_data = df[df['Business_Model'] == model]
    print(f"\n{model}:")
    print(model_data[['Year', 'Revenue', 'Net_Profit', 'Cumulative_Profit', 'ROI_Percent']].to_string(index=False))

# Market conditions impact analysis
print("\n=== MARKET CONDITIONS SENSITIVITY ===")
scenarios = {
    'Optimistic': {'growth_multiplier': 1.3, 'success_boost': 0.15},
    'Base Case': {'growth_multiplier': 1.0, 'success_boost': 0.0},  
    'Pessimistic': {'growth_multiplier': 0.7, 'success_boost': -0.20}
}

scenario_results = []
for scenario_name, params in scenarios.items():
    adj_year5 = year5_summary.copy()
    adj_year5['Adj_ROI'] = adj_year5['ROI_Percent'] * params['growth_multiplier']
    adj_year5['Adj_Success'] = np.clip(adj_year5['Success_Probability'] + params['success_boost'], 0.1, 0.95)
    adj_year5['Adj_Risk_ROI'] = adj_year5['Adj_ROI'] * adj_year5['Adj_Success']
    
    avg_roi = adj_year5['Adj_Risk_ROI'].mean()
    scenario_results.append({
        'Scenario': scenario_name,
        'Avg_Risk_Adjusted_ROI': round(avg_roi, 1),
        'Top_Model_ROI': round(adj_year5['Adj_Risk_ROI'].max(), 1),
        'Success_Models_Count': len(adj_year5[adj_year5['Adj_Risk_ROI'] > 500])
    })

scenario_df = pd.DataFrame(scenario_results)
print(scenario_df.to_string(index=False))

# Save summary data
year5_summary.to_csv('business_model_summary_2029.csv', index=False)
print(f"\nSummary data saved to 'business_model_summary_2029.csv'")