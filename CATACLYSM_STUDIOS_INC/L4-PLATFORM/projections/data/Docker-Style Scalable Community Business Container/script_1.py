# Fix the key error and create Docker-like containerized business model analysis
import pandas as pd
import numpy as np

# Define the "container" business models that can be spawned and scaled
container_business_models = {
    'Bulk-Purchase-Delivery': {
        'description': 'Security guard collective handles bulk Costco runs for community',
        'base_investment': 8000,  # Initial van purchase
        'monthly_operating_cost': 1200,
        'service_capacity': 50,  # households served per run
        'revenue_per_unit': 25,  # delivery fee per household
        'frequency_per_month': 8,  # twice weekly
        'cost_savings_per_household': 40,  # gas + time savings
        'worker_ownership_percentage': 100,
        'scalability_factor': 0.9,  # High scalability
        'community_retention': 0.95  # Money stays very local
    },
    'Shuttle-Transport': {
        'description': 'Resident-owned shuttle service for commuting and errands',
        'base_investment': 15000,  # Used shuttle bus
        'monthly_operating_cost': 2200,
        'service_capacity': 25,  # passengers per trip
        'revenue_per_unit': 5,  # per passenger per trip
        'frequency_per_month': 160,  # 8 trips per workday
        'cost_savings_per_household': 80,  # compared to individual transport
        'worker_ownership_percentage': 100,
        'scalability_factor': 0.8,
        'community_retention': 0.90
    },
    'Food-Hub-Delivery': {
        'description': 'Coordinated meal delivery from local restaurants/kitchens',
        'base_investment': 3000,  # Delivery bags, phone system
        'monthly_operating_cost': 800,
        'service_capacity': 200,  # orders per day
        'revenue_per_unit': 4,  # delivery fee per order
        'frequency_per_month': 25,  # working days
        'cost_savings_per_household': 15,  # compared to individual delivery fees
        'worker_ownership_percentage': 100,
        'scalability_factor': 0.95,
        'community_retention': 0.85
    },
    'Tool-Equipment-Share': {
        'description': 'Community tool library with delivery service',
        'base_investment': 5000,  # Initial tool inventory
        'monthly_operating_cost': 400,
        'service_capacity': 100,  # rentals per month
        'revenue_per_unit': 12,  # average rental fee
        'frequency_per_month': 1,  # monthly metric
        'cost_savings_per_household': 200,  # vs buying tools
        'worker_ownership_percentage': 100,
        'scalability_factor': 0.7,
        'community_retention': 0.98
    },
    'Repair-Maintenance-Mobile': {
        'description': 'Mobile repair services (appliances, electronics, bikes)',
        'base_investment': 6000,  # Tools, van setup
        'monthly_operating_cost': 900,
        'service_capacity': 80,  # repairs per month
        'revenue_per_unit': 35,  # average service fee
        'frequency_per_month': 1,
        'cost_savings_per_household': 60,  # vs shop visits
        'worker_ownership_percentage': 100,
        'scalability_factor': 0.85,
        'community_retention': 0.92
    },
    'Childcare-Collective': {
        'description': 'Rotating childcare with transport service',
        'base_investment': 4000,  # Safety equipment, van modifications
        'monthly_operating_cost': 600,
        'service_capacity': 30,  # children served
        'revenue_per_unit': 120,  # monthly fee per child
        'frequency_per_month': 1,
        'cost_savings_per_household': 300,  # vs commercial daycare
        'worker_ownership_percentage': 100,
        'scalability_factor': 0.6,
        'community_retention': 0.98
    }
}

# Calculate investor/user economics and scaling potential
def calculate_container_economics(model_name, model_data, num_containers=1):
    """Calculate economics for deploying N containers of a business model"""
    
    # Base economics per container
    monthly_revenue = (model_data['service_capacity'] * 
                      model_data['revenue_per_unit'] * 
                      model_data['frequency_per_month'])
    
    monthly_profit = monthly_revenue - model_data['monthly_operating_cost']
    annual_profit = monthly_profit * 12
    
    # Investment payback period
    payback_months = model_data['base_investment'] / monthly_profit if monthly_profit > 0 else float('inf')
    
    # Community value creation (cost savings to residents)
    total_households_served = model_data['service_capacity']
    monthly_community_savings = total_households_served * model_data['cost_savings_per_household']
    annual_community_savings = monthly_community_savings * 12
    
    # Scaling economics (diminishing returns factor)
    scaling_factor = model_data['scalability_factor']
    
    results = {
        'Model': model_name,
        'Containers': num_containers,
        'Total_Investment': model_data['base_investment'] * num_containers,
        'Monthly_Revenue_Per_Container': monthly_revenue,
        'Monthly_Profit_Per_Container': monthly_profit,
        'Annual_Profit_Per_Container': annual_profit,
        'Total_Annual_Profit': annual_profit * num_containers * (scaling_factor ** (num_containers - 1)),
        'Payback_Months': round(payback_months, 1),
        'Community_Savings_Annual': annual_community_savings * num_containers,
        'Worker_Ownership_Pct': model_data['worker_ownership_percentage'],
        'Community_Retention': model_data['community_retention'],
        'ROI_Year_1': round((annual_profit / model_data['base_investment']) * 100, 1) if model_data['base_investment'] > 0 else 0
    }
    
    return results

# Analyze each container model
container_analysis = []
for model_name, model_data in container_business_models.items():
    # Single container deployment
    single_result = calculate_container_economics(model_name, model_data, 1)
    container_analysis.append(single_result)
    
    # Multi-container deployment (3 containers)
    multi_result = calculate_container_economics(model_name, model_data, 3)
    multi_result['Model'] = f"{model_name}_3x"
    container_analysis.append(multi_result)

container_df = pd.DataFrame(container_analysis)

print("=== DOCKER-STYLE SCALABLE BUSINESS CONTAINERS ===")
print("Single Container Deployments:")
single_containers = container_df[container_df['Containers'] == 1].copy()
print(single_containers[['Model', 'Total_Investment', 'Monthly_Profit_Per_Container', 'ROI_Year_1', 'Payback_Months']].to_string(index=False))

print("\n=== COMMUNITY VALUE CREATION ===")
print(single_containers[['Model', 'Community_Savings_Annual', 'Community_Retention']].to_string(index=False))

print("\n=== SCALING ANALYSIS (3x Containers) ===")
multi_containers = container_df[container_df['Containers'] == 3].copy()
print(multi_containers[['Model', 'Total_Investment', 'Total_Annual_Profit', 'Community_Savings_Annual']].to_string(index=False))

# Token-based investment model
print("\n=== TOKEN-BASED INVESTOR MODEL ===")

# Calculate token economics for resident investors
def calculate_token_investment_model(model_data, total_investment_needed):
    """Calculate token-based community investment structure"""
    
    # Token structure: $100 per token
    token_price = 100
    total_tokens = total_investment_needed // token_price
    
    # Annual returns from the business
    annual_profit = calculate_container_economics('temp', model_data, 1)['Annual_Profit_Per_Container']
    
    # Token holder benefits
    profit_share_percentage = 0.70  # 70% of profits go to token holders
    annual_profit_distribution = annual_profit * profit_share_percentage
    annual_return_per_token = annual_profit_distribution / total_tokens
    token_roi = (annual_return_per_token / token_price) * 100
    
    # Service user benefits (additional rewards)
    service_users_get_bonus = 1.2  # 20% bonus for service users
    
    return {
        'Token_Price': token_price,
        'Total_Tokens': int(total_tokens),
        'Annual_Return_Per_Token': round(annual_return_per_token, 2),
        'Token_ROI_Percent': round(token_roi, 1),
        'Service_User_ROI': round(token_roi * service_users_get_bonus, 1),
        'Profit_Distribution_Total': round(annual_profit_distribution, 0)
    }

# Calculate token models for top business containers
token_models = []
for model_name, model_data in container_business_models.items():
    token_model = calculate_token_investment_model(model_data, model_data['base_investment'])
    token_model['Model'] = model_name
    token_models.append(token_model)

token_df = pd.DataFrame(token_models)

print("Token Investment Structure ($100 per token):")
print(token_df[['Model', 'Total_Tokens', 'Annual_Return_Per_Token', 'Token_ROI_Percent', 'Service_User_ROI']].to_string(index=False))

# Expansion economics - when to buy the second van
print("\n=== EXPANSION ECONOMICS: WHEN TO BUY SECOND VAN ===")

bulk_delivery = container_business_models['Bulk-Purchase-Delivery']
monthly_profit = calculate_container_economics('Bulk-Purchase-Delivery', bulk_delivery, 1)['Monthly_Profit_Per_Container']

# Expansion thresholds
second_van_cost = bulk_delivery['base_investment']
months_to_save = second_van_cost / monthly_profit

print(f"Monthly Profit from First Van: ${monthly_profit:,}")
print(f"Second Van Cost: ${second_van_cost:,}")
print(f"Time to Save for Second Van: {months_to_save:.1f} months")

# Alternative: Token-funded expansion
tokens_needed_for_expansion = second_van_cost // 100
print(f"Alternative: Issue {tokens_needed_for_expansion} new tokens at $100 each")
print(f"Existing token holders dilution: {(token_models[0]['Total_Tokens'] / (token_models[0]['Total_Tokens'] + tokens_needed_for_expansion)) * 100:.1f}%")

# Community multiplier effect
print(f"\n=== COMMUNITY WEALTH MULTIPLIER EFFECT ===")
total_investment = single_containers['Total_Investment'].sum()
total_annual_profit = single_containers['Annual_Profit_Per_Container'].sum()  
total_community_savings = single_containers['Community_Savings_Annual'].sum()
avg_retention = single_containers['Community_Retention'].mean()

# Local multiplier calculation
local_multiplier = 2.0 + (avg_retention * 1.5)  # Base 2x + retention bonus
total_community_impact = (total_annual_profit + total_community_savings) * local_multiplier

print(f"Total Container Portfolio Investment: ${total_investment:,}")
print(f"Direct Annual Benefits: ${total_annual_profit + total_community_savings:,}")
print(f"Local Economic Multiplier: {local_multiplier:.2f}x")
print(f"Total Community Economic Impact: ${total_community_impact:,}")
print(f"Community ROI: {((total_community_impact - total_investment) / total_investment) * 100:.1f}%")

# Worker income analysis
print(f"\n=== WORKER OWNERSHIP INCOME ANALYSIS ===")
security_workers = 3  # Number of security guards in collective
monthly_income_per_worker = monthly_profit / security_workers
annual_income_per_worker = monthly_income_per_worker * 12

print(f"Security Workers in Collective: {security_workers}")
print(f"Additional Monthly Income per Worker: ${monthly_income_per_worker:,.0f}")
print(f"Additional Annual Income per Worker: ${annual_income_per_worker:,.0f}")
print(f"Income Boost vs Median Security Wage (~$35k): {(annual_income_per_worker / 35000) * 100:.1f}%")

# Save all analysis
container_df.to_csv('docker_container_business_models.csv', index=False)
token_df.to_csv('token_investment_models.csv', index=False)

print(f"\nAnalysis saved to CSV files - ready for community deployment!")