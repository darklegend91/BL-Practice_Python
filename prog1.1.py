'''
## PROG 1: Sum A List

Write a custom function (custom_sum()) which takes a list of numbers as an input argument and returns the sum of all elements of the list

Check the answer received with the inbuilt function **sum** function.

Print True or False

Input =>** numbers = [29, 45, 32, 49, 37]

Output =>

```
The Original List is [29, 45, 32, 49, 37]
The Sum of the list using Custom function is 192
The Sum of the list using Builtin function is 192
Comparing the results of Custom function and Builtin function: True
```
'''

def custom_sum(og_list: list) -> float:
    sum_list = 0
    for num in og_list:
        sum_list +=num
    return sum_list

original_list = [29, 45, 32, 49, 37]

print(f"The Original List is {original_list}")

sum_custom = custom_sum(original_list)
print(f"The Sum of the list using Custom function is {sum_custom}")
    
builtin_sum = sum(original_list)
print(f"The Sum of the list using Builtin function is {builtin_sum}")

print(f"Comparing the results of Custom function and Builtin function: {builtin_sum == sum_custom}")