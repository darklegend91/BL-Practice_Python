import random

def generate_employees(num_employees=10):
    """Generate random employee data"""
    
    # Sample data for random generation
    first_names = ['John', 'Jane', 'Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Henry']
    last_names = ['Doe', 'Smith', 'Brown', 'White', 'Black', 'King', 'Lee', 'Woods', 'Green', 'Taylor']
    
    genders = ['M', 'F']
    ages = list(range(22, 55))
    
    degrees = ['BE', 'ME', 'BSc', 'MSc', 'BTech', 'MTech']
    streams = ['Computer Science', 'IT', 'Electronics', 'Mechanical', 'Civil', 'Electrical']
    
    languages_pool = ['Python', 'Java', 'C++', 'JavaScript', 'Go', 'Rust', 'Ruby', 'C#']
    tools_pool = ['Git', 'Docker', 'Kubernetes', 'Jenkins', 'AWS', 'Azure', 'Linux', 'MySQL', 'MongoDB']
    
    departments = ['Development', 'QA', 'DevOps', 'Product Management']
    roles = {
        'Development': ['Developer', 'Senior Developer', 'Lead Developer'],
        'QA': ['QA Engineer', 'Senior QA Engineer'],
        'DevOps': ['DevOps Engineer', 'Senior DevOps Engineer'],
        'Product Management': ['Product Manager', 'Associate Product Manager']
    }
    
    employees = []
    
    for emp_id in range(1, num_employees + 1):
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        gender = random.choice(genders)
        age = random.choice(ages)
        
        # Mobile numbers (10 digits)
        mobile = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        additional_mobile = ''.join([str(random.randint(0, 9)) for _ in range(10)]) if random.choice([True, False]) else None
        
        # Education
        degree = random.choice(degrees)
        stream = random.choice(streams)
        year = random.randint(2010, 2023)
        percentage = random.randint(60, 95)
        
        # Skills - each employee knows 2-4 languages and 2-5 tools
        num_languages = random.randint(2, 4)
        num_tools = random.randint(2, 5)
        languages = random.sample(languages_pool, num_languages)
        tools = random.sample(tools_pool, num_tools)
        
        # Department
        dept = random.choice(departments)
        role = random.choice(roles[dept])
        
        employee = {
            'id': emp_id,
            'name': name,
            'personal_information': {
                'gender': gender,
                'age': age,
                'mobile_number': mobile,
                'additional_mobile_number': additional_mobile
            },
            'education_information': {
                'Degree': degree,
                'Degree_Stream': stream,
                'Year_of_passout': year,
                'total_percentage': percentage
            },
            'skills_information': {
                'languages': languages,
                'tools': tools
            },
            'department_information': {
                'name_of_dept': dept,
                'role': role
            }
        }
        employees.append(employee)
    
    return employees

def analyze_employee_data(employees):
    """Analyze and display employee data statistics"""
    
    # Gender distribution
    male_count = sum(1 for e in employees if e['personal_information']['gender'] == 'M')
    female_count = len(employees) - male_count
    
    # Age distribution
    age_less_25 = 0
    age_25_35 = 0
    age_above_35 = 0
    
    for emp in employees:
        age = emp['personal_information']['age']
        if age < 25:
            age_less_25 += 1
        elif 25 <= age <= 35:
            age_25_35 += 1
        else:
            age_above_35 += 1
    
    # Number of developers
    developers = [emp for emp in employees if 'Developer' in emp['department_information']['role']]
    
    # Java and Python knowledge
    java_knowers = []
    python_knowers = []
    both_knowers = []
    
    for emp in employees:
        languages = emp['skills_information']['languages']
        knows_java = 'Java' in languages
        knows_python = 'Python' in languages
        
        if knows_java:
            java_knowers.append(emp['name'])
        if knows_python:
            python_knowers.append(emp['name'])
        if knows_java and knows_python:
            both_knowers.append(emp['name'])
    
    # Print results
    print("="*60)
    print("EMPLOYEE DATA ANALYSIS")
    print("="*60)
    
    print("\nGender Distribution Ratio:")
    print(f"Male: {male_count}")
    print(f"Female: {female_count}")
    
    print("\nAge Distribution:")
    print(f"Less than 25: {age_less_25}")
    print(f"25-35: {age_25_35}")
    print(f"Above 35: {age_above_35}")
    
    print(f"\nNumber of Developers: {len(developers)}")
    
    print("\nNames of Employees who know Java:")
    print(java_knowers)
    
    print("\nNames of Employees who know Python:")
    print(python_knowers)
    
    print("\nNames of Employees who know both Java and Python:")
    print(both_knowers)

def display_employee_details(employee):
    """Display detailed information about a single employee"""
    print("-"*60)
    print(f"ID: {employee['id']}")
    print(f"Name: {employee['name']}")
    print("\nPersonal Information:")
    for key, value in employee['personal_information'].items():
        print(f"  {key}: {value}")
    print("\nEducation Information:")
    for key, value in employee['education_information'].items():
        print(f"  {key}: {value}")
    print("\nSkills Information:")
    print(f"  Languages: {', '.join(employee['skills_information']['languages'])}")
    print(f"  Tools: {', '.join(employee['skills_information']['tools'])}")
    print("\nDepartment Information:")
    for key, value in employee['department_information'].items():
        print(f"  {key}: {value}")
    print("-"*60)

def main():
    """Main function"""
    # Generate employee data
    employees = generate_employees(10)
    
    print("\nEMPLOYEE DATABASE")
    print("="*60)
    
    # Analyze data
    analyze_employee_data(employees)
    
    # Display first employee details as sample
    print("\n" + "="*60)
    print("DETAILED VIEW OF FIRST EMPLOYEE")
    display_employee_details(employees[0])

if __name__ == "__main__":
    main()