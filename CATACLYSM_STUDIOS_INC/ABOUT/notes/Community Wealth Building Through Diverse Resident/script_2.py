# Create implementation timeline and resource allocation for community upskilling
import pandas as pd

# Create phased implementation plan
implementation_phases = {
    'Phase 1 - Foundation (Months 1-6)': {
        'Target_Backgrounds': ['Young Adults (18-25)', 'Community College Students'],
        'Investment_Required': 45000,
        'Expected_Participants': 800,
        'Key_Activities': [
            'Digital literacy bootcamps',
            'Basic AI tools training', 
            'Token economy pilot programs',
            'Community needs assessment'
        ],
        'Success_Metrics': {
            'Completion_Rate': 0.85,
            'Job_Placement_Rate': 0.60,
            'Income_Increase_Avg': 4500,
            'Community_Retention': 0.75
        }
    },
    'Phase 2 - Expansion (Months 7-18)': {
        'Target_Backgrounds': ['Single Parents', 'Recent Immigrants'],
        'Investment_Required': 80000,
        'Expected_Participants': 1200,
        'Key_Activities': [
            'Flexible learning programs',
            'Language-adaptive AI training',
            'Childcare-supported learning',
            'Cultural enterprise development'
        ],
        'Success_Metrics': {
            'Completion_Rate': 0.75,
            'Job_Placement_Rate': 0.55,
            'Income_Increase_Avg': 6200,
            'Community_Retention': 0.85
        }
    },
    'Phase 3 - Maturation (Months 19-36)': {
        'Target_Backgrounds': ['Displaced Workers', 'Retirees/Semi-Retired'],
        'Investment_Required': 95000,
        'Expected_Participants': 900,
        'Key_Activities': [
            'Skills transition programs',
            'Mentorship networks',
            'Advanced enterprise training',
            'Wisdom-sharing platforms'
        ],
        'Success_Metrics': {
            'Completion_Rate': 0.70,
            'Job_Placement_Rate': 0.50,
            'Income_Increase_Avg': 7800,
            'Community_Retention': 0.90
        }
    }
}

# Calculate cumulative community impact over 3 years
cumulative_analysis = []
total_investment = 0
total_participants = 0
cumulative_income_increase = 0

for phase_name, phase_data in implementation_phases.items():
    total_investment += phase_data['Investment_Required']
    participants = phase_data['Expected_Participants']
    completion_rate = phase_data['Success_Metrics']['Completion_Rate']
    successful_participants = int(participants * completion_rate)
    
    income_increase = successful_participants * phase_data['Success_Metrics']['Income_Increase_Avg']
    cumulative_income_increase += income_increase
    
    # Apply local multiplier effect based on community retention
    retention = phase_data['Success_Metrics']['Community_Retention']
    local_multiplier = 2.0 + (retention * 1.2)  # Enhanced multiplier for training programs
    community_economic_impact = income_increase * local_multiplier
    
    cumulative_analysis.append({
        'Phase': phase_name,
        'Investment': phase_data['Investment_Required'],
        'Cumulative_Investment': total_investment,
        'Participants': participants,
        'Successful_Participants': successful_participants,
        'Income_Increase': income_increase,
        'Cumulative_Income': cumulative_income_increase,
        'Local_Multiplier': round(local_multiplier, 2),
        'Community_Impact': round(community_economic_impact, 0),
        'Phase_ROI': round(((community_economic_impact - phase_data['Investment_Required']) / phase_data['Investment_Required']) * 100, 1)
    })

implementation_df = pd.DataFrame(cumulative_analysis)

print("=== PHASED IMPLEMENTATION PLAN ===")
print(implementation_df[['Phase', 'Investment', 'Participants', 'Successful_Participants', 'Community_Impact', 'Phase_ROI']].to_string(index=False))

# Calculate resource allocation by background
resource_allocation = []
total_community_population = 55000  # From previous analysis

for background, data in resident_backgrounds.items():
    population = data['population_size']
    population_percentage = population / total_community_population
    
    # Estimate training costs based on background characteristics
    if data['digital_fluency'] < 0.4:
        base_cost_per_person = 2200  # Higher cost for digital literacy
    elif data['digital_fluency'] > 0.8:
        base_cost_per_person = 1200  # Lower cost due to existing skills
    else:
        base_cost_per_person = 1500  # Standard cost
    
    # Adjust for language barriers and network access
    cost_multiplier = 1.0
    if data['language_barriers'] > 0.5:
        cost_multiplier += 0.3
    if data['network_access'] < 0.5:
        cost_multiplier += 0.2
    
    adjusted_cost = base_cost_per_person * cost_multiplier
    
    # Calculate potential participants (conservative 20% participation rate)
    potential_participants = int(population * 0.20)
    total_training_cost = potential_participants * adjusted_cost
    
    # Calculate expected outcomes
    success_rate = data['growth_potential'] * 0.8  # Conservative estimate
    successful_participants = int(potential_participants * success_rate)
    
    # Income increase based on baseline and growth potential
    avg_income_increase = data['baseline_income'] * 0.4 * data['growth_potential']
    total_income_boost = successful_participants * avg_income_increase
    
    resource_allocation.append({
        'Background': background,
        'Population': population,
        'Population_Percent': round(population_percentage * 100, 1),
        'Potential_Participants': potential_participants,
        'Cost_Per_Person': round(adjusted_cost, 0),
        'Total_Training_Cost': round(total_training_cost, 0),
        'Success_Rate': round(success_rate, 2),
        'Successful_Participants': successful_participants,
        'Avg_Income_Increase': round(avg_income_increase, 0),
        'Total_Income_Boost': round(total_income_boost, 0),
        'ROI': round(((total_income_boost - total_training_cost) / total_training_cost) * 100, 1)
    })

resource_df = pd.DataFrame(resource_allocation)

print("\n=== RESOURCE ALLOCATION BY BACKGROUND ===")
print(resource_df[['Background', 'Population_Percent', 'Cost_Per_Person', 'Success_Rate', 'ROI']].to_string(index=False))

print("\n=== TOTAL COMMUNITY TRANSFORMATION METRICS ===")
total_program_cost = resource_df['Total_Training_Cost'].sum()
total_participants_potential = resource_df['Potential_Participants'].sum()
total_successful = resource_df['Successful_Participants'].sum()
total_income_impact = resource_df['Total_Income_Boost'].sum()

# Apply community-wide multiplier effect
community_retention_avg = 0.82  # From previous analysis
community_multiplier = 2.5 + (community_retention_avg * 1.0)  # Strong local circulation
total_community_impact = total_income_impact * community_multiplier

print(f"Total Program Investment: ${total_program_cost:,}")
print(f"Total Potential Participants: {total_participants_potential:,}")
print(f"Expected Successful Graduates: {total_successful:,}")
print(f"Direct Income Impact: ${total_income_impact:,}")
print(f"Community Economic Multiplier: {community_multiplier:.2f}x")
print(f"Total Community Economic Impact: ${total_community_impact:,}")
print(f"Overall Community ROI: {((total_community_impact - total_program_cost) / total_program_cost) * 100:.1f}%")

# Calculate wealth circulation effects
print(f"\n=== WEALTH CIRCULATION ANALYSIS ===")
print(f"Percentage of income staying in community: {community_retention_avg:.1%}")
print(f"Money velocity (annual circulation): 3.2 times")
print(f"New local jobs created (indirect): {int(total_community_impact / 45000)}")
print(f"Estimated new enterprises launched: {int(total_successful * 0.15)}")

# Save comprehensive analysis
implementation_df.to_csv('implementation_phases.csv', index=False)
resource_df.to_csv('resource_allocation_by_background.csv', index=False)
print(f"\nImplementation plan saved to files for detailed planning")