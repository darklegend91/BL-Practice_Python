import random

def generate_student_data(num_students=20):
    """Generate random student data"""
    students = []
    names = [f"Student{i}" for i in range(1, num_students + 1)]
    
    for name in names:
        # Generate random marks between 0.0 and 50.0
        physics = round(random.uniform(0.0, 50.0), 1)
        chemistry = round(random.uniform(0.0, 50.0), 1)
        maths = round(random.uniform(0.0, 50.0), 1)
        
        # Generate random attendance between 1 and 120
        attendance = random.randint(1, 120)
        
        # Generate random gender
        gender = random.choice(['M', 'F'])
        
        # Calculate totals
        total_marks = physics + chemistry + maths
        percentage = round((total_marks / 150) * 100, 2)
        attendance_percentage = round((attendance / 120) * 100, 2)
        
        # Determine grade
        if percentage > 90:
            grade = 'A+'
        elif 80 <= percentage <= 90:
            grade = 'A'
        elif 60 <= percentage < 80:
            grade = 'B'
        elif 50 <= percentage < 60:
            grade = 'C'
        elif 30 <= percentage < 50:
            grade = 'D'
        else:
            grade = 'F'
        
        # Determine remark
        remark = "Congratulations!, Passed Successfully" if percentage >= 30 else "Failed, work hard to do better next time"
        
        student = {
            'name': name,
            'gender': gender,
            'marks': {
                'Physics': physics,
                'Chemistry': chemistry,
                'Maths': maths
            },
            'attendance': attendance,
            'total_marks': total_marks,
            'percentage': percentage,
            'attendance_percentage': attendance_percentage,
            'grade': grade,
            'remark': remark
        }
        students.append(student)
    
    return students

def display_student_details(student):
    """Display individual student details"""
    print("-" * 50)
    print(f"Name: {student['name']}")
    print(f"Gender: {student['gender']}")
    print("Marks:")
    for subject, marks in student['marks'].items():
        print(f"- {subject}: {marks}")
    print(f"Attendance: {student['attendance']}")
    print(f"Total Marks: {student['total_marks']}/150")
    print(f"Percentage Marks: {student['percentage']}%")
    print(f"Attendance: {student['attendance']}")
    print(f"Grade: {student['grade']}")
    print(f"Remarks: {student['remark']}")

def display_by_percentage(students):
    """Display students sorted by percentage"""
    sorted_students = sorted(students, key=lambda x: x['percentage'], reverse=True)
    for student in sorted_students:
        display_student_details(student)

def display_by_grade(students):
    """Display students grouped by grade"""
    grade_order = {'A+': 0, 'A': 1, 'B': 2, 'C': 3, 'D': 4, 'F': 5}
    sorted_students = sorted(students, key=lambda x: grade_order[x['grade']])
    
    current_grade = None
    for student in sorted_students:
        if student['grade'] != current_grade:
            current_grade = student['grade']
            print(f"\n{'='*20} Grade: {current_grade} {'='*20}")
        display_student_details(student)

def generate_summary(students):
    """Generate comprehensive summary"""
    total_students = len(students)
    
    # Overall Pass Percentage
    passed = [s for s in students if s['percentage'] >= 30]
    pass_percentage = round((len(passed) / total_students) * 100, 1)
    
    # Grade-wise distribution
    grade_distribution = {}
    for grade in ['A+', 'A', 'B', 'C', 'D', 'F']:
        count = sum(1 for s in students if s['grade'] == grade)
        grade_distribution[grade] = round((count / total_students) * 100, 1)
    
    # Top student overall
    top_student = max(students, key=lambda x: x['percentage'])
    
    # Top students subject-wise
    subject_toppers = {}
    for subject in ['Physics', 'Chemistry', 'Maths']:
        topper = max(students, key=lambda x: x['marks'][subject])
        subject_toppers[subject] = topper['name']
    
    # Passed students alphabetically
    passed_alphabetical = sorted(passed, key=lambda x: x['name'])
    
    # Passed students by marks
    passed_by_marks = sorted(passed, key=lambda x: x['total_marks'], reverse=True)
    
    # Print Summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"Overall Pass Percentage: {pass_percentage}%")
    print("\nGrade-wise Percentage Distribution:")
    for grade, percentage in grade_distribution.items():
        print(f"- Grade {grade}: {percentage}%")
    
    print(f"\nTop Student: {top_student['name']}")
    
    print("\nTop Students Subject-wise:")
    for subject, name in subject_toppers.items():
        print(f"- {subject}: {name}")
    
    print("\nList of Students Who Passed (Alphabetically sorted):")
    for student in passed_alphabetical:
        print(f"- {student['name']}: {student['percentage']}% ({student['grade']})")
    
    print("\nList of Students Who Passed (Sorted based on Total Marks):")
    for student in passed_by_marks:
        print(f"- {student['name']}: {student['total_marks']}/150 ({student['percentage']}%, {student['grade']})")

def main():
    """Main function"""
    # Generate student data
    students = generate_student_data(20)
    
    # User input
    choice = input("Enter 'grade' to display results by grade or 'percentage' to display results by percentage: ").lower()
    
    if choice == 'percentage':
        display_by_percentage(students)
    elif choice == 'grade':
        display_by_grade(students)
    else:
        print("Invalid choice! Displaying by percentage by default.")
        display_by_percentage(students)
    
    # Generate summary
    generate_summary(students)

if __name__ == "__main__":
    main()