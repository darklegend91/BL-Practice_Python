import re # importing regex module

# match() ->> find first occurance at the beggining
# search() ->> serach for a word or pattern and return the first occurance
# findall() ->> find all occurences of a pattern or a word
# finditer() ->>

# Patterns:
# '\s' for whitespace characters
# \d for digits
# \D for non digits
# \S for non whitespace characters
# \w for alphanumberic
# \W for non alphanumberic like special symbols and whitespaces


quote ="I scream, you scream, we all scream for ice cream"
text_2 = "I had 2 apples and 603 oranges in @ 2024"

sceam_search = re.search("cream" , quote)
sceam_search_all = re.findall("cream" , quote)

print(sceam_search)
print(sceam_search_all)


digit_matches = re.findall(r'\d+', text_2)
print(digit_matches)
print(type(digit_matches))

digit_matches_1 = re.findall(r'\d{2}', text_2) # serach squence in pattern length 
print(digit_matches_1)
print(type(digit_matches_1))

no_digit_matches = re.findall(r'\D+', text_2) # serach squence in pattern length 
print(no_digit_matches)
print(type(no_digit_matches))

white_space_char = re.findall(r'\S+' , text_2)
print(white_space_char)

alpha_numeric_patterns = re.findall(r'\w+' , text_2)
print(alpha_numeric_patterns)

non_alpha_numeric_patterns = re.findall(r'\W+' , text_2)
print(non_alpha_numeric_patterns)