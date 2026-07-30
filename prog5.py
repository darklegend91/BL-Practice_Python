'''
Employee Access Rights Update Based on Current Staff
=> A MIS person maintains a list of employees with access rights and another list representing the current employees.
=> Every month, few of the employees may move out and the current employees list gets updated on that day.
=> As a MIS person you would like to update the access list based on the current employees list.
=> Create a program to do this.

Input =>
Enter the employees with access rights (comma-separated): Alice, Bob, Charlie, David
Enter the current employees (comma-separated): bob, David, Emily

Output => \

Updated Access Rights List:
David
Bob
Hint =>
=> Use the intersection_update() method of a set.
'''
# PROG 5: Employee Access Rights Update Based on Current Staff

access_input = input(
    "Enter the employees with access rights (comma-separated): "
)

current_input = input(
    "Enter the current employees (comma-separated): "
)

employees_with_access = {
    employee.strip().lower()
    for employee in access_input.split(",")
    if employee.strip()
}

current_employees = {
    employee.strip().lower()
    for employee in current_input.split(",")
    if employee.strip()
}

# Retain access only for employees who are still working
employees_with_access.intersection_update(current_employees)

print("\nUpdated Access Rights List:")

for employee in sorted(employees_with_access):
    print(employee.title())