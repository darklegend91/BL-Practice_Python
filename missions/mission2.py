from algorithms import binarySearch
TREASURE_BONUS = 100

def findTreasure(list_ids : list[int]):
    try:
        target = int(input("Enter the Treasure id to find: "))

        index = binarySearch(list_ids, target)

        if index == -1:
            print("Treasure not Found!")
            return 0

        else:
            print(f"""
        Treasure Found!
        Index : {index}""")
            return TREASURE_BONUS

    except ValueError:
        print("Enter only Integer Value")
        return 0
