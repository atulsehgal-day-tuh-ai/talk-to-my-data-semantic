"""
STEP 4.3

Now that your graph can compute pairwise join paths, we will build a resolver that can compute the complete join path for the entire semantic plan:
- the measure table
- the time dimension table
- all group-by dimension tables

This is what will allow us to later auto-generate the exact SQL FROM and JOIN clauses.

Given a SemanticPlan like:

{
  "measure": {"table": "lineitem"},
  "time_dimension": {"table": "orders"},
  "group_by_dimensions": [
    {"table": "region"}
  ]
}


We want to compute one unified set of required joins:

lineitem
  → orders
  → customer
  → nation
  → region


This will become:

FROM lineitem l
JOIN orders o ON l.l_orderkey = o.o_orderkey
JOIN customer c ON o.o_custkey = c.c_custkey
JOIN nation n ON c.c_nationkey = n.n_nationkey
JOIN region r ON n.n_regionkey = r.r_regionkey

How we do it:
For each table in the semantic plan:

- compute path = find_path(measure_table, table_name)
- add all edges to a unified set
- deduplicate edges
- preserve the correct order (by graph order)
"""

from ast import If
from typing import List, Set, Optional
from src.semantic.join_graph import JoinGraph, JoinEdge
from src.semantic.semantic_plan import SemanticPlan


class JoinResolver:
    """
    Computes the full join path for a SemanticPlan.
    """

    def __init__(self, join_graph: JoinGraph):
        self.graph = join_graph


    def _preferred_roles_for_dimension(self, dim_name: str, dim_table: str) -> Set[str]:
        """
        Decide which relationship roles to prefer based on the dimension.

        This is the semantic intelligence layer that tells the system:
        - "region", "nation" → prefer customer geography
        - "customer" → customer hierarchy
        - "supplier" → supplier hierarchy
        """

        name = dim_name.lower()
        table = dim_table.lower()

        # Prefer customer hierarchy for geography dims
        if table in {"region", "nation"} or name in {"region", "nation"}:
            return {"customer_hierarchy"}

        # Customer dims → prefer customer_hierarchy
        if table == "customer":
            return {"customer_hierarchy"}

        # Supplier dims → prefer supplier_hierarchy
        if table == "supplier":
            return {"supplier_hierarchy"}

        # Default: no preference
        return set()


    def joins_for_plan(self, plan: SemanticPlan) -> List[JoinEdge]:
        """
        Given the semantic plan, compute all join edges required
        to connect the measure table with:
        - time dimension table
        - all group-by dimension tables

        This version is ROLE-AWARE:
        -----------------------------------------
        For ambiguous dimensions (like region, nation),
        we prefer certain semantic relationship roles,
        e.g., customer geography over supplier geography.

        Example:
            "revenue by region last year"
            - lineitem → supplier → nation → region (short path)
            - lineitem → orders → customer → nation → region (semantically correct)

        We use:
        1) Preferred roles (semantic priority)
        2) Path length (secondary criterion)
        """

        # ------------------------------------------------------------
        # Step 1 — Start at the measure table
        # All join paths begin from the fact table of the measure.
        # ------------------------------------------------------------
        measure_table = plan.measure.table

        # ------------------------------------------------------------
        # Step 2 — Identify all target tables
        # These come from:
        #   - time_dimension.table
        #   - each group-by dimension table
        #
        # But now we also compute preferred roles for each target.
        # ------------------------------------------------------------
        targets: List[tuple[str, Optional[Set[str]]]] = []

        # Time dimension first
        if plan.time_dimension:
            dim = plan.time_dimension
            preferred_roles = self._preferred_roles_for_dimension(dim.name, dim.table)
            targets.append((dim.table, preferred_roles))

        # Group-by dimensions
        for dim in plan.group_by_dimensions:
            preferred_roles = self._preferred_roles_for_dimension(dim.name, dim.table)
            targets.append((dim.table, preferred_roles))

        # ------------------------------------------------------------
        # Step 3 — For each target, compute the JOIN PATH
        # Using the role-aware find_path() we added earlier.
        # ------------------------------------------------------------
        all_edges: List[JoinEdge] = []

        for table, preferred_roles in targets:
            path = self.graph.find_path(
                start=measure_table,
                target=table,
                preferred_roles=preferred_roles,
            )

            if path is None:
                raise ValueError(
                    f"No join path found from measure table '{measure_table}' → '{table}'"
                )

            all_edges.extend(path)

        # ------------------------------------------------------------
        # Step 4 — Deduplicate edges while preserving order
        # Multiple group-by dimensions may require the same joins.
        # ------------------------------------------------------------
        unique_edges: List[JoinEdge] = []
        seen: Set[tuple] = set()

        for edge in all_edges:
            key = (edge.source, edge.target, edge.source_column, edge.target_column)
            if key not in seen:
                seen.add(key)
                unique_edges.append(edge)

        # ------------------------------------------------------------
        # Step 5 — Return final JoinEdge list
        # This is the unified join path for the entire query.
        # ------------------------------------------------------------
        return unique_edges
