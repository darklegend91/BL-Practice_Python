friend_dict = {"Name": input("enter the friend Name: "),
               "City" : input("enter the friend City: "),
               "Pin Code" : input("enter the friend Pincode : ") }


print(type(friend_dict))

print(f"\nPrinting details using keys:\n")
for key in friend_dict:
    print(f"{key} : {friend_dict[key]} ")

print(f"\nPrinting details using items():")

for key ,value in friend_dict.items():
    print(f"{key} : {value}")