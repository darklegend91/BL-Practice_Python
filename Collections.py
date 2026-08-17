from collections import Counter , defaultdict , deque , namedtuple
"""
    The collections module has 
    1. Counter
    2. Defaultdict
    3. Deque
    4. namedtuple
    
    User Dict
    Order Dict
    Chain Map
    Named Tuple
    User String
    User List
"""

# -------------------------------------------------- Counter --------------------------------------------------
""" 
Counter is a specialised dictioanry to maintain a specialised dictionary has update() ,  mostcommon() ,  elements {repeat the characters} and add and subtract methods and + and - 
"""

list1 = [2 , 5 ,6,7,8,3,4,5,6,7,9,0]

counter_dict = Counter(list1)


# -------------------------------------------------- Default Dict --------------------------------------------------
"""
    it is a dicioanry that when acessing a value that is not in dictioanry keys dont h=give KeyError but give a default value
"""

my_dict = defaultdict(list)
# print(my_dict.default_factory)

#  Custom default values :

def my_custom_dict () -> dict[str , object] :
    return {
        "marks" : 0,
        "passed": False
    }

my_dict_2 = defaultdict(my_custom_dict)

# print(my_dict_2["Student1"])


words = [
    "apple",
    "ant",
    "banana",
    "ball",
    "cat",
]

words_dict = defaultdict(list)

for word in words:
    words_dict[word[0]].append(word)

# for letter , word in words_dict.items():
#     print(f"{letter} : {", ".join(word)}")

# -------------------------------------------------- Deque --------------------------------------------------
""" 
This is a double sided queue that allows efficient insertion and deletion from both ends. 
insert end      -> append(element)      -> O(1)
insert start    -> appendleft(element)  -> O(1)
pop end         -> pop ()               -> O(1)
pop start       -> popleft ()           -> O(1)

roatate function

Max length -> add the new elemnts once overflowed but remove from left in append function

"""

q = deque(
    ["Aman", "Riya", "Kabir", "Meera"]
)

q.popleft()
q.appendleft("Rahul")
q.append("Teacher")

# print(f"{" ,".join(q)}")

# -------------------------------------------------- namedtuple --------------------------------------------------
""" 

"""

t= ( "Aman" , 100 , True)

nt= namedtuple(
    "Student" ,
    [
        "name" , 
        "roll number",
        "passed"
    ]
)

student = nt["Aman , "]