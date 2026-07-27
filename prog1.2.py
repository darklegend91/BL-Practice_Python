''''
PROG 1.2: Taking List From The User
Input =>
Enter the number of elements in the list: 3

Output =>

```
Enter the number of elements in the list: 3
Enter a number: A
Invalid input, please enter a valid number.
Enter a number: 1
Enter a number: 2
Enter a number: 3
The Original List is [1, 2, 3]
The Sum of the list using Custom function is 6
The Sum of the list using Builtin function is 6
Comparing the results of Custom function and Builtin function: True
```
'''

def custom_sum(numbers):
    total = 0

    for number in numbers:
        total += number

    return total


while True:
    try:
        number_of_elements = int(
            input("Enter the number of elements in the list: ")
        )

        if number_of_elements <= 0:
            raise ValueError

        break

    except ValueError:
        print("Invalid input, please enter a positive integer.")


numbers = []

while len(numbers) < number_of_elements:
    try:
        value = float(input("Enter a number: "))

        if value.is_integer():
            value = int(value)

        numbers.append(value)

    except ValueError:
        print("Invalid input, please enter a valid number.")


custom_result = custom_sum(numbers)
builtin_result = sum(numbers)

print(f"The Original List is {numbers}")
print(f"The Sum of the list using Custom function is {custom_result}")
print(f"The Sum of the list using Builtin function is {builtin_result}")
print(
    "Comparing the results of Custom function and Builtin function: "
    f"{custom_result == builtin_result}"
)