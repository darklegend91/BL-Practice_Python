friend_dict = {"Name": "Aam" , "City" : "U.P." ,"Pin Code" : 177001 }

# name_friend = input("ENter Name of the friend: ")
# city_friend = input("ENter city of the friend: ")
# pin_friend = input("ENter pin of the friend: ")

# friend_dict["name"] = name_friend
# friend_dict["city"] = city_friend
# friend_dict["pin"] = pin_friend

print(type(friend_dict))

print(f"\nPrinting details using keys:\n")
for key in friend_dict:
    print(f"{key} : {friend_dict[key]} ")

print(f"\nPrinting details using items():")

for key ,value in friend_dict.items():
    print(f"{key} : {value}")