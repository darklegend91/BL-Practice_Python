'''
List methods
'''

num_list = []
print(num_list.__doc__)

'''
For Insertion
Append, Extend ,Insert
'''

# Add one value to last of the list
num_list.append(45)

print(num_list)

#Add a list to old list
num_list.extend([34 , 56 , 78 , 90])
print(num_list)

#add a element at a given position
num_list.insert(3,121)
print(num_list)


'''
For Deletion
remove , pop , del , clear
'''

print(num_list.remove(56))
print(num_list)
print(len(num_list))

#Pop also stores the value
print(num_list.pop(3))
print(num_list)
print(len(num_list))

#clear deletes whole list
num_list.clear()
print(num_list)
print(len(num_list))

num_list=[45, 34, 56, 121, 78, 90 , 56] #
#delete in list
del num_list[2]
print(num_list)
print(len(num_list))

'''
For comprehension
range 
in keyword
enumurate
'''

for num in num_list:
    print(num , end =" ")

print()

for index , value in enumerate(num_list):
    print(f"List hold {value} at {index} index.")
    
for i in range (0 , len(num_list) , 1):
    print (num_list[i])


'''
List Functions
sort , reverse , count , index
'''

print(f"Original list is: {num_list}")
num_list.sort()
print(f"Sorted List is {num_list}")


num_list.reverse()
print(f"Reversed Sorted list is {num_list}")

