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
                # only grain column (NO raw date)
                grain_expr = (
                    f"DATE_TRUNC('{plan.time_grain}', {time_col}) "
                    f"AS {plan.time_grain}_date"
                )
                select_exprs.append(grain_expr)
            else:
                # raw date (when no grain exists)
                select_exprs.append(f"{time_col} AS {plan.time_dimension.name}")

        # Cleaned group-by dimensions (do NOT mutate the plan!)
        if plan.time_grain and plan.time_dimension:
            cleaned_group_dims = [
                d for d in plan.group_by_dimensions
                if d.name != plan.time_dimension.name
            ]
        else:
            cleaned_group_dims = plan.group_by_dimensions

        # --- Group-by Dimensions ---
        for dim in cleaned_group_dims:
            col_ref = self._dim_ref(dim.table, dim.column)
            select_exprs.append(f"{col_ref} AS {dim.name}")

        select_clause = "SELECT\n  " + ",\n  ".join(select_exprs)

        # =====================================================================
        # 2. FROM CLAUSE + COMPOSITE JOINS
        # =====================================================================
        base_table = plan.measure.table
        from_clause = f"FROM {base_table}"

        # ---- NEW: group join edges by (source,target) OR (target,source)
        join_groups = {}  # key: frozenset({table1,table2}) → list[JoinEdge]

        for e in joins:
            key = frozenset({e.source, e.target})
            join_groups.setdefault(key, []).append(e)

        # ---- DEBUG: print the join groups for inspection
        print("\n=== DEBUG: JOIN GROUPS ===")
        for key, edge_list in join_groups.items():
            print(f"  TABLE PAIR: {key}")
            for ed in edge_list:
                print(f"    - {ed.source}.{ed.source_column} = {ed.target}.{ed.target_column} (role={ed.role})")
        print("==========================\n")

        joined_tables = {base_table}
        join_clauses = []

        # ---- Build JOINs using merged ON conditions
        for tableset, edges_for_pair in join_groups.items():

            t1, t2 = list(tableset)

            # case A: t1 already joined → join t2
            if t1 in joined_tables and t2 not in joined_tables:
                join_table = t2
                other_table = t1

            # case B: t2 already joined → join t1
            elif t2 in joined_tables and t1 not in joined_tables:
                join_table = t1
                other_table = t2

            else:
                # BOTH tables are already joined → we still need composite ON conditions!
                join_table = t1
                other_table = t2

            # --- Build composite ON conditions
            # edge.source always has the left column in YAML
            on_parts = []
            for e in edges_for_pair:
                left = self._dim_ref(e.source, e.source_column)
                right = self._dim_ref(e.target, e.target_column)
                on_parts.append(f"{left} = {right}")

            on_clause = " AND ".join(on_parts)

            # ==============================
            # OPTIONAL DEBUG PRINT — ADD HERE
            # ==============================
            print(f"\n--> DEBUG JOIN BUILD:")
            print(f"    Joining table: {join_table}")
            print(f"    Other table:   {other_table}")
            print(f"    ON: {on_clause}")
            for e in edges_for_pair:
                print(f"       edge: {e.source}.{e.source_column} = {e.target}.{e.target_column} (role={e.role})")
            print()

            join_clauses.append(
                f"JOIN {join_table} ON {on_clause}"
            )

            joined_tables.add(join_table)

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
        group_by_exprs = []

        if grain_expr:
            group_by_exprs.append(grain_expr.split(" AS ")[0])
        elif time_col:
            group_by_exprs.append(time_col)

        for dim in cleaned_group_dims:
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




