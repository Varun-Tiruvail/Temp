import pandas as pd
import random
import string
import os

def generate_password(length=10):
    """Generate a random password with specified length."""
    # Include lowercase, uppercase, numbers, and some special characters
    characters = string.ascii_lowercase + string.ascii_uppercase + string.digits + "!@#$%&*"
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

def generate_username(first_names, last_names):
    """Generate a username based on first and last names."""
    first = random.choice(first_names)
    last = random.choice(last_names)
    
    # Different username formats
    formats = [
        f"{first.lower()}.{last.lower()}",
        f"{first.lower()}{random.randint(1, 999)}",
        f"{first[0].lower()}{last.lower()}",
        f"{first[0].lower()}{last.lower()}{random.randint(10, 99)}",
        f"{last.lower()}.{first.lower()}"
    ]
    
    return random.choice(formats)

def generate_credentials(num_users=10, output_file="login_details.xlsx"):
    """Generate credentials for specified number of users and save to Excel."""
    
    # Sample names for generating usernames
    first_names = [
        "John", "Jane", "Michael", "Emily", "David", "Sarah", "Robert", "Lisa", 
        "Richard", "Jennifer", "William", "Linda", "Daniel", "Barbara", "Charles", 
        "Jessica", "Thomas", "Susan", "Joseph", "Margaret"
    ]
    
    last_names = [
        "Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller", "Wilson", 
        "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", 
        "Martin", "Thompson", "Garcia", "Martinez", "Robinson"
    ]
    
    # Generate credentials
    credentials = []
    for _ in range(num_users):
        username = generate_username(first_names, last_names)
        password = generate_password()
        credentials.append({"username": username, "password": password})
    
    # Create DataFrame and save to Excel
    df = pd.DataFrame(credentials)
    df.to_excel(output_file, index=False)
    
    print(f"Generated {num_users} credentials and saved to {output_file}")
    print("\nSample credentials:")
    for i, cred in enumerate(credentials[:3], 1):
        print(f"{i}. Username: {cred['username']}, Password: {cred['password']}")
    print("...")

if __name__ == "__main__":
    # Number of user credentials to generate
    num_users = int(input("Enter the number of users to generate (default 10): ") or 10)
    
    # Output file name
    output_file = input("Enter output file name (default 'login_details.xlsx'): ") or "login_details.xlsx"
    
    generate_credentials(num_users, output_file)