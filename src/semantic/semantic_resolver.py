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

    def plan_from_question(self, question: str) -> SemanticPlan:
        # Step 1: Prepare schema summary for the LLM
        measure_names = ", ".join(self.model.measures.keys())
        dimension_names = ", ".join(self.model.dimensions.keys())

        # Step 2: Build prompt for semantic reasoning
        prompt = f"""
You are a semantic planner converting natural language into a structured semantic plan.

Available measures: {measure_names}
Available dimensions: {dimension_names}

User question: "{question}"

Tasks:
1. Identify the correct measure based on synonyms and meaning.
2. Identify the correct time dimension if present.
3. Provide a Snowflake SQL time filter using CURRENT_DATE if the question asks for
   "last month", "last 3 months", "last year", etc.
4. Identify group-by dimensions if the question implies grouping.
5. Return result strictly in this JSON format:

{{
  "measure": "<measure_name>",
  "time_dimension": "<dimension_name or null>",
  "time_filter": "<SQL predicate or null>",
  "group_by_dimensions": ["<dim>", "<dim>", ...]
}}
"""

        # Step 3: Call LLM
        response = self.llm.invoke(prompt).content

        # Step 4: Parse resulting JSON
        data = json.loads(response)

        measure = self.model.measures[data["measure"]]

        time_dim_name = data.get("time_dimension")
        time_dim = self.model.dimensions[time_dim_name] if time_dim_name else None

        group_dims = [
            self.model.dimensions[name]
            for name in data.get("group_by_dimensions", [])
        ]

        return SemanticPlan(
            measure=measure,
            time_dimension=time_dim,
            time_filter=data.get("time_filter"),
            group_by_dimensions=group_dims,
        )
