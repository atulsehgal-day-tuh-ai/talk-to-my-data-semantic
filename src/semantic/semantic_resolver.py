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

import numpy as np
from typing import List, Optional
from langchain_openai import ChatOpenAI
import json

from src.semantic.semantic_model import SemanticModel
from src.semantic.semantic_plan import SemanticPlan

from .embedding_store import EmbeddingIndex

class SemanticResolver:
    def __init__(self, semantic_model: SemanticModel, embedding_index: EmbeddingIndex = None, embedding_model=None):
        """
        embedding_index is optional — if provided, we enable embedding-based lookup.
        """
        self.model = semantic_model
        self.embedding_index = embedding_index
        self.embedding_model = embedding_model
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # --------------------------------------------
    # Embedding-powered semantic lookup helpers
    # --------------------------------------------
    def _semantic_best_measure(self, question: str):
        """
        Return the best matching MEASURE using semantic embeddings.

        The logic follows a 4-stage decision pipeline:

        1. **If no embedding index loaded** → fall back to YAML lookup
        2. **Convert question into an embedding vector**
        3. **Retrieve the top semantic matches (filter=measure)**
        4. **Apply a robust acceptance rule**:
                - top1_score must exceed a minimum floor (0.15)
                - AND top1 must beat top2 by a margin (> 0.05)
        If these are satisfied → return that measure.
        Otherwise → fallback to YAML lookup.
        """

        # 1 — Embeddings disabled → use YAML matching
        if not self.embedding_index:
            return self.model.get_measure(question)

        # 2 — Try embedding the user question
        query_vector = self._embed_query_text(question)
        if query_vector is None:
            return self.model.get_measure(question)

        # 3 — Retrieve top-K most similar measures from the embedding index
        results = self.embedding_index.search_measure(query_vector, top_k=5)
        if not results:
            return self.model.get_measure(question)

        # Top-1 result
        best_item, best_score = results[0]

        # Top-2 (if available) for relative comparison
        if len(results) > 1:
            second_item, second_score = results[1]
        else:
            second_score = 0.0

        # ----- Decision Rule -----
        # FLOOR: If the similarity is extremely low → reject it (avoid hallucinations)
        MIN_SCORE = 0.15

        # MARGIN: Top1 must be meaningfully better than top2 → ensures disambiguation
        MARGIN = 0.05

        if best_score >= MIN_SCORE and (best_score - second_score) >= MARGIN:
            return self.model.measures.get(best_item.name)

        # Otherwise → fallback
        return self.model.get_measure(question)


    def _semantic_best_dimension(self, token: str):
        """
        Return the best matching DIMENSION using semantic embeddings.

        Pipeline logic (same structure as measures):

        1. No embedding → YAML fallback
        2. Embed the token (e.g., "cust", "regn")
        3. Query only DIMENSION-type embeddings
        4. Accept result only if:
            - score > minimum floor (0.10–0.15 works well for short dim names)
            - AND top1 is significantly higher than top2 (margin rule)
        Else → revert to YAML dimension resolution.
        """

        # 1 — Embeddings unavailable
        if not self.embedding_index:
            return self.model.get_dimension(token)

        # 2 — Embed the input text
        query_vector = self._embed_query_text(token)
        if query_vector is None:
            return self.model.get_dimension(token)

        # 3 — Retrieve top dimension results
        results = self.embedding_index.search_dimension(query_vector, top_k=5)
        if not results:
            return self.model.get_dimension(token)

        # Extract top-1 and top-2
        best_item, best_score = results[0]
        second_score = results[1][1] if len(results) > 1 else 0.0

        # ----- Thresholds tuned specifically for DIMENSIONS -----
        # Dimensions are short ("nation", "region", "cust") → embeddings match weaker
        MIN_SCORE = 0.12      # slightly lower than measures
        MARGIN = 0.04         # dimensions tend to cluster closer → smaller margin ok

        # Apply decision rule
        if best_score >= MIN_SCORE and (best_score - second_score) >= MARGIN:
            return self.model.dimensions.get(best_item.name)

        # 4 — Fallback to YAML resolution
        return self.model.get_dimension(token)



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

        # Resolve MEASURE (LLM → embeddings → fallback)
        measure_name_llm = data.get("measure")

        # Prefer embedding match over LLM match
        measure = self._semantic_best_measure(measure_name_llm)

        # If the LLM found a measure name, prefer that if valid
        if measure_name_llm and measure_name_llm in self.model.measures:
            measure = self.model.measures[measure_name_llm]

        if not measure:
            raise KeyError(f"Could not resolve measure from question: {question}")

        # -------------------------------------------------------------
        # Step 7 — Resolve TIME DIMENSION
        # -------------------------------------------------------------
        time_dim = None

        if data.get("time_dimension"):
            # First try LLM output
            dim_name_llm = data["time_dimension"]
            if dim_name_llm in self.model.dimensions:
                time_dim = self.model.dimensions[dim_name_llm]

        # If LLM failed → try embedding match on question
        if not time_dim:
            time_dim = self._semantic_best_dimension(question)

        # Validate it is actually a time dimension
        if time_dim and not time_dim.time_grains:
            time_dim = None  # not a real time dim


        # -------------------------------------------------------------
        # Step 8 — Resolve GROUP-BY DIMENSIONS (LLM → embeddings → fallback)
        # -------------------------------------------------------------
        group_dims = []
        group_by_list = data.get("group_by_dimensions", [])

        for dim_name_llm in group_by_list:

            dim_name_llm_lower = dim_name_llm.lower()

            dim = None

            # 1) Direct name match
            if dim_name_llm_lower in self.model.dimensions:
                dim = self.model.dimensions[dim_name_llm_lower]

            # 2) Embedding match (best for fuzzy)
            if dim is None:
                dim = self._semantic_best_dimension(dim_name_llm)

            # 3) No fallback to full question — prevents wrong matches!
            if dim is None:
                raise KeyError(f"Invalid group-by dimension: {dim_name_llm}")

            # 4) Prevent grouping by the time dimension
            if time_dim and dim.name == time_dim.name:
                continue

            group_dims.append(dim)

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

    def _embed_query_text(self, text: str):
        """
        Embed query text using the configured embedding model.
        Uses LangChain's OpenAIEmbeddings.embed_query().
        Prints errors instead of hiding them.
        """
        if self.embedding_model is None:
            print("No embedding_model configured.")
            return None

        try:
            # LangChain OpenAIEmbeddings → returns a Python list
            vec = self.embedding_model.embed_query(text)
            return np.asarray(vec, dtype="float32")

        except Exception as e:
            print(f"[Embedding Error] Could not embed text '{text}': {e}")
            return None
