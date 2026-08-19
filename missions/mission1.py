from algorithms import (
    quick_sort,
    merge_sort,
    selection_sort,
    bubble_sort
)

def console_mission1():

    score_list = [40, 30, 20, 10]

    print("\n===== MISSION 1 =====")
    print("Original Scores:", score_list)

    while True:

        choice = input(
            """
Choose Sorting Algorithm:

1. Selection Sort
2. Bubble Sort
3. Quick Sort
4. Merge Sort

Enter Choice: """
        )

        # Selection Sort
        if choice == "1":

            selection_sort(score_list)

            sorted_array = score_list

            algorithm = "Selection Sort"

            break

        # Bubble Sort
        elif choice == "2":

            bubble_sort(score_list)

            sorted_array = score_list

            algorithm = "Bubble Sort"

            break

        # Quick Sort
        elif choice == "3":

            quick_sort(
                score_list,
                0,
                len(score_list) - 1
            )

            sorted_array = score_list

            algorithm = "Quick Sort"

            break

        # Merge Sort
        elif choice == "4":

            sorted_array = merge_sort(score_list)

            algorithm = "Merge Sort"

            break

        else:

            print(
                "\nWrong Choice!"
                "\nPlease enter a number from 1 to 4."
            )

    print("\n==============================")
    print("THE LEADERBOARD")
    print("==============================")

    print("Algorithm:", algorithm)

    for score in sorted_array:
        print(score)