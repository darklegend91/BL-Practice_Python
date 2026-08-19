def bubble_sort(num_list: list[int]) -> None:
    """
    Bubble Sort sorts the list in place.
    Larger elements move toward the end of the list.
    """

    n = len(num_list)

    for i in range(n - 1):
        for j in range(0, n - i - 1):

            if num_list[j] > num_list[j + 1]:
                num_list[j], num_list[j + 1] = ( num_list[j + 1], num_list[j] )


def selection_sort(num_list: list[int]) -> None:
    """
    Selection Sort sorts the list in place.
    """

    n = len(num_list)

    for i in range(n):
        mini = i

        for j in range(i + 1, n):

            if num_list[j] < num_list[mini]:
                mini = j

        num_list[mini], num_list[i] = ( num_list[i], num_list[mini] )


# -------------------------
# Merge Sort
# -------------------------

def merge_sort(num_list: list[int]) -> list[int]:

    if len(num_list) <= 1:
        return num_list

    mid = len(num_list) // 2

    left_half = num_list[:mid]
    right_half = num_list[mid:]

    left_half = merge_sort(left_half)
    right_half = merge_sort(right_half)

    return merge(left_half, right_half)


def merge(left: list[int], right: list[int]) -> list[int]:

    new = []

    i = 0
    j = 0

    while i < len(left) and j < len(right):

        if left[i] < right[j]:
            new.append(left[i])
            i += 1

        else:
            new.append(right[j])
            j += 1

    new.extend(left[i:])
    new.extend(right[j:])

    return new


def quick_sort(
    num_list: list[int],
    low: int,
    high: int
) -> None:
    """
    Quick Sort sorts the list in place.

    Elements smaller than the pivot are moved left,
    and larger elements are moved right.
    """

    if low < high:

        pivot = partition(num_list, low, high)

        quick_sort(
            num_list,
            low,
            pivot - 1
        )

        quick_sort(
            num_list,
            pivot + 1,
            high
        )


def partition(
    num_list: list[int],
    low: int,
    high: int
) -> int:

    pivot = num_list[low]

    i = low + 1
    j = high

    while True:

        while i <= j and num_list[i] <= pivot:
            i += 1

        while i <= j and num_list[j] >= pivot:
            j -= 1

        if i <= j:

            num_list[i], num_list[j] = (
                num_list[j],
                num_list[i]
            )

        else:
            break

    num_list[low], num_list[j] = (
        num_list[j],
        num_list[low]
    )

    return j

def binarySearch(num_list: list[int] , target : int):
    
    left = 0
    right = len(num_list) - 1

    while left <= right:
        mid = left + (right - left) //2
    
        if num_list[mid] == target:
            return mid
        
        elif num_list[mid] > target :
            right = mid - 1
            
        else:
            left = mid + 1
    
    return -1