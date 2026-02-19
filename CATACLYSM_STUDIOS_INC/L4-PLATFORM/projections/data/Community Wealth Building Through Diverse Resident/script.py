# Create comprehensive analysis of resident backgrounds and upskilling scenarios for AI+Tokenomics models
import pandas as pd
import numpy as np

# Define diverse resident backgrounds with specific characteristics
resident_backgrounds = {
    'Recent Immigrants': {
        'population_size': 15000,
        'baseline_income': 28000,
        'digital_fluency': 0.45,  # 45% digitally fluent
        'entrepreneurial_interest': 0.65,
        'language_barriers': 0.70,
        'network_access': 0.30,
        'primary_skills': ['multilingual', 'cultural knowledge', 'food service', 'manual labor'],
        'growth_potential': 0.85  # High potential with proper support
    },
    'Single Parents': {
        'population_size': 8500,
        'baseline_income': 32000,
        'digital_fluency': 0.55,
        'entrepreneurial_interest': 0.70,
        'language_barriers': 0.15,
        'network_access': 0.40,
        'primary_skills': ['multitasking', 'time management', 'customer service', 'administrative'],
        'growth_potential': 0.75
    },
    'Young Adults (18-25)': {
        'population_size': 12000,
        'baseline_income': 22000,
        'digital_fluency': 0.90,
        'entrepreneurial_interest': 0.80,
        'language_barriers': 0.05,
        'network_access': 0.85,
        'primary_skills': ['social media', 'technology', 'creative content', 'retail'],
        'growth_potential': 0.90
    },
    'Displaced Workers': {
        'population_size': 6000,
        'baseline_income': 35000,
        'digital_fluency': 0.35,
        'entrepreneurial_interest': 0.50,
        'language_barriers': 0.20,
        'network_access': 0.60,
        'primary_skills': ['industry experience', 'work ethic', 'problem solving', 'manual skills'],
        'growth_potential': 0.65
    },
    'Retirees/Semi-Retired': {
        'population_size': 9000,
        'baseline_income': 38000,
        'digital_fluency': 0.25,
        'entrepreneurial_interest': 0.40,
        'language_barriers': 0.10,
        'network_access': 0.75,
        'primary_skills': ['mentorship', 'life experience', 'crafts', 'consulting'],
        'growth_potential': 0.55
    },
    'Community College Students': {
        'population_size': 4500,
        'baseline_income': 18000,
        'digital_fluency': 0.80,
        'entrepreneurial_interest': 0.75,
        'language_barriers': 0.25,
        'network_access': 0.50,
        'primary_skills': ['learning agility', 'technical skills', 'research', 'collaboration'],
        'growth_potential': 0.95
    }
}

# Calculate community wealth multiplier effects with local circulation
def calculate_local_multiplier(initial_spending, business_type, community_retention_rate):
    """Calculate how money circulates through local economy"""
    # Based on research showing 2-4x multiplier for local businesses
    if business_type == 'local_cooperative':
        base_multiplier = 3.2  # Higher retention
    elif business_type == 'local_enterprise':
        base_multiplier = 2.8
    elif business_type == 'chain_business':
        base_multiplier = 1.4  # Most money leaves community
    else:
        base_multiplier = 2.5
    
    # Apply community retention rate
    effective_multiplier = base_multiplier * community_retention_rate
    total_economic_impact = initial_spending * effective_multiplier
    
    return {
        'initial_spending': initial_spending,
        'multiplier_effect': effective_multiplier,
        'total_impact': total_economic_impact,
        'additional_value': total_economic_impact - initial_spending
    }

# Create upskilling pathways for different backgrounds
upskilling_programs = []

for background, data in resident_backgrounds.items():
    # Basic AI literacy program (3 months)
    basic_ai_cost = 800
    basic_ai_impact = data['digital_fluency'] * 1.2 + 0.3
    
    # Advanced tokenomics training (6 months) 
    advanced_token_cost = 1500
    advanced_token_impact = data['entrepreneurial_interest'] * 1.1 + 0.2
    
    # Enterprise development program (12 months)
    enterprise_cost = 3000
    enterprise_impact = data['growth_potential'] * 1.3
    
    # Calculate potential income increases
    basic_income_boost = data['baseline_income'] * 0.25 * basic_ai_impact
    advanced_income_boost = data['baseline_income'] * 0.45 * advanced_token_impact  
    enterprise_income_boost = data['baseline_income'] * 0.80 * enterprise_impact
    
    upskilling_programs.append({
        'Background': background,
        'Population': data['population_size'],
        'Baseline_Income': data['baseline_income'],
        'Digital_Fluency': data['digital_fluency'],
        'Entrepreneurial_Interest': data['entrepreneurial_interest'],
        'Growth_Potential': data['growth_potential'],
        'Basic_AI_Cost': basic_ai_cost,
        'Basic_Income_Boost': round(basic_income_boost, 0),
        'Basic_ROI_Months': round(basic_ai_cost / (basic_income_boost/12), 1) if basic_income_boost > 0 else float('inf'),
        'Advanced_Token_Cost': advanced_token_cost,
        'Advanced_Income_Boost': round(advanced_income_boost, 0),
        'Advanced_ROI_Months': round(advanced_token_cost / (advanced_income_boost/12), 1) if advanced_income_boost > 0 else float('inf'),
        'Enterprise_Cost': enterprise_cost,
        'Enterprise_Income_Boost': round(enterprise_income_boost, 0),
        'Enterprise_ROI_Months': round(enterprise_cost / (enterprise_income_boost/12), 1) if enterprise_income_boost > 0 else float('inf')
    })

upskilling_df = pd.DataFrame(upskilling_programs)

print("=== UPSKILLING PATHWAY ANALYSIS BY RESIDENT BACKGROUND ===")
print(upskilling_df[['Background', 'Population', 'Baseline_Income', 'Basic_Income_Boost', 'Basic_ROI_Months']].to_string(index=False))

print("\n=== ADVANCED PROGRAMS ROI ANALYSIS ===")
print(upskilling_df[['Background', 'Advanced_Income_Boost', 'Advanced_ROI_Months', 'Enterprise_Income_Boost', 'Enterprise_ROI_Months']].to_string(index=False))

# Calculate community-wide economic impact
total_population = sum([data['population_size'] for data in resident_backgrounds.values()])
print(f"\nTotal Community Population: {total_population:,}")

# Calculate participation rates and economic multipliers  
participation_scenarios = {
    'Conservative (10% participation)': 0.10,
    'Moderate (25% participation)': 0.25,
    'Optimistic (40% participation)': 0.40
}

community_impact_analysis = []

for scenario_name, participation_rate in participation_scenarios.items():
    total_participants = int(total_population * participation_rate)
    total_investment = total_participants * 1500  # Average program cost
    
    # Calculate average income boost across all backgrounds
    weighted_income_boost = 0
    for _, row in upskilling_df.iterrows():
        weight = row['Population'] / total_population
        avg_boost = (row['Basic_Income_Boost'] + row['Advanced_Income_Boost']) / 2
        weighted_income_boost += weight * avg_boost
    
    annual_income_increase = total_participants * weighted_income_boost
    
    # Apply local multiplier effect (assuming 70% community retention)
    multiplier_impact = calculate_local_multiplier(annual_income_increase, 'local_cooperative', 0.70)
    
    community_impact_analysis.append({
        'Scenario': scenario_name,
        'Participants': total_participants,
        'Total_Investment': total_investment,
        'Annual_Income_Increase': round(annual_income_increase, 0),
        'Local_Multiplier': round(multiplier_impact['multiplier_effect'], 2),
        'Total_Economic_Impact': round(multiplier_impact['total_impact'], 0),
        'Community_ROI': round((multiplier_impact['total_impact'] / total_investment) * 100, 1)
    })

impact_df = pd.DataFrame(community_impact_analysis)
print("\n=== COMMUNITY-WIDE ECONOMIC IMPACT SCENARIOS ===")
print(impact_df.to_string(index=False))

# Save data
upskilling_df.to_csv('resident_upskilling_analysis.csv', index=False)
impact_df.to_csv('community_economic_impact.csv', index=False)
print(f"\nData saved to files for further analysis")