def count_chars(str_chk: str) -> tuple[int , int, int] :
    
    letters = sum(1 for char in str_chk if char.isalpha())
    digits = sum(1 for char in str_chk if char.isdigit())
    
    symbols = len(str_chk) - (letters + digits)

    return letters , digits , symbols

def main():
    str_chk = "P@fhjdsfhj%*&1234567890vdhkvhbd#"
    letters , digits , symbols = count_chars(str_chk)
    
    print(f"Number of letter is {letters}")
    print(f"Number of digits is {digits}")
    print(f"Number of special symbols is {symbols}")

if __name__ == "__main__" :
    main()