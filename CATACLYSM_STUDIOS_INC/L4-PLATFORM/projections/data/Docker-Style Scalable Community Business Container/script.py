# Create Docker-like containerized business model analysis for scalable micro-enterprises
import pandas as pd
import numpy as np

# Define the "container" business models that can be spawned and scaled
container_business_models = {
    'Bulk-Purchase-Delivery': {
        'description': 'Security guard collective handles bulk Costco runs for community',
        'base_investment': 8000,  # Initial van purchase
        'monthly_operating_cost': 1200,
        'service_capacity': 50,  # households served per run
        'revenue_per_household': 25,  # delivery fee
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
        'revenue_per_passenger': 5,  # per trip
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
        'revenue_per_order': 4,  # delivery fee
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
        'revenue_per_rental': 12,  # average rental fee
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
        'revenue_per_service': 35,  # average service fee
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
        'revenue_per_child': 120,  # monthly fee per child
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
                      model_data['revenue_per_household'] * 
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
        'Payback_Months': payback_months,
        'Community_Savings_Annual': annual_community_savings * num_containers,
        'Worker_Ownership_Pct': model_data['worker_ownership_percentage'],
        'Community_Retention': model_data['community_retention'],
        'ROI_Year_1': (annual_profit / model_data['base_investment']) * 100 if model_data['base_investment'] > 0 else 0
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

# Investor model analysis
print("\n=== INVESTOR PARTICIPATION MODEL ===")

# Two types of investors: Service Users and Community Supporters
def calculate_investor_returns(model_data, investment_amount, investor_type):
    """Calculate returns for different investor types"""
    
    annual_profit = calculate_container_economics('temp', model_data, 1)['Annual_Profit_Per_Container']
    
    if investor_type == 'service_user':
        # Users get service discounts + profit sharing
        service_discount = model_data['cost_savings_per_household'] * 12 * 0.1  # 10% of savings as discount
        profit_share = (investment_amount / model_data['base_investment']) * annual_profit * 0.6  # 60% profit share
        total_return = service_discount + profit_share
        
    elif investor_type == 'community_supporter':
        # Supporters get higher profit sharing but no service discounts
        profit_share = (investment_amount / model_data['base_investment']) * annual_profit * 0.8  # 80% profit share
        total_return = profit_share
        
    return total_return

# Example investor scenarios
investor_scenarios = []
investment_amounts = [500, 1000, 2000, 5000]

for model_name, model_data in list(container_business_models.items())[:3]:  # Top 3 models
    for investment in investment_amounts:
        for investor_type in ['service_user', 'community_supporter']:
            annual_return = calculate_investor_returns(model_data, investment, investor_type)
            roi = (annual_return / investment) * 100
            
            investor_scenarios.append({
                'Model': model_name,
                'Investment': investment,
                'Investor_Type': investor_type,
                'Annual_Return': round(annual_return, 0),
                'ROI_Percent': round(roi, 1)
            })

investor_df = pd.DataFrame(investor_scenarios)

print("\nService User Investor Returns (get service discounts + profit share):")
user_investors = investor_df[investor_df['Investor_Type'] == 'service_user']
print(user_investors.groupby(['Model', 'Investment']).agg({
    'Annual_Return': 'first',
    'ROI_Percent': 'first'
}).round(1).to_string())

print("\nCommunity Supporter Returns (profit share only, higher rate):")
supporter_investors = investor_df[investor_df['Investor_Type'] == 'community_supporter']
print(supporter_investors.groupby(['Model', 'Investment']).agg({
    'Annual_Return': 'first', 
    'ROI_Percent': 'first'
}).round(1).to_string())

# Save container analysis
container_df.to_csv('scalable_container_businesses.csv', index=False)
investor_df.to_csv('investor_participation_models.csv', index=False)

print(f"\n=== SCALING ECONOMICS SUMMARY ===")
total_investment_single = single_containers['Total_Investment'].sum()
total_annual_profit_single = single_containers['Annual_Profit_Per_Container'].sum()
total_community_savings = single_containers['Community_Savings_Annual'].sum()

print(f"Single Container Portfolio Investment: ${total_investment_single:,}")
print(f"Annual Profit (6 containers): ${total_annual_profit_single:,}")
print(f"Annual Community Savings: ${total_community_savings:,}")
print(f"Community ROI: {((total_annual_profit_single + total_community_savings) / total_investment_single) * 100:.1f}%")

print(f"\nContainer deployment saved to CSV files for implementation planning")