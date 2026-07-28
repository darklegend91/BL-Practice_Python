text_1 = 'Hello World!!'
print(text_1)
print(type(text_1))
print(len(text_1))
print()

text_2 = "This is my brothers's dog" # to use single single quote without \
print(text_2)
print(type(text_2))
print(len(text_2))
print()


text_3 = """This is a new car t t
                    This has a V6 Engine.""" # remember the spaces nand new lines  
print(text_3)
print(type(text_3))
print(len(text_3))
print()
''''
.isupper()
.islower()
.lower()
.upper()
.isalpha()
.isdigit()
.title()
.count(alphabet to be counted)
.replace("what", "with_what")
'''

print(text_3.count('T')) # Case sensitive

places_list = []

for i in range(5):
    place = input(f"ENter the {i+1} place name: ")
    places_list.append(place)

print(places_list)

places_str = ', '.join(place.upper() for place in places_list)
print(places_str)

'''
Slicing in Strings:
str[start : end : step]
By deault it start at start of string , end at end of string and step of 1 
'''
