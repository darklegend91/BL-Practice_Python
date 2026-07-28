'''
## PROG 5: To Check Email Address
Regex to check valid email address

TESTCASE 1:
Input => Enter an email address: `test@gmail.com`
Output => 
`test@gmail.com is a Valid Email Address.`

TESTCASE 2:
Input => Enter an email address: `test`
Output => 
`test is an Invalid Email Address.`

TESTCASE 3:
Input => Enter an email address: `test@`
Output => 
`test@ is an Invalid Email Address.`

TESTCASE 4:
Input => Enter an email address: `test@gmail`
Output => 
`test@gmail is an Invalid Email Address.`

TESTCASE 5:
Input => Enter an email address: `test@gmail.`
Output => 
`test@gmail. is an Invalid Email Address.`

TESTCASE 6:
Input => Enter an email address: `testgmail.com`
Output => 
`testgmail.com is an Invalid Email Address.`

TESTCASE 7:
Input => Enter an email address: `@yahoo.in`
Output => 
`@yahoo.in is an Invalid Email Address.`
'''
import re

def check_emiail(email:str) ->bool :
    
    pattern = r'^[a-zA-z0-9._%+-]+@[a-zA-z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern , email):
        return True
    else:
        return False

# email = input("enter address to be checked: ")
email = "adimail.com"

result = "Valid" if check_emiail(email) else "Not Valid"
print(f"The email is {result}")