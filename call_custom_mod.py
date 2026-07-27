import custom_mod as cm

first_num = float(input("Enter first Value: "))
second_num = float(input("Enter second Value: "))

print(f" Sum of {first_num} and {second_num} is {cm.add(first_num , second_num)}")
print(f" Subreaction of {first_num} and {second_num} is {cm.sub(first_num , second_num)}")
print(f" Product of {first_num} and {second_num} is {cm.mul(first_num , second_num)}")
print(f" Division of {first_num} and {second_num} is {cm.div(first_num , second_num)}")
print(f" Power of {first_num} to {second_num} is {cm.power(first_num , second_num)}")