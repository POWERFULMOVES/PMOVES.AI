# Create comprehensive model for "Docker Container-like" micro business spawning system
import pandas as pd
import numpy as np

print("=== MICRO BUSINESS 'CONTAINER' SPAWNING MODEL ===")
print("Treating each business as a deployable, scalable 'container' that can be replicated\n")

# Define the containerized business models - like Docker images
business_containers = {
    'Security-Delivery-Hub': {
        'base_investment': 25000,
        'scaling_unit': 15000,  # Cost to add each additional "container"
        'revenue_per_unit': 8500,  # Monthly revenue per container
        'margin': 0.35,
        'community_retention': 0.90,
        'startup_time_days': 30,
        'replication_difficulty': 'Low',
        'core_services': ['Security services', 'Bulk delivery coordination', 'Route optimization']
    },
    'Bulk-Purchase-Cooperative': {
        'base_investment': 15000,
        'scaling_unit': 8000,
        'revenue_per_unit': 6200,
        'margin': 0.25,
        'community_retention': 0.85,
        'startup_time_days': 45,
        'replication_difficulty': 'Medium',
        'core_services': ['Group buying coordination', 'Inventory management', 'Distribution']
    },
    'Community-Shuttle-Network': {
        'base_investment': 35000,
        'scaling_unit': 20000,
        'revenue_per_unit': 12000,
        'margin': 0.40,
        'community_retention': 0.88,
        'startup_time_days': 60,
        'replication_difficulty': 'Medium',
        'core_services': ['Community transportation', 'Route planning', 'Membership management']
    },
    'Token-Rewards-Platform': {
        'base_investment': 12000,
        'scaling_unit': 6000,
        'revenue_per_unit': 4800,
        'margin': 0.45,
        'community_retention': 0.75,
        'startup_time_days': 20,
        'replication_difficulty': 'Low',
        'core_services': ['Token issuance', 'Reward distribution', 'Community engagement']
    },
    'Neighborhood-Food-Hub': {
        'base_investment': 18000,
        'scaling_unit': 12000,
        'revenue_per_unit': 9500,
        'margin': 0.30,
        'community_retention': 0.92,
        'startup_time_days': 35,
        'replication_difficulty': 'Medium',
        'core_services': ['Community kitchen', 'Catering', 'Cultural events']
    }
}

# Model the Costco bulk delivery scenario specifically
print("=== COSTCO BULK DELIVERY SCENARIO ANALYSIS ===")

# Assumptions based on real cooperative delivery data
costco_scenario = {
    'households_served': 200,
    'average_order_size': 180,  # Average Costco order
    'delivery_fee_individual': 15,  # What each household would pay individually
    'bulk_coordination_fee': 8,   # Reduced fee through coordination
    'security_additional_pay': 25,  # Extra pay per trip for security
    'trips_per_week': 3,
    'gas_savings_per_trip': 12,   # Saved per household by not making individual trips
    'time_savings_hours': 2,      # Hours saved per household per trip
}

# Calculate economic impact
individual_cost = costco_scenario['households_served'] * costco_scenario['delivery_fee_individual']
coordinated_cost = costco_scenario['households_served'] * costco_scenario['bulk_coordination_fee']
total_savings_per_trip = individual_cost - coordinated_cost
security_income_per_trip = costco_scenario['security_additional_pay'] * costco_scenario['trips_per_week']

# Weekly calculations
weekly_community_savings = total_savings_per_trip * costco_scenario['trips_per_week']
weekly_security_income = security_income_per_trip
weekly_gas_savings = costco_scenario['gas_savings_per_trip'] * costco_scenario['households_served'] * costco_scenario['trips_per_week']

print(f"Individual delivery cost per trip: ${individual_cost:,}")
print(f"Coordinated bulk delivery cost: ${coordinated_cost:,}")
print(f"Community savings per trip: ${total_savings_per_trip:,}")
print(f"Weekly community savings: ${weekly_community_savings:,}")
print(f"Weekly additional income for security: ${weekly_security_income:,}")
print(f"Weekly gas savings community-wide: ${weekly_gas_savings:,}")

# Calculate van purchase timeline
van_cost = 45000  # New delivery van
weekly_profit_towards_van = weekly_community_savings * 0.30  # 30% of savings goes to van fund
weeks_to_van = van_cost / weekly_profit_towards_van

print(f"\nVan purchase fund: ${weekly_profit_towards_van:,} per week")
print(f"Time to purchase new van: {weeks_to_van:.1f} weeks ({weeks_to_van/52:.1f} years)")

# Model the scaling/replication system
print(f"\n=== BUSINESS CONTAINER SCALING MODEL ===")

scaling_scenarios = []

for container_name, config in business_containers.items():
    # Calculate scaling economics for 1, 3, 5, and 10 "containers"
    for scale in [1, 3, 5, 10]:
        # Investment calculation
        if scale == 1:
            total_investment = config['base_investment']
        else:
            total_investment = config['base_investment'] + (config['scaling_unit'] * (scale - 1))
        
        # Revenue calculation with network effects
        network_multiplier = 1 + (scale - 1) * 0.15  # 15% network effect per additional unit
        monthly_revenue = config['revenue_per_unit'] * scale * network_multiplier
        
        # Community wealth circulation
        local_multiplier = 2.2 + (config['community_retention'] * 0.8)
        total_community_impact = monthly_revenue * 12 * local_multiplier
        
        # Calculate ROI and payback
        annual_profit = monthly_revenue * 12 * config['margin']
        roi = (annual_profit / total_investment) * 100
        payback_months = total_investment / (monthly_revenue * config['margin'])
        
        scaling_scenarios.append({
            'Container_Type': container_name,
            'Scale': f"{scale}x",
            'Total_Investment': total_investment,
            'Monthly_Revenue': round(monthly_revenue, 0),
            'Annual_Profit': round(annual_profit, 0),
            'ROI_Percent': round(roi, 1),
            'Payback_Months': round(payback_months, 1),
            'Community_Impact': round(total_community_impact, 0),
            'Startup_Days': config['startup_time_days'],
            'Replication_Difficulty': config['replication_difficulty']
        })

scaling_df = pd.DataFrame(scaling_scenarios)

# Show top performing scaled models
print("Top performing scaled business containers:")
top_performers = scaling_df.nlargest(10, 'ROI_Percent')
print(top_performers[['Container_Type', 'Scale', 'Total_Investment', 'ROI_Percent', 'Community_Impact']].to_string(index=False))

print(f"\n=== RESIDENT INVESTOR MODEL ===")

# Model resident investment structure
investor_types = {
    'Service_Users': {
        'investment_per_person': 150,
        'expected_participants': 300,
        'motivation': 'Access to services + cost savings',
        'expected_return': 'Service credits + annual dividends'
    },
    'Community_Supporters': {
        'investment_per_person': 500,
        'expected_participants': 100,
        'motivation': 'Community development + financial return',
        'expected_return': '8-12% annual return + community benefits'
    },
    'Local_Business_Partners': {
        'investment_per_person': 2000,
        'expected_participants': 25,
        'motivation': 'Supply chain integration + market access',
        'expected_return': '15-20% return + business development'
    }
}

total_resident_investment = 0
total_investors = 0

print("Resident Investment Structure:")
for investor_type, data in investor_types.items():
    type_investment = data['investment_per_person'] * data['expected_participants']
    total_resident_investment += type_investment
    total_investors += data['expected_participants']
    
    print(f"\n{investor_type}:")
    print(f"  Investment per person: ${data['investment_per_person']:,}")
    print(f"  Expected participants: {data['expected_participants']}")
    print(f"  Total investment: ${type_investment:,}")
    print(f"  Motivation: {data['motivation']}")
    print(f"  Return: {data['expected_return']}")

print(f"\nTotal resident investment available: ${total_resident_investment:,}")
print(f"Total resident investors: {total_investors}")

# Calculate how many business containers can be launched
affordable_containers = []

for container_name, config in business_containers.items():
    max_containers = int(total_resident_investment / config['base_investment'])
    total_monthly_revenue = config['revenue_per_unit'] * max_containers * (1 + (max_containers - 1) * 0.1)
    
    affordable_containers.append({
        'Container_Type': container_name,
        'Max_Containers': max_containers,
        'Total_Investment': max_containers * config['base_investment'],
        'Monthly_Revenue': round(total_monthly_revenue, 0),
        'Startup_Timeline_Months': (config['startup_time_days'] * max_containers) / 30
    })

print(f"\n=== CONTAINERIZED BUSINESS DEPLOYMENT CAPACITY ===")
containers_df = pd.DataFrame(affordable_containers)
print(containers_df.to_string(index=False))

# Save comprehensive analysis
scaling_df.to_csv('micro_business_container_scaling.csv', index=False)
containers_df.to_csv('resident_investment_capacity.csv', index=False)

print(f"\n=== KEY SUCCESS FACTORS FOR 'CONTAINER' MODEL ===")
success_factors = [
    "Standardized operations manual (like Docker images)",
    "AI-driven optimization for each deployment",
    "Token-based coordination between containers",
    "Resident ownership structure ensures local wealth retention",
    "Rapid replication capability (30-60 days per container)",
    "Network effects increase value with scale",
    "Community-first governance model"
]

for i, factor in enumerate(success_factors, 1):
    print(f"{i}. {factor}")

print(f"\nFiles saved for implementation planning")