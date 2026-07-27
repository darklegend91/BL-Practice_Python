''''
### PROG 2.1: By Using Slicing

Input => numbers = [29, 45, 32, 49, 37]

Output => 

```
The Original List is [29, 45, 32, 49, 37]
The Reversed List using slicing is [37, 49, 32, 45, 29]
```

'''

original_list = [29, 45, 32, 49, 37]

reversed_list = original_list[::-1]

print(f"The Original List is {original_list}")
print(f"The Reversed List using slicing is {reversed_list}")