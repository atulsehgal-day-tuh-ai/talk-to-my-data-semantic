def clean_sql(sql: str) -> str:
    return (
        sql.replace("```sql", "")
           .replace("```", "")
           .strip()
    )


def normalize_rows(rows):
    """
    Normalizes ANY db.run(sql) output into either:
      - a Python scalar
      - a pandas DataFrame
      - None (if nothing returned)
    """
    
    # ---- 1. None or empty --------------------------------------------
    if rows is None:
        return None

    if isinstance(rows, str):
        # Try parsing CSV-style string
        try:
            return pd.read_csv(pd.io.common.StringIO(rows))
        except Exception:
            return rows

    if not rows:  # empty list
        return None

    # ---- 2. Single-value aggregate e.g. [(42,)] or [[42]] -----------------------
    if (
        isinstance(rows, (list, tuple))
        and len(rows) == 1
        and isinstance(rows[0], (list, tuple))
        and len(rows[0]) == 1
    ):
        return rows[0][0]   # <-- return clean scalar (0, 42, etc.)

    # ---- 3. List of scalars e.g. ["A", "B", "C"] ----------------------
    if isinstance(rows, list) and all(
        not isinstance(r, (list, tuple)) for r in rows
    ):
        return pd.DataFrame({"value": rows})

    # ---- 4. List of tuples → DataFrame -------------------------------
    if isinstance(rows, list) and all(isinstance(r, (tuple, list)) for r in rows):
        return pd.DataFrame(rows)

    # ---- 5. Fallback ---------------------------------------------------
    return rows

