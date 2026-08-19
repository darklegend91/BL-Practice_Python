from pyfiglet import Figlet
def show_banner():
    figlet = Figlet()

    print("=" * 70)
    print(figlet.renderText("ALGORITHM ARENA"))
    print("                 THE LOST KINGDOM")
    print("=" * 70)

    print("""
        Welcome, Adventurer!  

    A mysterious kingdom awaits you.

    Complete missions.
    Discover treasures.
    Explore cities.
    Defeat monsters.
    Master algorithms.

    To begin the journey enter mission choice...
    """)


def show_mission_menu():
    print("\n" + "=" * 55)
    print("                 MISSION BOARD")
    print("=" * 55)

    print("""
    [1] Build the Leaderboard
        Algorithms: Selection / Bubble / Merge / Quick Sort

    [2] Treasure Scanner
        Algorithm: Binary Search

    [3] Find the Fastest Route
        Algorithm: BFS

    [4] Explore the Kingdom
        Algorithm: DFS

    [5] Monster Battle
        Calculate your battle score

    [6] Algorithm Performance
        View algorithm statistics

    [7] View Game Result
        View score and rank

    [0] Exit the Kingdom
    """)

    print("=" * 55)


def get_mission_choice():
    while True:
        choice = input("Choose your mission: ").strip()

        if choice == "1":
            return 1
        elif choice == "2":
            return 2
        elif choice == "3":
            return 3
        elif choice == "4":
            return 4
        elif choice == "5":
            return 5
        elif choice == "6":
            return 6
        elif choice == "7":
            return 7
        elif choice == "0":
            return 0
        else:
            print("\nInvalid mission.")
            print("Please choose a number from 0 to 7.\n")
