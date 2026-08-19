# Programming Challenge: Algorithm Arena — The Lost Kingdom

### Difficulty: Hard

### Concepts Covered

* Selection Sort
* Bubble Sort
* Merge Sort
* Quick Sort
* Binary Search
* BFS
* DFS
* Lists
* Recursion
* Graphs
* Algorithm Selection
* Time Complexity

---

## 🎮 Game Story

You are building **Algorithm Arena**, a text-based adventure game.

The player enters a mysterious kingdom containing **cities, monsters, treasures, and quests**.

To complete the game, the player must:

1. Manage and sort game objects.
2. Search for treasures efficiently.
3. Find the shortest route between cities.
4. Explore the complete kingdom.
5. Defeat monsters and calculate a final score.

However, there is one restriction:

> **You are not allowed to use Python's `sort()`, `sorted()`, or any built-in graph-search function.**

You must implement the required algorithms yourself.

---

# 🗺️ Game World

The kingdom contains `N` locations connected by roads.

Example:

```text
            Castle
           /      \
      Forest      Village
      /    \          \
   Cave    Lake       Market
             \         /
              \       /
               Dungeon
```

The map is represented as a graph.

---

# 🎯 Game Requirements

Your program should provide the following game operations.

---

## Mission 1 — Build the Leaderboard

Each player has a score.

Example:

### Players

```text
Arjun   450
Riya    720
Kabir   310
Neha    890
Aman    560
```

The game must display players according to their scores in ascending order.

### Required Algorithms

The game should support **four sorting modes**:

1. Selection Sort
2. Bubble Sort
3. Merge Sort
4. Quick Sort

The user selects the sorting algorithm.

Example:

```text
Choose Sorting Algorithm:

1. Selection Sort
2. Bubble Sort
3. Merge Sort
4. Quick Sort

Choice: 3
```

Output:

```text
Leaderboard:

Kabir 310
Arjun 450
Aman 560
Riya 720
Neha 890
```

### Restriction

You must implement all four sorting algorithms manually.

---

# 🔎 Mission 2 — Treasure Scanner

Each treasure has a unique ID.

The treasure IDs are maintained in **sorted order**:

```text
105 118 129 145 167 189 205 221 250
```

The player enters a treasure ID.

Example:

```text
Enter Treasure ID: 189
```

Your program must determine whether the treasure exists.

### Required Algorithm

**Binary Search**

Output:

```text
Treasure Found!

Index: 5
```

If the treasure does not exist:

```text
Treasure Not Found!
```

### Restriction

Do not use:

* `in`
* `index()`
* Linear search

---

# 🧭 Mission 3 — Find the Fastest Route

The player wants to travel from one location to another.

Each road represents one movement.

Example graph:

```text
A ─── B ─── D
│     │
C ─── E ─── F
      │
      G
```

Input:

```text
Start: A

Destination: G
```

Your program must find the route requiring the **minimum number of roads**.

### Required Algorithm

**BFS**

Expected output:

```text
Shortest Route:

A -> C -> E -> G

Steps: 3
```

### Important

The program should print the actual path, not just the number of steps.

---

# 🏰 Mission 4 — Explore the Kingdom

Before the player can finish the game, they must determine which locations are reachable from the starting location.

Given:

```text
A-B
A-C
B-D
B-E
C-F
E-G
```

Starting location:

```text
A
```

Perform a complete exploration.

### Required Algorithm

**DFS**

The program should print the order in which locations were explored.

Example:

```text
DFS Exploration:

A
B
D
E
G
C
F
```

The exact order can depend on the adjacency-list ordering used by the implementation.

---

# ⚔️ Mission 5 — Monster Battle

Each monster has:

* Monster Name
* Health
* Attack
* Reward

Example:

```text
Goblin    100   20   50
Dragon    500   80   500
Orc       250   40   150
Troll     350   60   300
```

The player chooses a monster.

The battle score is calculated as:

```text
Battle Score = Reward + (Monster Health / 10) - Attack
```

For example:

```text
Goblin

= 50 + (100 / 10) - 20

= 40
```

The battle score is added to the player's total score.

---

# 🏆 Final Game Score

At the end:

```text
Final Score =

Leaderboard Score
+ Treasure Bonus
+ Battle Score
+ Exploration Bonus
```

The player receives:

| Final Score | Rank               |
| ----------- | ------------------ |
| `0–299`     | Novice Explorer    |
| `300–599`   | Skilled Adventurer |
| `600–999`   | Master Strategist  |
| `1000+`     | Algorithm Legend   |

---

# 📥 Sample Input

One possible input format:

```text
5

Arjun 450
Riya 720
Kabir 310
Neha 890
Aman 560

3

9

105 118 129 145 167 189 205 221 250

189

7

A B
A C
B D
B E
C F
E G
F G

A G

7

A B
A C
B D
B E
C F
E G
F G

A

4

Goblin 100 20 50
Dragon 500 80 500
Orc 250 40 150
Troll 350 60 300

Dragon
```

---

# 📤 Sample Output

```text
===== ALGORITHM ARENA =====

LEADERBOARD

Using Merge Sort:

Kabir 310
Arjun 450
Aman 560
Riya 720
Neha 890


TREASURE SCANNER

Searching for: 189

Treasure Found!

Index: 5


FASTEST ROUTE

From: A

To: G

Shortest Route:

A -> C -> F -> G

Steps: 3


KINGDOM EXPLORATION

Starting Location: A

DFS Order:

A -> B -> D -> E -> G -> C -> F


MONSTER BATTLE

Monster: Dragon

Battle Score: 470


===== GAME RESULT =====

Player Score: 890

Treasure Bonus: 100

Battle Score: 470

Exploration Bonus: 100

Final Score: 1560

Rank: ALGORITHM LEGEND
```

---

# 🔥 Mandatory Algorithm Rules

The game is considered complete only if all of these are implemented:

| Game Feature         | Required Algorithm |
| -------------------- | ------------------ |
| Basic leaderboard    | Selection Sort     |
| Fast leaderboard     | Bubble Sort        |
| Large leaderboard    | Merge Sort         |
| Advanced leaderboard | Quick Sort         |
| Treasure lookup      | Binary Search      |
| Shortest route       | BFS                |
| Kingdom exploration  | DFS                |

### Additional Restriction

The following are **not allowed**:

```python
sorted()
list.sort()
```

For searching:

```python
in
index()
```

For graph traversal, learners must implement the algorithm themselves.

---

# ⭐ Bonus Challenge

Add a **Game Performance Dashboard**:

```text
===== ALGORITHM PERFORMANCE =====

Selection Sort

Comparisons: 10

Swaps: 4


Bubble Sort

Comparisons: 8

Swaps: 4


Merge Sort

Comparisons: 7


Quick Sort

Comparisons: 6


Binary Search

Comparisons: 3


BFS

Nodes Visited: 5


DFS

Nodes Visited: 7
```

Then ask the player:

1. Which sorting algorithm performed best?
2. Which algorithm found the treasure?
3. Which algorithm found the shortest route?
4. Which algorithm explored the entire kingdom?
