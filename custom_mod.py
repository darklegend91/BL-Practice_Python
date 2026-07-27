def add(num1: float, num2: float) -> float:
    return num1 + num2

def sub(num1: float, num2: float) -> float:
    return num1 - num2

def mul(num1: float, num2: float) -> float:
    return num1 * num2

def div(divident: float, divisor: float) -> float:
    try:
        res = divident / divisor
        return res
    
    except ZeroDivisionError as err:
        print(f"Error {err} occured!!")
        return 0

 
def power(base: float, exp: float) -> float:
    return base ** exp