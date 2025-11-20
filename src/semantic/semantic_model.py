"""
Semantic Model Module for Data Analysis

This module provides a comprehensive framework for defining and managing semantic layers
over database schemas. It enables users to define tables, columns, measures, dimensions,
and relationships in a declarative YAML format, which can then be used to translate
natural language queries into SQL.

Classes:
    Column: Represents a database column with metadata including role, description,
            synonyms, and foreign key references.
    
    Table: Represents a database table with its type (fact/dimension), primary key,
           description, and a collection of columns.
    
    Measure: Represents a calculated metric/KPI with an expression, source table,
             description, and synonyms for natural language processing.
    
    Dimension: Represents a dimension attribute used for slicing/filtering data,
               including support for time grains (year, quarter, month, etc.).
    
    Relationship: Defines foreign key relationships between tables, including
                  cardinality types (one_to_many, many_to_one, etc.).
    
    SemanticModel: Main class that loads and manages the complete semantic layer
                   definition from YAML configuration files.

Usage Example:
    >>> model = SemanticModel.from_yaml("path/to/semantic_model.yaml")
    >>> revenue_measure = model.get_measure("total_revenue")
    >>> date_dimension = model.get_dimension("order_date")
    >>> print(revenue_measure.expression)
    >>> print(date_dimension.time_grains)

The semantic model supports:
    - Loading table schemas with column metadata
    - Defining calculated measures with SQL expressions
    - Creating dimension hierarchies with time grain support
    - Establishing table relationships for join operations
    - Synonym matching for natural language query interpretation
    - YAML-based configuration for easy maintenance and version control

Note:
    This module follows Microsoft content policies and is designed to assist
    with database semantic layer development and management.
"""


from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml


# -----------------------------
# Data Classes for Semantics
# -----------------------------

@dataclass
class Column:
    name: str
    role: Optional[str] = None
    description: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)
    references: Optional[str] = None


@dataclass
class Table:
    name: str
    type: str
    primary_key: Optional[Any] = None  # can be str or list
    description: Optional[str] = None
    columns: Dict[str, Column] = field(default_factory=dict)


@dataclass
class Measure:
    name: str
    expression: str
    table: str
    description: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)


@dataclass
class Dimension:
    name: str
    table: str
    column: str
    description: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)
    time_grains: List[str] = field(default_factory=list)


@dataclass
class Relationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    type: str
    description: Optional[str] = None


# ----------------------------------
# The Semantic Model Loader
# ----------------------------------

class SemanticModel:
    def __init__(self, spec: Dict[str, Any]):
        self.raw = spec

        self.tables = self._load_tables(spec.get("tables", {}))
        self.measures = self._load_measures(spec.get("measures", {}))
        self.dimensions = self._load_dimensions(spec.get("dimensions", {}))
        self.relationships = self._load_relationships(spec.get("relationships", []))

    # ---------- Loaders ----------

    @staticmethod
    def from_yaml(path: str) -> "SemanticModel":
        text = Path(path).read_text(encoding="utf-8")
        spec = yaml.safe_load(text)
        return SemanticModel(spec)

    def _load_tables(self, table_block: Dict[str, Any]) -> Dict[str, Table]:
        tables = {}
        for table_name, info in table_block.items():
            table = Table(
                name=table_name,
                type=info.get("type"),
                primary_key=info.get("primary_key"),
                description=info.get("description"),
                columns=self._load_columns(info.get("columns", {})),
            )
            tables[table_name] = table
        return tables

    def _load_columns(self, column_block: Dict[str, Any]) -> Dict[str, Column]:
        columns = {}
        for col_name, info in column_block.items():
            column = Column(
                name=col_name,
                role=info.get("role"),
                description=info.get("description"),
                synonyms=info.get("synonyms", []),
                references=info.get("references"),
            )
            columns[col_name] = column
        return columns

    def _load_measures(self, block: Dict[str, Any]) -> Dict[str, Measure]:
        out = {}
        for name, info in block.items():
            out[name] = Measure(
                name=name,
                expression=info["expression"],
                table=info["table"],
                description=info.get("description"),
                synonyms=info.get("synonyms", []),
            )
        return out

    def _load_dimensions(self, block: Dict[str, Any]) -> Dict[str, Dimension]:
        out = {}
        for name, info in block.items():
            out[name] = Dimension(
                name=name,
                table=info["table"],
                column=info["column"],
                description=info.get("description"),
                synonyms=info.get("synonyms", []),
                time_grains=info.get("time_grains", []),
            )
        return out

    def _load_relationships(self, block: List[Dict[str, Any]]) -> List[Relationship]:
        rels = []
        for rel in block:
            from_table, from_col = rel["from"].split(".")
            to_table, to_col = rel["to"].split(".")
            rels.append(
                Relationship(
                    from_table=from_table,
                    from_column=from_col,
                    to_table=to_table,
                    to_column=to_col,
                    type=rel.get("type", "many_to_one"),
                    description=rel.get("description"),
                )
            )
        return rels


# ----------------------------------
# Convenience Methods
# ----------------------------------

    def get_measure(self, name_or_synonym: str) -> Optional[Measure]:
        key = name_or_synonym.lower()

        # direct match
        if key in self.measures:
            return self.measures[key]

        # synonym match
        for m in self.measures.values():
            if key in [s.lower() for s in m.synonyms]:
                return m

        return None

    def get_dimension(self, name_or_synonym: str) -> Optional[Dimension]:
        key = name_or_synonym.lower()

        if key in self.dimensions:
            return self.dimensions[key]

        for d in self.dimensions.values():
            if key in [s.lower() for s in d.synonyms]:
                return d

        return None
