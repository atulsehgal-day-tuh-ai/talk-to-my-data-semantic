"""
Step 5 is where this thing finally turns into real SQL

You already have:
- SemanticPlan → what to compute
- JoinResolver.joins_for_plan(plan) → which tables & joins you need

Now we’ll build:
- SQLGenerator → turns (plan + joins) into a full Snowflake SQL string.

"""

from typing import List
from src.semantic.semantic_plan import SemanticPlan
from src.semantic.join_graph import JoinEdge


class SQLGenerator:
    """
    Generate Snowflake SQL from a SemanticPlan and a list of JoinEdge objects.
    Supports semantic-aware time grains (day, month, quarter, year).
    """

    def __init__(self):
        pass

    def _dim_ref(self, table: str, column: str) -> str:
        """Build table.column reference (no aliasing yet)."""
        return f"{table}.{column}"

    def _apply_time_filter(self, plan: SemanticPlan) -> str:
        """
        Take the semantic time_filter from the plan and replace the semantic
        time dimension name (e.g., 'order_date') with its physical
        table.column reference.
        """
        if not plan.time_filter:
            return ""

        if not plan.time_dimension:
            return plan.time_filter

        semantic_name = plan.time_dimension.name
        physical_ref = self._dim_ref(
            plan.time_dimension.table,
            plan.time_dimension.column,
        )

        return plan.time_filter.replace(semantic_name, physical_ref)

    # -------------------------------------------------------------------------
    #   MAIN METHOD: sql_from_plan (UPDATED WITH TIME_GRAIN FIX)
    # -------------------------------------------------------------------------
    def sql_from_plan(self, plan: SemanticPlan, joins: List[JoinEdge]) -> str:
        """
        Build a full Snowflake SQL query string for the given semantic plan,
        fully respecting time grains (day, month, quarter, year).
        """

        # ======================
        # 1. SELECT CLAUSE
        # ======================
        select_exprs = []

        # --- Measure Expression ---
        measure_expr = f"{plan.measure.expression} AS {plan.measure.name}"
        select_exprs.append(measure_expr)

        # --- Time Grain Expression (if requested) ---
        time_col = None
        grain_expr = None

        if plan.time_dimension:
            time_col = self._dim_ref(
                plan.time_dimension.table,
                plan.time_dimension.column
            )

            if plan.time_grain:
                # Example: DATE_TRUNC('month', orders.o_orderdate)
                grain_expr = (
                    f"DATE_TRUNC('{plan.time_grain}', {time_col}) "
                    f"AS {plan.time_grain}_date"
                )
                select_exprs.append(grain_expr)

            else:
                # No grain → output raw date
                select_exprs.append(f"{time_col} AS {plan.time_dimension.name}")

        # --- Group-by Dimensions ---
        # (These remain unchanged)
        for dim in plan.group_by_dimensions:
            col_ref = self._dim_ref(dim.table, dim.column)
            select_exprs.append(f"{col_ref} AS {dim.name}")

        select_clause = "SELECT\n  " + ",\n  ".join(select_exprs)

        # ======================
        # 2. FROM + JOINS
        # ======================
        base_table = plan.measure.table
        from_clause = f"FROM {base_table}"
        joined_tables = {base_table}

        join_clauses = []
        for edge in joins:
            if edge.source in joined_tables and edge.target not in joined_tables:
                join_clause = (
                    f"JOIN {edge.target} "
                    f"ON {self._dim_ref(edge.source, edge.source_column)} "
                    f"= {self._dim_ref(edge.target, edge.target_column)}"
                )
                joined_tables.add(edge.target)
                join_clauses.append(join_clause)

            elif edge.target in joined_tables and edge.source not in joined_tables:
                join_clause = (
                    f"JOIN {edge.source} "
                    f"ON {self._dim_ref(edge.source, edge.source_column)} "
                    f"= {self._dim_ref(edge.target, edge.target_column)}"
                )
                joined_tables.add(edge.source)
                join_clauses.append(join_clause)

        join_section = ""
        if join_clauses:
            join_section = "\n" + "\n".join(join_clauses)

        # ======================
        # 3. WHERE CLAUSE
        # ======================
        where_parts = []

        time_pred = self._apply_time_filter(plan)
        if time_pred:
            where_parts.append(time_pred)

        where_clause = ""
        if where_parts:
            where_clause = "\nWHERE " + " AND ".join(where_parts)

        # ======================
        # 4. GROUP BY CLAUSE
        # ======================
        # ---- REMOVE RAW TIME DIM GROUP-BY WHEN TIME GRAIN EXISTS ----
        if plan.time_grain and plan.time_dimension:
            plan.group_by_dimensions = [
                d for d in plan.group_by_dimensions
                if d.name != plan.time_dimension.name
            ]
            
        group_by_exprs = []

        # --- Time grain grouping FIXED ---
        if grain_expr:
            # Use only DATE_TRUNC — do NOT include raw date
            group_by_exprs.append(grain_expr.split(" AS ")[0])

        elif time_col:
            # No grain → group by raw date
            group_by_exprs.append(time_col)

        # --- Dimension grouping ---
        for dim in plan.group_by_dimensions:
            group_by_exprs.append(self._dim_ref(dim.table, dim.column))

        group_by_clause = ""
        if group_by_exprs:
            group_by_clause = "\nGROUP BY " + ", ".join(group_by_exprs)

        # ======================
        # 5. Final SQL
        # ======================
        sql = (
            select_clause
            + "\n"
            + from_clause
            + join_section
            + where_clause
            + group_by_clause
        )

        return sql




