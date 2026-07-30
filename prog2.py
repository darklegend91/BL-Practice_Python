'''
PROG 2 : Fruit Store Inventory Management System
=> A fruit store has a set of items which are in stock and a set of items which are out of stock.

in_stock = {'apple','watermelon','strawberry' }
out_of_stock = {'banana', 'orange', 'guava'}
Carry out the following : \

Check if 'apple' is in stock or not. Do the same check for mango
Find out the possible items which the fruit store keeps.
Print them one by one in a new line.
By evening the banana comes up in the store.
Update the instock and out of stock accordingly
Create a function which updates in_stock and out_of_stock, when an item comes in the stock or goes out of stock.
Input =>
Initial sets of in-stock and out-of-stock items in_stock = {'apple', 'watermelon', 'strawberry'} out_of_stock = {'banana', 'orange', 'guava'}

Output =>

--- Fruit Store Inventory Management ---
1. Check if a fruit is in stock
2. List all items in the store
3. Update stock (add/remove item)
4. Exit

Enter your choice (1-4): 2

The possible items that the store keeps are:
Apple
Orange
Guava
Watermelon
Banana
Strawberry

--- Fruit Store Inventory Management ---
1. Check if a fruit is in stock
2. List all items in the store
3. Update stock (add/remove item)
4. Exit

Enter your choice (1-4): 1
Enter the name of the fruit to check: Apple
Apple is in stock.

--- Fruit Store Inventory Management ---
1. Check if a fruit is in stock
2. List all items in the store
3. Update stock (add/remove item)
4. Exit

Enter your choice (1-4): Banana
Invalid choice. Please select a valid option.

--- Fruit Store Inventory Management ---
1. Check if a fruit is in stock
2. List all items in the store
3. Update stock (add/remove item)
4. Exit

Enter your choice (1-4): 1
Enter the name of the fruit to check: Banana
Banana is not in stock.

--- Fruit Store Inventory Management ---
1. Check if a fruit is in stock
2. List all items in the store
3. Update stock (add/remove item)
4. Exit

Enter your choice (1-4): 1
Enter the name of the fruit to check: watermelon
Watermelon is in stock.

--- Fruit Store Inventory Management ---
1. Check if a fruit is in stock
2. List all items in the store
3. Update stock (add/remove item)
4. Exit

Enter your choice (1-4): 3
Enter the name of the fruit: banana
Enter 'in' if the item is now in stock or 'out' if it is out of stock: in

Banana has been added to in-stock.

--- Fruit Store Inventory Management ---
1. Check if a fruit is in stock
2. List all items in the store
3. Update stock (add/remove item)
4. Exit

Enter your choice (1-4): 2

The possible items that the store keeps are:
Apple
Orange
Guava
Watermelon
Banana
Strawberry

--- Fruit Store Inventory Management ---
1. Check if a fruit is in stock
2. List all items in the store
3. Update stock (add/remove item)
4. Exit

Enter your choice (1-4): 1
Enter the name of the fruit to check: banana
Banana is in stock.

--- Fruit Store Inventory Management ---
1. Check if a fruit is in stock
2. List all items in the store
3. Update stock (add/remove item)
4. Exit

Enter your choice (1-4): 4
Exiting the program. Goodbye!
'''

# PROG 2: Fruit Store Inventory Management System

in_stock = {"apple", "watermelon", "strawberry"}
out_of_stock = {"banana", "orange", "guava"}


def check_stock(item):
    """Check whether an item is currently in stock."""
    item = item.strip().lower()

    if item in in_stock:
        return f"{item.title()} is in stock."

    if item in out_of_stock:
        return f"{item.title()} is not in stock."

    return f"{item.title()} is not available in the store."


def list_items():
    """Print all items kept by the store."""
    all_items = in_stock.union(out_of_stock)

    print("\nThe possible items that the store keeps are:")

    for item in sorted(all_items):
        print(item.title())


def update_stock(item, status):
    """Move an item to the in-stock or out-of-stock set."""
    item = item.strip().lower()
    status = status.strip().lower()

    if status == "in":
        out_of_stock.discard(item)
        in_stock.add(item)
        return f"{item.title()} has been added to in-stock."

    if status == "out":
        in_stock.discard(item)
        out_of_stock.add(item)
        return f"{item.title()} has been added to out-of-stock."

    return "Invalid stock status. Enter either 'in' or 'out'."


while True:
    print("\n--- Fruit Store Inventory Management ---")
    print("1. Check if a fruit is in stock")
    print("2. List all items in the store")
    print("3. Update stock (add/remove item)")
    print("4. Exit")

    choice = input("\nEnter your choice (1-4): ").strip()

    if choice == "1":
        fruit = input("Enter the name of the fruit to check: ")
        print(check_stock(fruit))

    elif choice == "2":
        list_items()

    elif choice == "3":
        fruit = input("Enter the name of the fruit: ")
        stock_status = input(
            "Enter 'in' if the item is now in stock or "
            "'out' if it is out of stock: "
        )

        print("\n" + update_stock(fruit, stock_status))

    elif choice == "4":
        print("Exiting the program. Goodbye!")
        break

    else:
        print("Invalid choice. Please select a valid option.")