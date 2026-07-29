'''
PROG 4: Dynamic Dictionary Update with User Input for Friend Type Selection
=> In the above dictionary - plan adding “Country” as “India” as default value, “Friend-Type” as another key.
=> Possible values of Friend Type can be [“School”, “College”, “Neighbourhood”].
=> Initially do not add any value for “FriendType”
=> Print and see how the dictionary changes.
=> Define “Friend Type” based on one of the above options.
=> Print and check.
'''

def print_dict(dict_print: dict) -> None:
    
    print(f"Keys of the dict are: " , end="")
    for keys in dict_print.keys():
        print(f"{keys}" , end=", ")
    
    print()
        
    print(f"Values of the dict are: " , end=" ")
    for values in dict_print.values():
        print(f"{values}" , end=", ")
    
    print()
        
    print(f"Key value pairs of the dict are")
    for key , values in dict_print.items():
        print(f"{key} : {values}", end=", ")
    
    print()
    
friend_details ={"Name": "Aam" , "City" : "U.P." ,"Pin Code" : 177001 }
    
contact_details = {'Phone' : 9856784510,
                    'Email': 'name@example.com'}

friend_type_options = ["School" , "College" , "Neighbourhood"]
    
merged_dict ={**friend_details ,**contact_details} 

print(f"The original dict is \n")
print_dict(merged_dict)

merged_dict.setdefault("Country" ,"India")
print(f"The original dict after adding default county is \n ")
print_dict(merged_dict)

# Add friend type:
merged_dict.setdefault('Friend-Type' , '')

print_dict(merged_dict)

print(f"Select friend type from: { ''.join([f'\n{index+1}. {friend_type}' for index , friend_type in enumerate(friend_type_options)])}")
option = int(input())

if 1 <= option <=len(friend_type_options):
    print(f"Your Entered Choice is {option} .{friend_type_options[option-1]}")
    merged_dict["Friend-Type"] = friend_type_options[option-1]
else:
    print(f"Enter correct choice and it must be between 1 and {len(friend_type_options)}")
    
print("After adding friend type:")
print_dict(merged_dict)