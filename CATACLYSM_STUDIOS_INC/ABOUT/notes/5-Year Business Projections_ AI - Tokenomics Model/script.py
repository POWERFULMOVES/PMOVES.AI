import pandas as pd
import numpy as np

# Create comprehensive 5-year projections for various AI + Tokenomics business models
# Based on the research data and the attached PDF insights

# Base scenario parameters from research
ai_adoption_rate = 0.68  # 68% of small businesses using AI
ai_revenue_boost = 0.91  # 91% see revenue growth with AI
token_success_rate = 0.47  # ~47% token success rate (100% - 53% failure rate)
community_currency_viability = 0.35  # Based on limited success stories

# Business model categories
business_models = [
    "AI-Enhanced Local Service Business",
    "Community Token Pre-Order System", 
    "Sustainable Energy AI Consulting",
    "Creative Content + Token Rewards",
    "Local Food Network with Tokens",
    "AI Tutoring + Community Currency",
    "Digital Art Creation + NFT Tokens",
    "Urban Agriculture + Token Economy"
]

# Create 5-year projections
years = [2025, 2026, 2027, 2028, 2029]
projections_data = []

for model in business_models:
    # Base parameters vary by business model
    if "AI-Enhanced" in model:
        initial_investment = 5000
        success_probability = 0.75  # Higher due to AI adoption success rates
        year1_revenue = 25000
        growth_rate = 0.45  # 45% annual growth for AI businesses
        operating_margin = 0.35
        
    elif "Token" in model or "Community" in model:
        initial_investment = 3000
        success_probability = 0.40  # Lower due to token failure rates
        year1_revenue = 15000
        growth_rate = 0.25  # More conservative growth
        operating_margin = 0.25
        
    elif "Creative" in model or "Art" in model:
        initial_investment = 2000
        success_probability = 0.55  # Medium success rate
        year1_revenue = 12000
        growth_rate = 0.35
        operating_margin = 0.40
        
    else:  # Mixed AI + Token models
        initial_investment = 4000
        success_probability = 0.60  # Balanced approach
        year1_revenue = 20000
        growth_rate = 0.38
        operating_margin = 0.30
    
    # Calculate 5-year projections
    for i, year in enumerate(years):
        if i == 0:
            revenue = year1_revenue
        else:
            # Apply compound growth with some market saturation
            saturation_factor = 1 - (i * 0.05)  # Gradual market saturation
            revenue = projections_data[-1]['Revenue'] * (1 + growth_rate * saturation_factor)
        
        operating_profit = revenue * operating_margin
        net_profit = operating_profit - (initial_investment / 5)  # Amortize initial investment
        cumulative_profit = net_profit * (i + 1) if i == 0 else projections_data[-1]['Cumulative_Profit'] + net_profit
        roi = (cumulative_profit / initial_investment) * 100
        
        projections_data.append({
            'Business_Model': model,
            'Year': year,
            'Revenue': round(revenue, 0),
            'Operating_Profit': round(operating_profit, 0),
            'Net_Profit': round(net_profit, 0),
            'Cumulative_Profit': round(cumulative_profit, 0),
            'ROI_Percent': round(roi, 1),
            'Success_Probability': success_probability,
            'Initial_Investment': initial_investment
        })

# Create DataFrame
df = pd.DataFrame(projections_data)

# Display sample of the data
print("5-Year Business Model Projections Sample:")
print(df.head(10).to_string(index=False))
print(f"\nTotal models analyzed: {len(business_models)}")
print(f"Total projections: {len(df)}")

# Save to CSV
df.to_csv('ai_tokenomics_business_projections.csv', index=False)
print("\nData saved to 'ai_tokenomics_business_projections.csv'")