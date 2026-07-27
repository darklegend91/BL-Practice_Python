'''
## PROG 3: Lambda Function

Double the List: Given a list of numbers, plan creating a new list where all elements are double of the input list.
Note : Plan using lambda function here
Input => numbers = [1, 2, 3, 4, 5]
Output =>

```
Original list is [1, 2, 3, 4, 5]
Doubled list is [2, 4, 6, 8, 10]
```
> **Hint =>**
1. Use `lambda` function
2. Use `map` function
'''

numbers = [1, 2, 3, 4, 5]

doubled_list = list(
    map(lambda num: num * 2, numbers)
)

print(f"Original list is {numbers}")
print(f"Doubled list is {doubled_list}")