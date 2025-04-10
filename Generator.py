import pandas as pd
import random
from faker import Faker

def generate_hierarchy():
    fake = Faker()
    
    # Create the superuser
    superuser = fake.unique.first_name()
    hierarchy = []
    
    # Level 1 (direct reports to superuser)
    level1 = [fake.unique.first_name() for _ in range(random.randint(3, 5))]
    for emp in level1:
        hierarchy.append({'Manager': superuser, 'Reportee': emp})
    
    # Level 2
    level2 = []
    for manager in level1:
        num_subordinates = random.randint(2, 4)
        subordinates = [fake.unique.first_name() for _ in range(num_subordinates)]
        level2.extend(subordinates)
        for emp in subordinates:
            hierarchy.append({'Manager': manager, 'Reportee': emp})
    
    # Level 3
    level3 = []
    for manager in level2:
        # Only create subordinates for some managers to limit size
        if random.random() > 0.4:  # 60% chance to have subordinates
            num_subordinates = random.randint(2, 3)
            subordinates = [fake.unique.first_name() for _ in range(num_subordinates)]
            level3.extend(subordinates)
            for emp in subordinates:
                hierarchy.append({'Manager': manager, 'Reportee': emp})
    
    # Level 4
    for manager in level3:
        # Even fewer managers have subordinates at this level
        if random.random() > 0.7:  # 30% chance to have subordinates
            num_subordinates = random.randint(2, 3)
            subordinates = [fake.unique.first_name() for _ in range(num_subordinates)]
            for emp in subordinates:
                hierarchy.append({'Manager': manager, 'Reportee': emp})
    
    return hierarchy

# Generate the hierarchy data
hierarchy_data = generate_hierarchy()

# Create DataFrame and save to Excel
df = pd.DataFrame(hierarchy_data)
df.to_excel('employee_hierarchy.xlsx', index=False)

print("Excel file 'employee_hierarchy.xlsx' has been generated successfully!")