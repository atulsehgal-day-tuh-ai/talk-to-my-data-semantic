
"""
Represents a semantic query plan for data analysis.

This module defines the SemanticPlan dataclass which encapsulates the components
needed to execute a semantic query, including measures, dimensions, and filters.

Attributes:
    measure (Measure): The measure to be aggregated or calculated in the query.
    time_dimension (Optional[Dimension]): The time-based dimension for temporal analysis.
        Can be None if time-based grouping is not required.
    time_filter (Optional[str]): A filter expression to restrict the time range.
        Can be None if no time filtering is needed.
    group_by_dimensions (List[Dimension]): A list of dimensions to group the results by.
        Can be an empty list if no grouping is required.
"""

from dataclasses import dataclass
from typing import List, Optional
from src.semantic.semantic_model import Measure, Dimension

# This object represents the intent of the question.
@dataclass
class SemanticPlan:
    measure: Measure
    time_dimension: Optional[Dimension]
    time_filter: Optional[str]
    group_by_dimensions: List[Dimension]
    time_grain: Optional[str] = None #Represents the grain to GROUP BY:"day", "month", "quarter", "year". If None, we group by raw date column.
