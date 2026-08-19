from collections import deque
import time

def bfs_shortest_path(graph , start:str , end: str):
    start_time = time.time()

    visited = set()
    visited.add(start)
    parent : dict[str , str | None] = {start : None}
    q = deque()
    q.append(start)

    while q:
        current = q.popleft()

        if current == end:
            break

        for nei_node in graph[current]:
            if nei_node not in visited:
                visited.add(nei_node)
                parent[nei_node] = current
                q.append(nei_node)

    # Path reconstruction
    if end not in parent:
        print(f"No path is found from {start} to {end}")
        return

    path = []
    node = end
    while node != start:
        path.append(node)
        next_node = parent[node]
        assert next_node is not None
        node = next_node
    path.append(start)
    path = path[::-1]

    print(f"shortest Route:\n{(' -> '.join(path))}\nSteps: {len(path) -1}")
    end_time = time.time()
    print(f"Time Taken to find the shortest path using classis BFS: {end_time - start_time}s")  


def bidirectional_bfs_shortest_path( graph , start: str , end: str):

    start_time = time.time()
    if start == end:
        print(f"shortest Route:\n{start}\nSteps: 0")
        return

    if start not in graph or end not in graph:
        print(f"No path is found from {start} to {end}")
        return

    # Given graph is only one way directed graph, so the bfs from end node needs a reversed graph
    reverse_graph : dict[str , list[str]] = {node : [] for node in graph}
    for node in graph:
        for nei_node in graph[node]:
            reverse_graph[nei_node].append(node)

    parent_start : dict[str , str | None] = {start : None}
    parent_end : dict[str , str | None] = {end : None}
    dist_start = {start : 0}
    dist_end = {end : 0}

    q_start = deque([start])
    q_end = deque([end])

    meeting_node = None

    while q_start and q_end and meeting_node is None:

        # Iterate from the start side by one full layer
        for _ in range(len(q_start)):
            current = q_start.popleft()
            for nei_node in graph[current]:
                if nei_node not in parent_start:
                    parent_start[nei_node] = current
                    dist_start[nei_node] = dist_start[current] + 1
                    q_start.append(nei_node)

        # Iterate the end side by one full layer (using the reversed graph)
        for _ in range(len(q_end)):
            current = q_end.popleft()
            for nei_node in reverse_graph[current]:
                if nei_node not in parent_end:
                    parent_end[nei_node] = current
                    dist_end[nei_node] = dist_end[current] + 1
                    q_end.append(nei_node)

        # Find common node in both parent dictionaries
        common = [n for n in parent_start if n in parent_end]
        if common:
            meeting_node = min(common , key = lambda n: dist_start[n] + dist_end[n])

    if meeting_node is None:
        print(f"No path is found from {start} to {end}")
        return

    # Path reconstruction: start -> meeting_node
    path_start = []
    node = meeting_node
    while node is not None:
        path_start.append(node)
        node = parent_start[node]
    path_start = path_start[::-1]

    # Path reconstruction: meeting_node -> end
    path_end = []
    node = parent_end[meeting_node]
    while node is not None:
        path_end.append(node)
        node = parent_end[node]

    path = path_start + path_end

    print(f"shortest Route:\n{(' -> '.join(path))}\nSteps: {len(path) -1}")
    end_time = time.time()
    print(f"Time Taken to find the shortest path using classis BFS: {end_time - start_time}s")  
