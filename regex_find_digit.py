import re
text1 = "I have 2 applesx and 5 oranges."

digits_in_text = re.findall( r'\d', text1)

print(digits_in_text)