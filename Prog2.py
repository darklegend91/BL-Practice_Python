'''
Update the dictionary
Use copy()
Use update()
use | 
Use keys()
Use values()
Use items()
'''

def merge_dicts():
    friend_details ={"Name": "Aam" , "City" : "U.P." ,"Pin Code" : 177001 }
    
    contact_details = {'Phone' : 9856784510,
                       'Email': 'name@example.com'}
    
    #First Way using copy()
    merged_dict = friend_details.copy()
    merged_dict.update(contact_details)
    # print(merged_dict)
    
    
    #Using unpacking (**)
    merged_dict_unpacked = {**friend_details, **contact_details}
    print(merged_dict_unpacked)
    
    # Using | operator
    merged_dict_union = friend_details | contact_details
    print(merged_dict_union)
    
    
merge_dicts()