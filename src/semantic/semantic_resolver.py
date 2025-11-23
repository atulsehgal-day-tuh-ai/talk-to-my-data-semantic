"""
SemanticResolver class that translates natural language questions into structured semantic plans.

This class uses an LLM (Language Model) to interpret user questions and map them to
semantic model components (measures, dimensions, filters) for query generation.

Attributes:
    model (SemanticModel): The semantic model containing measures and dimensions definitions.
    llm (ChatOpenAI): The language model instance used for natural language processing.

Methods:
    plan_from_question(question: str) -> SemanticPlan:
        Converts a natural language question into a structured semantic plan.
        
        The method performs the following steps:
        1. Extracts available measures and dimensions from the semantic model
        2. Constructs a prompt for the LLM with available schema elements
        3. Asks the LLM to identify relevant measures, dimensions, and filters
        4. Parses the LLM's JSON response
        5. Maps the response to actual semantic model objects
        6. Returns a SemanticPlan object with all resolved components
        
        Args:
            question (str): The user's natural language query (e.g., "What were sales last month?")
        
        Returns:
            SemanticPlan: A structured plan containing:
                - measure: The identified metric to compute
                - time_dimension: The time dimension if applicable
                - time_filter: SQL predicate for time-based filtering
                - group_by_dimensions: List of dimensions for grouping results
        
        Raises:
            KeyError: If the LLM returns measure or dimension names not found in the semantic model
            json.JSONDecodeError: If the LLM response is not valid JSON
"""

from typing import List, Optional
from langchain_openai import ChatOpenAI
import json

from src.semantic.semantic_model import SemanticModel
from src.semantic.semantic_plan import SemanticPlan

class SemanticResolver:
    def __init__(self, semantic_model: SemanticModel):
        self.model = semantic_model
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


    def _detect_time_grain(self, question: str) -> Optional[str]:
        """
        Detect which time grain the user is explicitly asking for
        using semantic keyword matching.

        Why this is needed:
        -------------------
        The user may write:
        "revenue by month this year"
        "daily sales for 90 days"
        "quarterly revenue"
        "region-wise revenue per year"

        The semantic model must automatically choose the correct DATE_TRUNC
        grain in SQL. This function returns one of:
        "day", "month", "quarter", "year"
        or None if nothing is explicitly requested.
        """

        q = question.lower()

        patterns = {
            "day":     ["by day", "daily", "each day", "per day", "day wise"],
            "month":   ["by month", "monthly", "each month", "per month", "month wise"],
            "quarter": ["by quarter", "quarterly", "each quarter", "per quarter"],
            "year":    ["by year", "yearly", "annual", "annually", "each year", "per year"]
        }

        # Loop through patterns and return the FIRST match
        for grain, keywords in patterns.items():
            for kw in keywords:
                if kw in q:
                    return grain

        # Default: no explicit grain
        return None



    def plan_from_question(self, question: str) -> SemanticPlan:
        """
        Convert a natural-language question into a structured SemanticPlan.
        Uses:
        - LLM for semantic interpretation
        - local logic for time-grain detection
        - local model for measure/dimension lookup
        """

        # -------------------------------------------------------------
        # Step 1 — Summaries help the LLM understand the schema context
        # -------------------------------------------------------------
        measure_names = ", ".join(self.model.measures.keys())
        dimension_names = ", ".join(self.model.dimensions.keys())

        # -------------------------------------------------------------
        # Step 2 — Build structured prompt for the LLM
        # -------------------------------------------------------------
        prompt = f"""
            You are a semantic planner converting natural language into a structured semantic plan.

            Available measures: {measure_names}
            Available dimensions: {dimension_names}

            User question: "{question}"

            Tasks:
            1. Identify the correct measure based on meaning + synonyms.
            2. Identify the correct time dimension if present.
            3. Provide a Snowflake SQL time filter using CURRENT_DATE 
            for expressions like "last month", "last 90 days", "last year".
            4. Identify group-by dimensions only when the question implies grouping
            (e.g., "by region", "by product", "per customer").
            5. Return result strictly as this JSON (no narration):

            {{
                "measure": "<measure_name>",
                "time_dimension": "<dimension_name or null>",
                "time_filter": "<SQL predicate or null>",
                "group_by_dimensions": ["<dim>", "<dim>", ...]
            }}

            6. DO NOT include the time dimension itself inside group_by_dimensions.
                Time dimensions should never appear as group-by columns.

            7. If the question implies grouping by a time grain (month, quarter, year):
            - You MUST NOT put the raw time dimension (e.g., "order_date") in group_by_dimensions.
            - The SQL generator will automatically generate DATE_TRUNC('<grain>', <column>)
                — you do NOT need to return any dimension for time grouping.
        """

        # -------------------------------------------------------------
        # Step 3 — Detect time grain BEFORE calling the LLM
        # -------------------------------------------------------------
        time_grain = self._detect_time_grain(question)

        # -------------------------------------------------------------
        # Step 4 — Query the LLM
        # -------------------------------------------------------------
        response_text = self.llm.invoke(prompt).content

        # -------------------------------------------------------------
        # Step 5 — Parse JSON safely
        # -------------------------------------------------------------
        try:
            data = json.loads(response_text)
        except Exception as e:
            raise ValueError(f"LLM returned invalid JSON:\n{response_text}") from e

        # -------------------------------------------------------------
        # Step 6 — Resolve MEASURE
        # -------------------------------------------------------------
        measure_name = data.get("measure")
        if measure_name not in self.model.measures:
            raise KeyError(f"Invalid measure from LLM: {measure_name}")

        measure = self.model.measures[measure_name]

        # -------------------------------------------------------------
        # Step 7 — Resolve TIME DIMENSION
        # -------------------------------------------------------------
        time_dim_name = data.get("time_dimension")
        if time_dim_name:
            time_dim_name = time_dim_name.lower()
            if time_dim_name not in self.model.dimensions:
                raise KeyError(f"Invalid time dimension from LLM: {time_dim_name}")
            time_dim = self.model.dimensions[time_dim_name]
        else:
            time_dim = None

        # -------------------------------------------------------------
        # Step 8 — Resolve GROUP-BY DIMENSIONS
        # -------------------------------------------------------------
        group_by_list = data.get("group_by_dimensions", [])

        # These words must NEVER be treated as dimensions
        TIME_GRAIN_WORDS = {"day", "month", "quarter", "year"}

        group_dims = []
        for dim_name in group_by_list:
            dim_name = dim_name.lower()

            # Skip invalid time-grain pseudo-dimensions
            if dim_name in TIME_GRAIN_WORDS:
                continue

            if dim_name in self.model.dimensions:
                group_dims.append(self.model.dimensions[dim_name])
            else:
                raise KeyError(f"Invalid group-by dimension: {dim_name}")


        # -------------------------------------------------------------
        # Step 9 — Build and return the final semantic plan
        # -------------------------------------------------------------
        return SemanticPlan(
            measure=measure,
            time_dimension=time_dim,
            time_filter=data.get("time_filter"),
            group_by_dimensions=group_dims,
            time_grain=time_grain
        )
