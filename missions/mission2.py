from algorithms import binarySearch

def findTreasure(list_ids : list[int]):
    try:
        target = int(input("Enter the Treasure id to find: "))

        index = binarySearch(list_ids, target)

        if index == -1:
            print("Treasure not Found!")

        else:
            print(f"""
        Treasure Found!
        Index : {index}""")

    except ValueError:
        print("Enter only Integer Value")
