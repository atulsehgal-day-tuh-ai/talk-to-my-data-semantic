"""
THE IMPORTANT INSIGHT:
The Semantic Plan tells WHAT to compute.
The Join Resolver tells HOW to compute it.

Your JSON plan tells us:
-What measure to compute
-What time dimension to use
-What filters to apply
What dimensions to group by

But it does NOT tell the system HOW to join the tables required to actually compute those fields in SQL.

The semantic plan has meaning, but no SQL topology.

This is the semantic relationship graph our model needs to understand.It shows ALL joins relevant to:
-measures
-time dimensions
-product attributes
-customer attributes
-geography (nation/region)

                      ┌──────────────┐
                      │    region    │
                      │  (r_region)  │
                      └──────┬───────┘
                             │
                             │ r_regionkey = n_regionkey
                             ▼
                      ┌──────────────┐
                      │    nation    │
                      │ (n_nation)   │
                      └──────┬───────┘
                             │
                             │ n_nationkey = c_nationkey
                             ▼
                      ┌──────────────┐
                      │   customer   │
                      │  (c_custkey) │
                      └──────┬───────┘
                             │
                             │ c_custkey = o_custkey
                             ▼
                      ┌──────────────┐
                      │    orders    │
                      │ (o_orderkey) │
                      └──────┬───────┘
                             │
                             │ o_orderkey = l_orderkey
                             ▼
                      ┌──────────────┐
                      │   lineitem   │
                      │ (l_orderkey) │
                      └──────┬───────┬─────────────┐
                             │       │             │
                             │       │             │
                 l_partkey = │       │ = l_suppkey │
                             ▼       ▼             ▼
                      ┌──────────┐ ┌──────────┐ ┌────────────┐
                      │   part   │ │ partsupp │ │  supplier   │
                      │ p_partkey│ │ ps_part  │ │ s_suppkey   │
                      └──────────┘ └──────────┘ └────────────┘

This join graph is essential for the Semantic Resolver to generate correct SQL queries
from natural language questions.


STEP 4.1 — Build the Join Graph:
Goal: Create a Python object that represents all joins from your YAML so your system can later compute:
- which tables are needed
- what order to join them
- join keys (source/target columns)
- minimal join path
- direction of joins

This will allow SQL generation to become fully automatic.
"""


# src/semantic/join_graph.py

from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import deque


# This is the most basic building block of join relationships
@dataclass
class JoinEdge:
    source: str
    target: str
    source_column: str
    target_column: str


class JoinGraph:

    """
    A join graph is a graph where 
    nodes = tables
    and edges = join relationships

    This class will store all join edges in a structure like:
    graph = {
        "lineitem": [JoinEdge(...), JoinEdge(...)],
        "orders": [JoinEdge(...)]
    }
    """


    def __init__(self):
        # adjacency list: graph[table] = [JoinEdge, JoinEdge, ...]
        self.graph: Dict[str, List[JoinEdge]] = {}

    def add_edge(self, edge: JoinEdge):

        """
        This is where we teach the graph how to:
        - store joins
        - make them bidirectional
        - ensure both tables appear in the graph
        """

        # ensure both sides exist
        if edge.source not in self.graph:
            self.graph[edge.source] = []
        if edge.target not in self.graph:
            self.graph[edge.target] = []

        # Add source -> target
        self.graph[edge.source].append(edge)

        # Add target -> source (reverse join)
        # This means joins become fully bidirectional
        # We want it to behave like a bidirectional graph, because joins can go BOTH ways:
        # fact → dimension
        # dimension → fact
        # dimension → another dimension

        reverse_edge = JoinEdge(
            source=edge.target,
            target=edge.source,
            source_column=edge.target_column,
            target_column=edge.source_column
        )
        self.graph[edge.target].append(reverse_edge)



    @classmethod
    def from_model(cls, model) -> "JoinGraph":

        """
        This is the part where our join graph gets populated from the YAML semantic model.
        1. Reads all relationships from our semantic model
        2. Converts them into JoinEdge objects
        3. Calls add_edge() for each one
        4. Returns a fully built JoinGraph
        """

        graph = cls()  # Creates a new empty JoinGraph

        # The semantic model stores relationships as dataclasses
        # Loop through all relationships in the semantic model
        # Create a JoinEdge out of it
        for rel in model.relationships:
            edge = JoinEdge(
                source=rel.from_table,
                target=rel.to_table,
                source_column=rel.from_column,
                target_column=rel.to_column
            )
            graph.add_edge(edge)

        return graph


    def print_graph(self):
        """
        Debug Printer
        This method prints each table and its outgoing join edges.
        """
        for table, edges in self.graph.items():
            print(f"{table}:")
            for e in edges:
                print(f"   {e.source}.{e.source_column}  →  {e.target}.{e.target_column}")
            print()


    def find_path(self, start: str, target: str) -> Optional[List[JoinEdge]]:
        """
        Find the shortest join path (in number of hops) between two tables
        using BFS. Returns a list of JoinEdge objects from start → target,
        or None if no path exists.

        start = source table name (e.g., "lineitem")
        target = destination table name (e.g., "region")
        returns: a list of JoinEdge in order from start → target, or None if no path exists.

        What this does:
        - Uses a queue (deque) to explore neighbors layer by layer (BFS).
        - Tracks path as a list of JoinEdge objects from start to current node.
        - Stops when it reaches target, returns the path.
        - Guarantees shortest path in number of joins.
        """
        if start == target:
            return []

        if start not in self.graph or target not in self.graph:
            return None

        # queue entries: (current_table, path_so_far)
        queue = deque()
        queue.append((start, []))

        visited = set([start])

        while queue:
            current_table, path = queue.popleft()

            for edge in self.graph.get(current_table, []):
                next_table = edge.target

                if next_table in visited:
                    continue

                new_path = path + [edge]

                if next_table == target:
                    return new_path

                visited.add(next_table)
                queue.append((next_table, new_path))

        # no path found
        return None


    def show_path(self, start: str, target: str):
        """
        Convenience utility: pretty-print the join path from start → target
        using the find_path() BFS resolver.
        """
        path = self.find_path(start, target)

        print(f"\nJoin path from '{start}' to '{target}':")

        if path is None:
            print("   (no path found)")
            return

        if len(path) == 0:
            print("   (start and target are the same table)")
            return

        for edge in path:
            print(f"   {edge.source}.{edge.source_column}  →  {edge.target}.{edge.target_column}")


