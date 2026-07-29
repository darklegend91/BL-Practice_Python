'''
Python Dictionary Cheat Sheet

Dictionary is a mutable python data type which stores data in form of key value pairs

CODIN CONCEPTS

1: Standard IO (stdio) - stdio stands for Standard Input and Output.

2: Formatted string literal, or f-string -

An f-string looks very much like a typical Python string except that it's prepended by the character f'' or F''
The magic of f-strings is that you can embed Python expressions directly inside them by using curly braces {}.
The expression is evaluated and converted to string representation, and the result is interpolated into the original string in that location
3: Python Data Types - Data types define the kind of data that can be stored in memory for a variable. In Python Data Types are implicitly assigned. For Python all built-in data types belongs to Python class. They can be categorized as either

Primitive Data Types - int, float, str, bool

Derived Data Types - list, dict, set, tuple

4: Python Explicit Type Conversion - Type conversion is converting from one data type to another. Explicit type conversion is achieved through Python's built-in functions such as int(), float(), and str().

5: Python Constant - Constants are types of variables whose values cannot be altered or changed after initialization. These values are universally proven to be true and they cannot be changed over time. e.g. PI = 22/7

Naming Convention to define Constant is all caps
Python constants are declared and initialized in the beginning of the program as global or preferably in different modules/files.
6: Python Format Specifier -

Formatting float variables as string with Format Specifier expression like {number:.2f}.
Formatting integer variables as string with Format Specifier expression like {number:02d}.
7: Python Operator - Operators are special symbols that perform operations on variables and values. They are

Arithmetic Operators like Add is +, Subtract is -, Multiply is *, Power is **...
Assignment Operator = used in assigning value to a variable
Comparison Operator to compare 2 values like ==, !=, >= ...
Logical Operator used in expression and, or, and not
Bitwise operators for bit operations &, |,...
Special Operators for memory comparison like is & is not
8: Python Operator Precedence - In Python, the order of operations follows the same principles as PEMDAS.

PEMDAS is an acronym that stands for “Parentheses, Exponents, Multiplication and Division, and Addition and Subtraction”
That is, expressions inside parentheses are evaluated first, followed by exponents, then multiplication and division (from left to right), and finally addition and subtraction (from left to right).
9: Conditional Operation - The conditional operation simply allows testing a condition in a single line replacing the multiline if-else making the code compact. It predominantly uses Comparison Operator and Logical Operators

10: Python Shorthand If Else - If you have only one condition to execute, one for if, and one for else, you can put it all on the same line using Python Shorthand as in gender == 'male' and 'his' or 'her'

Comparison Operator - Please note the use of Comparison Operator == to check the gender is 'male'
11: String Formatting Expression - We use the followimg String formatting expressions

{'Item Code':^10} is a string formatting expression used to center-align the text "Item Code" within a field width of 10 characters. Here's what each part of the expression means:
{'-' * 74} is used to repeat the character '-' 74 times. This is because of the multiplier operator *
{' ' * 54} is used to repeat space character ' ' 54 times due to operator *
12: Python Functions - A function is a block of code which only runs when it is called. You can pass data, known as parameters, into a function.

def keyword is used to create a function, followed by function name, the parameters in parenthesis follwed by : to indicate function block as can be seen in the figure below


Function Definition

13: DRY PRICIPLE - DRY is a software development principle that stands for “Don't Repeat Yourself.” Living by this principle means that your aim is to reduce repetitive patterns and duplicate code and logic in favor of modular and referenceable code.

14: Python Modules - Python Module is a file that contains built-in functions, classes,its and variables. There are many Python modules, each with its specific work.

Some of the frequently used functions from certain built-in modules.

os module
random module
math module
time module
sys module
collections module
statistics module
15: Python List - Python Lists are just like dynamically sized arrays, declared in other languages (vector in C++ and ArrayList in Java). In simple language, a list is a collection of things, enclosed in [ ] and separated by commas.

16: Python RegEx Module - A Regular Expression or RegEx is a special sequence of characters that uses a search pattern to find a string or set of strings.

17: Python Dictionary - It can detect the presence or absence of a text by matching it with a particular pattern and also can split a pattern into one or more sub-patterns.
=> A Python dictionary is a data structure that stores the value in key: value pairs.
=> This makes it different from lists, tuples, and arrays as in a dictionary each key has an associated value.
=> Python dictionaries are essential for efficient data mapping and manipulation in programming.
=> A dictionary is a collection which is ordered*, changeable and do not allow duplicates.
'''
