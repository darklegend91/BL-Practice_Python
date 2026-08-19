from collections import deque

def _selection_sort(scores : list[int]):
    a = scores[:]
    comparisons = 0
    swaps = 0
    n = len(a)

    for i in range(n):
        mini = i
        for j in range(i + 1, n):
            comparisons += 1
            if a[j] < a[mini]:
                mini = j
        if mini != i:
            a[i], a[mini] = a[mini], a[i]
            swaps += 1

    return comparisons, swaps


def _bubble_sort(scores : list[int]):
    a = scores[:]
    comparisons = 0
    swaps = 0
    n = len(a)

    for i in range(n - 1):
        for j in range(0, n - i - 1):
            comparisons += 1
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swaps += 1

    return comparisons, swaps


def _merge_sort(scores : list[int]):
    comparisons = 0

    def merge(left, right):
        nonlocal comparisons
        merged = []
        i = 0
        j = 0
        while i < len(left) and j < len(right):
            comparisons += 1
            if left[i] < right[j]:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
        merged.extend(left[i:])
        merged.extend(right[j:])
        return merged

    def sort(a):
        if len(a) <= 1:
            return a
        mid = len(a) // 2
        left = sort(a[:mid])
        right = sort(a[mid:])
        return merge(left, right)

    sort(scores[:])
    return comparisons


def _quick_sort(scores : list[int]):
    a = scores[:]
    comparisons = 0

    def partition(low, high):
        nonlocal comparisons
        pivot = a[low]
        i = low + 1
        j = high
        while True:
            while i <= j:
                comparisons += 1
                if a[i] <= pivot:
                    i += 1
                else:
                    break
            while i <= j:
                comparisons += 1
                if a[j] >= pivot:
                    j -= 1
                else:
                    break
            if i <= j:
                a[i], a[j] = a[j], a[i]
            else:
                break
        a[low], a[j] = a[j], a[low]
        return j

    def sort(low, high):
        if low < high:
            p = partition(low, high)
            sort(low, p - 1)
            sort(p + 1, high)

    sort(0, len(a) - 1)
    return comparisons


def _binary_search(list_ids : list[int], target : int):
    comparisons = 0
    left = 0
    right = len(list_ids) - 1

    while left <= right:
        mid = left + (right - left) // 2
        comparisons += 1
        if list_ids[mid] == target:
            return comparisons
        elif list_ids[mid] > target:
            right = mid - 1
        else:
            left = mid + 1

    return comparisons


def _bfs_nodes_visited(graph, start : str):
    visited = set()
    visited.add(start)
    q = deque([start])
    count = 0

    while q:
        current = q.popleft()
        count += 1
        for nei_node in graph[current]:
            if nei_node not in visited:
                visited.add(nei_node)
                q.append(nei_node)

    return count


def _dfs_nodes_visited(graph, start : str):
    visited = set()
    stack = [start]
    count = 0

    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        count += 1
        for nei_node in reversed(graph[current]):
            if nei_node not in visited:
                stack.append(nei_node)

    return count


def algorithm_performance(scores, list_ids, target, graph, start):

    sel_c, sel_s = _selection_sort(scores)
    bub_c, bub_s = _bubble_sort(scores)
    mer_c = _merge_sort(scores)
    qui_c = _quick_sort(scores)
    bin_c = _binary_search(list_ids, target)
    bfs_n = _bfs_nodes_visited(graph, start)
    dfs_n = _dfs_nodes_visited(graph, start)

    print("\n===== ALGORITHM PERFORMANCE =====")
    print(f"\nSelection Sort\nComparisons: {sel_c}\nSwaps: {sel_s}")
    print(f"\nBubble Sort\nComparisons: {bub_c}\nSwaps: {bub_s}")
    print(f"\nMerge Sort\nComparisons: {mer_c}")
    print(f"\nQuick Sort\nComparisons: {qui_c}")
    print(f"\nBinary Search\nComparisons: {bin_c}")
    print(f"\nBFS\nNodes Visited: {bfs_n}")
    print(f"\nDFS\nNodes Visited: {dfs_n}")

    # Work out the best sorter (fewest comparisons + swaps) for the quiz answer
    sort_work = {
        "Selection Sort": sel_c + sel_s,
        "Bubble Sort": bub_c + bub_s,
        "Merge Sort": mer_c,
        "Quick Sort": qui_c,
    }
    best_sort = min(sort_work, key=lambda name: sort_work[name])

    quiz(best_sort)


def quiz(best_sort : str):

    print("\n===== PERFORMANCE QUIZ =====")

    questions = [
        ("Which sorting algorithm performed best?", best_sort),
        ("Which algorithm found the treasure?", "Binary Search"),
        ("Which algorithm found the shortest route?", "BFS"),
        ("Which algorithm explored the entire kingdom?", "DFS"),
    ]

    for question, answer in questions:
        guess = input(f"\n{question}\nYour answer: ").strip()
        if guess.lower() == answer.lower():
            print("Correct!")
        else:
            print(f"The answer is: {answer}")
