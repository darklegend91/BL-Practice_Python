'''
## PROG 4: To Remove Elements From The List

Removing Elements at particular position/index: Given a list colors, plan removing 0th, 2nd and 5th element from the list.

colors = [“Red”,”Green”, “Pink”, “Blue”, “Black”, ”Purple”, “Yellow”, “Magenta”, “Brown”]

revised_colors = [“Green”,  “Blue”, ”Purple”, “Yellow”, “Magenta”, “Brown”]

Input => \
Colors List :  ['Red', 'Green', 'Pink', 'Blue', 'Black', 'Purple', 'Yellow', 'Magenta', 'Brown']

Output =>

```
Colors List :  ['Red', 'Green', 'Pink', 'Blue', 'Black', 'Purple', 'Yellow', 'Magenta', 'Brown']

List After Removing Particular Elements : ['Green', 'Blue', 'Black', 'Yellow', 'Magenta', 'Brown']

```
'''


colors = ["Red","Green","Pink","Blue","Black","Purple","Yellow","Magenta","Brown"]

indexes_to_remove = {0, 2, 5}

revised_colors = [
    color
    for index, color in enumerate(colors)
    if index not in indexes_to_remove
]

print(f"Colors List: {colors}")
print(f"List After Removing Particular Elements: {revised_colors}")