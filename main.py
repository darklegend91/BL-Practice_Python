from missions.mission1 import console_mission1
from menu import show_banner , show_mission_menu , get_mission_choice
from missions.mission2 import findTreasure
from missions.mission3 import bfs_shortest_path , bidirectional_bfs_shortest_path
from missions.mission4 import iterative_dfs
from missions.mission5 import battle
from missions.mission6 import algorithm_performance
from missions.mission7 import game_result

def main(game_state):

   list_ids = [105, 118, 129, 145, 167, 189, 205, 221, 250]

   graph = {
    'A': ['B', 'C'],
    'B': ['D', 'E'],
    'C': ['E' ,'F'],
    'D': [],
    'E': ['F' , 'G'],
    'F': [],
    'G': []
}

   monsters = {
    'Goblin': {'health': 100, 'attack': 20, 'reward': 50},
    'Dragon': {'health': 500, 'attack': 80, 'reward': 500},
    'Orc':    {'health': 250, 'attack': 40, 'reward': 150},
    'Troll':  {'health': 350, 'attack': 60, 'reward': 300}
}

   sample_scores = [450, 720, 310, 890, 560]

   show_mission_menu()
   mission_choice = get_mission_choice()

   if mission_choice == 0:
      print("\nNice Play , Bye Bye!")
      return

   if mission_choice == 1:
      game_state['leaderboard_score'] = console_mission1(sample_scores)

   if mission_choice == 2:
      game_state['treasure_bonus'] = findTreasure(list_ids)

   if mission_choice == 3:
      print("""
Enter 1 for Classic BFS
Enter 2 for Bidirectional BFS
""")
      bfs_choice = int(input("Enter Choice: "))
      if bfs_choice == 1:
         bfs_shortest_path(graph , 'A' , 'G')
      elif bfs_choice ==2:
         bidirectional_bfs_shortest_path(graph , 'A' , 'G')
      else:
         print("Wrong Choice !! Choose Again")

   if mission_choice == 4:
      game_state['exploration_bonus'] = iterative_dfs(graph , 'A')

   if mission_choice == 5:
      game_state['battle_score'] = battle(monsters) or 0

   if mission_choice == 6:
      algorithm_performance(sample_scores , list_ids , 189 , graph , 'A')

   if mission_choice == 7:
      game_result(game_state)

   main(game_state)

if __name__ == "__main__":
   show_banner()

   game_state = {
      'leaderboard_score': 0,
      'treasure_bonus': 0,
      'battle_score': 0,
      'exploration_bonus': 0
   }

   main(game_state)
