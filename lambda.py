'''
Learn Lambda Function in Python.
Lambda function is used to define inline functions.

Map returns a map object.
To get a list from map use list(map())
'''

original_list = [1 , 2, 3,4,5]
str1 = "string"

upper  = lambda string: string.upper()
maxEle = lambda a , b , c : max(a , b,c)
double_list = list(map(lambda x : x*2 , original_list))


print(upper(str1))
print(maxEle(2 , 4 , 5))
print(double_list)