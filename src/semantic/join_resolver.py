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


    def _extract_tables_from_measure(self, expression: str) -> Set[str]:
        """
        Parse measure SQL expression and extract all tables referenced by column names.

        Example: SUM(l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity)
        → returns {"lineitem", "partsupp"}

        Uses the semantic model's table->columns map.
        """
        referenced = set()

        # tokens like l_extendedprice, ps_supplycost, o_orderdate
        tokens = self.graph.column_regex.findall(expression)

        for token in tokens:
            # check each table to see who owns the column
            for tbl, columns in self.graph.table_columns.items():
                if token in columns:
                    referenced.add(tbl)

        return referenced


    def joins_for_plan(self, plan: SemanticPlan) -> List[JoinEdge]:
        """
        Given the semantic plan, compute all join edges required
        to connect the measure table with:
        - time dimension table
        - all group-by dimension tables

        Compute all JOIN edges needed for:
        - measure table
        - any tables referenced by the measure expression   (NEW)
        - time dimension
        - group-by dimensions

        This version is ROLE-AWARE:
        -----------------------------------------
        For ambiguous dimensions (like region, nation),
        we prefer certain semantic relationship roles,
        e.g., customer geography over supplier geography.

        We use:
        1) Preferred roles (semantic priority)
        2) Path length (secondary criterion)
        """

        # ------------------------------------------------------------
        # Step 1 — Start at the measure table
        # ------------------------------------------------------------
        measure_table = plan.measure.table

        # ------------------------------------------------------------
        # Step 2 — Identify all target tables
        # ------------------------------------------------------------
        targets: List[tuple[str, Optional[Set[str]]]] = []

        # 2A — Time dimension target
        if plan.time_dimension:
            dim = plan.time_dimension
            preferred_roles = self._preferred_roles_for_dimension(dim.name, dim.table)
            targets.append((dim.table, preferred_roles))

        # 2B — Group-by dimension targets
        for dim in plan.group_by_dimensions:
            preferred_roles = self._preferred_roles_for_dimension(dim.name, dim.table)
            targets.append((dim.table, preferred_roles))

        # ------------------------------------------------------------
        # 2C — NEW: Add tables referenced inside the measure expression
        # ------------------------------------------------------------
        referenced_tables = self._extract_tables_from_measure(plan.measure.expression)

        for tbl in referenced_tables:
            if tbl != measure_table:
                # For measure-derived tables we do NOT enforce preferred roles
                targets.append((tbl, None))

        # ------------------------------------------------------------
        # Step 3 — Resolve join paths for every target
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

            # Add the primary path edges
            all_edges.extend(path)

            # ---------- 🔴 IMPORTANT NEW GUARD ----------
            # If start == target (e.g. measure table and time dimension
            # both on 'orders'), find_path() returns [].
            # In that case, there is no join to add and no "parallel edge"
            # logic to run.
            if not path:
                continue

            last_edge = path[-1]

            # --- NEW: also include parallel edges between the same two tables
            #          (needed for composite join conditions like
            #           lineitem.l_partkey & lineitem.l_suppkey → partsupp.*)
            for e in self.graph.graph.get(last_edge.source, []):
                if e.target == last_edge.target and e not in path:
                    all_edges.append(e)

            for e in self.graph.graph.get(last_edge.target, []):
                if e.source == last_edge.source and e not in path:
                    all_edges.append(e)

        # ------------------------------------------------------------
        # Step 4 — Deduplicate edges (preserve original order)
        # ------------------------------------------------------------
        unique_edges: List[JoinEdge] = []
        seen: Set[tuple] = set()

        for edge in all_edges:
            key = (edge.source, edge.target, edge.source_column, edge.target_column)
            if key not in seen:
                seen.add(key)
                unique_edges.append(edge)

        return unique_edges


