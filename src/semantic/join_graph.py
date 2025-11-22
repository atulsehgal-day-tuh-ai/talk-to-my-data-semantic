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


# ⭐ OVERVIEW: Which functions are REQUIRED for SQL generation? ⭐

# Here is the complete list:

# 🟢 Functions REQUIRED for SQL generation:

# 1. find_path()
# ✔ Critical
# ✔ Used by JoinResolver
# ✔ Applies semantic roles
# ✔ Affects SQL correctness

# 2. joins_for_plan()
# ✔ Critical
# ✔ Builds final join chain
# ✔ Consumes find_path() output
# ✔ Direct input to SQL builder

# 3. SQLGenerator.generate() (when you build it)
# ✔ Critical
# ✔ Takes join edges + measure + dims → final query


# 🔵 Functions NOT required for SQL generation:
# find_path_raw()
# Only for debugging

# show_path_raw()
# Only pretty print

# show_path_semantic()
# Only pretty print

# Any other debugging helpers
# Not used in SQL

# 🎯 TL;DR (Short Answer)

# YES — find_path() is needed for SQL.
# NO — show_*() functions do not matter for SQL.
# YES — you must keep joins_for_plan() correct.
# NO — you don’t need to change anything else in JoinGraph for SQL.
# YES — your next step is to implement the SQL generator layer.


from dataclasses import dataclass
import queue
from typing import List, Dict, Optional, Set
from collections import deque


# This is the most basic building block of join relationships
@dataclass
class JoinEdge:
    source: str
    target: str
    source_column: str
    target_column: str
    role: Optional[str] = None
    description: Optional[str] = None


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

        # reverse_edge = JoinEdge(
        #     source=edge.target,
        #     target=edge.source,
        #     source_column=edge.target_column,
        #     target_column=edge.source_column,
        #     role=edge.role,
        #     description=edge.description
        # )
        # self.graph[edge.target].append(reverse_edge)

        # Ensure target table exists in graph but DO NOT add reverse join
        if edge.target not in self.graph:
            self.graph[edge.target] = []




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
                target_column=rel.to_column,
                role=rel.role,
                description=rel.description,
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

    #################################################################################
    #### find_path_raw() = PHYSICAL shortest path #####

    # Used for:
    # - Debugging your graph
    # - Verifying relationships from YAML
    # - Seeing actual forward-only edges
    # - Confirming the physical schema layout
    # - Understanding the star/snowflake model

    # Behavior:
    # - Pure BFS
    # - No semantic scoring
    # - Not used for SQL generation

    # Example result:
    # lineitem → supplier → nation → region

    #################################################################################
    ##### find_path() = SEMANTICALLY ranked path (CORE ENGINE) #####

    # Used for:
    # - Semantic decisions
    # - Choosing the correct business meaning
    # - Avoiding “supplier geography” when user asks “customer region”
    # - Selecting longest-but-correct path (customer_hierarchy)
    # - SQL generation (JOIN ON paths)
    # - Future metric-by-metric reasoning
    # - Future LLM-driven intent reasoning

    # Behavior:
    # - Explores all possible join paths
    # - Scores them using:
    # 1. Preferred roles (semantic priority)
    # 2. Hop count (tie-breaker)
    # - Picks the best semantic path, not the shortest

    # Example result:
    # lineitem → orders → customer → nation → region   ✔ customer hierarchy


    def find_path(
        self,
        start: str,
        target: str,
        preferred_roles: Optional[Set[str]] = None,
    ) -> Optional[List[JoinEdge]]:
        """
        Role-aware join path finder.

        What this method does:
        ------------------------------------
        We want to find a join path between two tables (start → target).
        But not all join paths are equally meaningful semantically.

        Example:
            lineitem → supplier → nation → region      (shorter, but supplier region)
            lineitem → orders → customer → nation → region  (longer, but customer region)

        Business meaning prefers customer geography, not supplier geography.

        Therefore, we use TWO ranking criteria:

        1. PRIMARY RANK: number of edges whose role is in `preferred_roles`
           (e.g., {"customer_hierarchy"}). More matches = better.

        2. SECONDARY RANK: number of hops (path length).
           Among paths with the same role score, choose the shortest one.

        NOTE:
        - If `preferred_roles` is empty or None, this behaves like normal BFS shortest-path.
        - The method explores ALL possible BFS paths (because we must compare role scores).
        """

        # trivial case: same table
        if start == target:
            return []

        # invalid input check
        if start not in self.graph or target not in self.graph:
            return None

        preferred_roles = preferred_roles or set()

        # These track the best path found so far
        best_path: Optional[List[JoinEdge]] = None
        best_pref_count = -1   # how many edges match preferred roles
        best_hops = None       # path length

        # BFS queue stores (current_table, path_so_far)
        queue = deque([(start, [])])

        while queue:
            current_table, path = queue.popleft()

            for edge in self.graph.get(current_table, []):
                next_table = edge.target
                new_path = path + [edge]

                # === Case 1: we reached the target ===
                if next_table == target:
                    path_len = len(new_path)
                    pref_count = sum(
                        1 for e in new_path
                        if e.role is not None and e.role in preferred_roles
                    )

                    # FIRST priority: more preferred-role edges
                    if (
                        best_path is None
                        or pref_count > best_pref_count
                        or (pref_count == best_pref_count and path_len < best_hops)
                    ):
                        best_path = new_path
                        best_pref_count = pref_count
                        best_hops = path_len

                # === Case 2: continue BFS ===
                # Allow exploring all DISTINCT paths but avoid loops
                current_path_tables = [start] + [e.target for e in path]

                if next_table not in current_path_tables:
                    queue.append((next_table, new_path))


        # if we found a preferred-best path, return it
        return best_path
    
        # --------------------------------------------------------------------
    # RAW BFS shortest path (NO semantic roles)
    # --------------------------------------------------------------------
    def find_path_raw(self, start: str, target: str):
        """
        Pure raw BFS shortest path.
        No semantic scoring.
        No role awareness.
        """
        if start == target:
            return []

        if start not in self.graph or target not in self.graph:
            return None

        queue = deque([(start, [])])
        visited = set([start])

        while queue:
            table, path = queue.popleft()

            for edge in self.graph.get(table, []):
                next_table = edge.target

                if next_table in visited:
                    continue

                new_path = path + [edge]

                if next_table == target:
                    return new_path

                visited.add(next_table)
                queue.append((next_table, new_path))

        return None



    # Show Path: Raw physical path (shortest path)
    def show_path_raw(self, start: str, target: str):
        """
        Show the shortest physical join path (no semantics).
        This is the raw graph BFS.
        """
        # path = self.find_path(start, target, preferred_roles=None)
        path = self.find_path_raw(start, target)

        print(f"\nRAW shortest path from '{start}' to '{target}':")

        if path is None:
            print("   (no path found)")
            return

        if len(path) == 0:
            print("   (start and target are the same table)")
            return

        for edge in path:
            print(f"   {edge.source}.{edge.source_column} → {edge.target}.{edge.target_column} | role: {edge.role}")


    # Show Path: Semantic path (role-aware)
    def show_path_semantic(self, start: str, target: str, preferred_roles: Optional[Set[str]] = None):
        """
        Show the semantic join path (role-aware).
        This is what the SQL generator will actually use.
        """
        path = self.find_path(start, target, preferred_roles=preferred_roles)

        print(f"\nSEMANTIC path from '{start}' to '{target}' (roles={preferred_roles}):")

        if path is None:
            print("   (no path found)")
            return

        if len(path) == 0:
            print("   (start and target are the same table)")
            return

        for edge in path:
            print(f"   {edge.source}.{edge.source_column} → {edge.target}.{edge.target_column} | role: {edge.role}")

