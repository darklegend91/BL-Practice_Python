import re
text1 = "I have 2 apples and 5 oranges."

digits_in_text = re.findall( r'\W+', text1)

print(digits_in_text)