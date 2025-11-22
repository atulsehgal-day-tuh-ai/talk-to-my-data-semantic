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
    """

    def __init__(self):
        # You can add config here later (e.g., database/schema)
        pass

    def _dim_ref(self, table: str, column: str) -> str:
        """
        Helper to build a fully-qualified column reference.
        For now we don't alias tables to keep SQL simple.
        """
        return f"{table}.{column}"

    def _apply_time_filter(self, plan: SemanticPlan) -> str:
        """
        Take the semantic time_filter from the plan (which may use the
        time_dimension's name like 'order_date') and convert it into a
        valid SQL predicate using the real table+column.
        """
        if not plan.time_filter:
            return ""

        if not plan.time_dimension:
            # Nothing to substitute, just return as is
            return plan.time_filter

        # Example:
        # time_dimension.name = "order_date"
        # table = "orders", column = "o_orderdate"
        # time_filter = "order_date >= DATEADD(month, -3, CURRENT_DATE)"
        semantic_name = plan.time_dimension.name
        physical_ref = self._dim_ref(
            plan.time_dimension.table,
            plan.time_dimension.column,
        )

        predicate = plan.time_filter.replace(semantic_name, physical_ref)
        return predicate

    def sql_from_plan(self, plan: SemanticPlan, joins: List[JoinEdge]) -> str:
        """
        Build a full Snowflake SQL query string for the given semantic plan
        and resolved join edges.
        """

        # -------- SELECT clause --------
        select_exprs = []

        # Measure
        # e.g., "SUM(l_extendedprice * (1 - l_discount)) AS revenue"
        measure_expr = f"{plan.measure.expression} AS {plan.measure.name}"
        select_exprs.append(measure_expr)

        # Group-by dimensions
        for dim in plan.group_by_dimensions:
            col_ref = self._dim_ref(dim.table, dim.column)
            select_exprs.append(f"{col_ref} AS {dim.name}")

        select_clause = "SELECT\n  " + ",\n  ".join(select_exprs)

        # -------- FROM + JOIN clause --------

        # Anchor table is the measure's table
        base_table = plan.measure.table
        from_clause = f"FROM {base_table}"

        # We are not aliasing tables for now, so we can use table names directly
        joined_tables = {base_table}

        join_clauses = []
        for edge in joins:
            # Decide which side to join based on what we've already included
            if edge.source in joined_tables and edge.target not in joined_tables:
                # join target to existing source
                join_clause = (
                    f"JOIN {edge.target} "
                    f"ON {self._dim_ref(edge.source, edge.source_column)} "
                    f"= {self._dim_ref(edge.target, edge.target_column)}"
                )
                joined_tables.add(edge.target)
                join_clauses.append(join_clause)
            elif edge.target in joined_tables and edge.source not in joined_tables:
                # join source to existing target (reverse direction)
                join_clause = (
                    f"JOIN {edge.source} "
                    f"ON {self._dim_ref(edge.source, edge.source_column)} "
                    f"= {self._dim_ref(edge.target, edge.target_column)}"
                )
                joined_tables.add(edge.source)
                join_clauses.append(join_clause)
            else:
                # Either both already joined, or neither anchored yet.
                # If both are already present, we can skip.
                # If neither is present, this edge will be handled when we
                # reach a connected edge in the path.
                continue

        join_section = ""
        if join_clauses:
            join_section = "\n" + "\n".join(join_clauses)

        # -------- WHERE clause --------
        where_parts = []

        time_predicate = self._apply_time_filter(plan)
        if time_predicate:
            where_parts.append(time_predicate)

        where_clause = ""
        if where_parts:
            where_clause = "\nWHERE " + " AND ".join(where_parts)

        # -------- GROUP BY clause --------
        group_by_clause = ""
        if plan.group_by_dimensions:
            group_exprs = [
                self._dim_ref(dim.table, dim.column)
                for dim in plan.group_by_dimensions
            ]
            group_by_clause = "\nGROUP BY " + ", ".join(group_exprs)

        # -------- Final SQL --------
        sql = (
            select_clause
            + "\n"
            + from_clause
            + join_section
            + where_clause
            + group_by_clause
        )

        return sql
