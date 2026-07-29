'''
Remove the data using functions
'''
friend_details ={"Name": "Aam" , "City" : "U.P." ,"Pin Code" : 177001 }
    
contact_details = {'Phone' : 9856784510,
                    'Email': 'name@example.com'}
    
merged_dict ={**friend_details ,**contact_details} 

print(f"The original dict is {merged_dict}")


# using del keyword 
if "Email" in merged_dict.keys():
     del merged_dict["Email"]
     
print(f"The dict after removing email is {merged_dict}")
     
merged_dict.pop("Pin Code")

print(f"The dict after removing Pin Code is {merged_dict}")