# 🤖 Talk-to-My-Data: Semantic SQL Engine

Talk-to-My-Data is an enterprise-grade Semantic RAG Application that enables non-technical users to query Snowflake databases using natural language.

Unlike basic "Text-to-SQL" bots that hallucinate table joins, this project uses a deterministic Semantic Layer and Graph Theory to ensure **100% accurate SQL generation**, correct business logic (e.g., Profit formulas), and safe query execution.

---

## 🚀 Key Features

- 🧠 **Semantic Intent Resolution**: Uses LLMs (GPT-4o) + Vector Embeddings (`text-embedding-3-large`) to map fuzzy user terms (e.g., "gross margin", "cust") to precise database columns.
- 🕸️ **Graph-Based Join Routing**: Directed JoinGraph + BFS for accurate join paths.
- 🛤️ **Role-Aware Navigation**: Picks Customer Region vs Supplier Region intelligently.
- 🔗 **Composite Join Support**: Prevents row explosion in schemas like TPC-H.
- ⏳ **Time Grain Intelligence**: Injects DATE_TRUNC dynamically.
- 🔍 **Transparent Reasoning**: Shows Semantic Plan → Join Path → SQL → Data.

---

## 📂 Project Structure

```plaintext
talk-to-my-data/
├── artifacts/                  # Generated vector stores
│   └── semantic_embeddings_tpch.json
├── configs/                    # Configuration
│   └── dev.env                 # API Keys & DB Creds
├── notebooks/                  # Jupyter notebooks for component validation
├── scripts/                    # Utility scripts
│   └── build_embeddings_index.py
├── src/                        # Source Code
│   ├── db_connector.py         # Snowflake connection logic
│   ├── main_app.py             # Streamlit UI Entry Point
│   └── semantic/               # THE CORE ENGINE
│       ├── model_tpch.yml      # The Semantic Model Definition
│       ├── semantic_model.py   # YAML Loader & Logic
│       ├── semantic_resolver.py# Intent Parsing (LLM + Embeddings)
│       ├── join_graph.py       # Graph Topology & BFS
│       ├── join_resolver.py    # Pathfinding Strategy
│       ├── sql_generator.py    # Snowflake SQL Compiler
│       └── embedding_store.py  # Vector Search Logic
└── requirements.txt            # Python Dependencies
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- Python 3.10+
- Snowflake Account (TPC-H Sample Data)
- OpenAI API Key

### 2. Clone & Install

```bash
git clone https://github.com/your-repo/talk-to-my-data.git
cd talk-to-my-data
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

Create `configs/dev.env`:

```bash
# Snowflake Credentials
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ROLE=ACCOUNTADMIN
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DB=SNOWFLAKE_SAMPLE_DATA
SNOWFLAKE_SCHEMA=TPCH_SF1

# AI Credentials
OPENAI_API_KEY=sk-proj-...

# Optional: LangSmith Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=semantic-sql-v1
```

---

## ⚡ Usage

### 1. Build Embedding Index

```bash
python -m scripts.build_embeddings_index
```

**Output:**  
```
Saved embedding index to artifacts/semantic_embeddings_tpch.json
```

### 2. Run Streamlit App

```bash
streamlit run src/main_app.py
```

---

## 🧠 How It Works (Architecture)

### **Layer 1: Semantic Model**
Defines tables, measures, dimensions, and join relationships.

### **Layer 2: Semantic Resolution**
Embeddings + LLM extract:
- measure
- group-by dimensions
- time grain
- filters  
producing a **SemanticPlan**.

### **Layer 3: Graph Routing**
BFS selects join paths while applying:
- composite join rules  
- role preference logic  
- cycle detection  

### **Layer 4: SQL Generator**
Transforms the plan + join edges into Snowflake SQL with:
- DATE_TRUNC  
- composite ON conditions  
- clean GROUP BY  

---

# 🏗️ System Architecture Diagram (Deep Dive)

Below is the complete, low-level architecture exactly as in the Word document.

---

## **1. Data Layer — The Source of Truth**

### Module: `src.semantic.semantic_model`  
### Class: **SemanticModel**

#### `__init__(spec)`  
- Loads YAML semantic model.  
- Builds **Column Index** mapping every column → table.  
- Compiles regex to extract column references inside formulas.

#### `infer_tables_from_expression(expr)`  
- Input example:  
  `SUM(l_extendedprice - ps_supplycost * l_quantity)`  
- Detects column usage across tables.  
- Returns `{lineitem, partsupp}`.  
- **Purpose**: Required for multi-table measures like Profit.

---

## **2. Intent Layer — Understanding the Question**

### Module: `src.semantic.embedding_store`  
### Class: **EmbeddingIndex**

- Stores vector embeddings of measures & dimensions.  
- Performs cosine similarity searches:  
  - `search_measure(vec)`
  - `search_dimension(vec)`  
- Enables fuzzy matching (“GM” → “Profit”).

---

### Module: `src.semantic.semantic_resolver`  
### Class: **SemanticResolver**

Primary brain converting English → Structured Plan.

#### `plan_from_question(question)`
- Detects:
  - time grain (“monthly”, “quarterly”)
  - measure
  - filters  
- Runs an LLM call to extract structured intent.

#### `_semantic_best_measure` & `_semantic_best_dimension`
- If text matches YAML → use it.  
- Else → embed + fuzzy-match via EmbeddingIndex.  
- Example: “profitability” → “profit”.

---

## **3. Topology Layer — Join Pathfinding**

### Module: `src.semantic.join_graph`  
### Class: **JoinGraph**

#### `from_model(model)`
- Reads YAML relationships.  
- Splits composite join keys into parallel edges.  
- Respects directed edges (no reverse auto-creation).

#### `find_path(start, target, preferred_roles)`
- Uses **Breadth-First Search (BFS)**.  
- Applies **role-aware prioritization**.  
- Prevents cycles with path history.

---

### Module: `src.semantic.join_resolver`  
### Class: **JoinResolver**

#### `joins_for_plan(plan)`
- Gathers all required tables:
  - measure deps  
  - time dimension  
  - group-by dimensions  
- Calls JoinGraph to compute paths.  
- Retrieves all edges (including multi-key edges) for SQL assembly.

---

## **4. Synthesis Layer — SQL Generation**

### Module: `src.semantic.sql_generator`  
### Class: **SQLGenerator**

Converts Plan + Join Edges → **Snowflake SQL**.

#### Key behaviors:

- **Time filters**: rewrites `order_date` into fully qualified form.  
- **Time grain**: injects  
  `DATE_TRUNC('quarter', o_orderdate)`  
- **Composite joins**: groups edges using frozenset logic to produce:  
  ```
  ON l.partkey = ps.partkey
     AND l.suppkey = ps.suppkey
  ```
- Ensures no row explosion.

---

# 🔄 End-to-End Data Flow Example

### Query: **“Profit by quarter in 1992”**

1. **SemanticResolver**
   - “Profit” → measure  
   - “Quarter” → time grain  
   - “1992” → filter expression  

2. **JoinResolver**
   - Profit uses `ps_supplycost`  
   - Needs `partsupp`  
   - Path:  
     `lineitem → orders` (date)  
     `lineitem → partsupp` (profit dependencies)

3. **JoinGraph**
   - Returns 2 edges:  
     - partkey  
     - suppkey  

4. **SQLGenerator**
   - Builds SELECT + DATE_TRUNC  
   - Joins partsupp with composite ON  
   - Produces correct, safe Snowflake SQL  

5. **Main App**
   - Executes SQL  
   - Displays DataFrame  

---


---


# 🔍 What is BFS and Why Does the Join Resolver Use It?

In the context of the **Layer 3: Graph Routing** diagram, **BFS** stands for **Breadth-First Search** — a fundamental algorithm used to explore graphs (networks of connected nodes).  
In this system, BFS is used to determine **how database tables should be joined** to satisfy a Semantic Plan.

---

## **1. What is BFS?**

Think of dropping a stone into a calm pond:

- Ripples expand outward in perfect circles.
- The closest areas are touched first.
- Then the next layer.
- Then the next.

BFS works the same way when searching a graph:

1. Start at a given table (e.g., `customer`)
2. **Level 1:** Check all tables directly connected to it
3. **Level 2:** Check all tables connected to those tables
4. Repeat until the **target table** is found

It explores the graph **layer by layer**.

---

## **2. Why BFS for Join Pathfinding?**

When generating SQL, the system needs to find a path from **Table A → Table B**.

Example:

- **Path A:** `A → B` (simple, 1 join)
- **Path B:** `A → C → D → B` (complex, 3 joins)

BFS guarantees:

> **The first time we reach the target table, we have found the shortest possible join path.**

This ensures:

- Shorter join paths → **faster SQL**
- Fewer hops → **more accurate joins**
- Deterministic behavior → **no hallucinated join chains**

---

## **3. What Rules Does BFS Apply?**

Your JoinGraph + JoinResolver extend BFS with domain-specific logic:

### ✔ Composite Join Rules
Some relationships require multiple keys  
(e.g., `lineitem` ↔ `partsupp` needs both `partkey` *and* `suppkey`).  
BFS verifies all required keys before traversing the edge.

### ✔ Cycle Detection
Schemas may have loops: `A → B → C → A`  
BFS maintains a **visited set** to prevent infinite loops.

### ✔ Role Preference
If multiple valid paths exist (e.g. customer vs supplier geography),  
BFS uses **preferred role rules** to choose the correct path and avoid ambiguity.

---

## **4. How BFS Connects to the Code**

### **SemanticModel**
- Loads YAML relationships  
- Produces the “edges” for the graph  

### **JoinGraph + BFS**
- Traverses those edges  
- Applies rules  
- Finds the shortest, valid join chain  

Together:

- The **Semantic Plan** defines *WHAT* to compute  
- **BFS Join Resolution** defines *HOW* to compute it  

---


# 🗺️ Database Join Diagram (Semantic Relationship Graph)

```plaintext
                      ┌──────────────┐
                      │    region    │
                      │  (r_region)  │
                      └──────┬───────┘
                             │
                             │ r_regionkey = n_regionkey
                             ▼
                      ┌──────────────┐
                      │    nation    │
                      │  (n_nation)  │
                      └──────┬───────┘
                             │
                             │ n_nationkey = c_nationkey
                             ▼
                      ┌──────────────┐
                      │   customer   │
                      │ (c_custkey)  │
                      └──────┬───────┘
                             │
                             │ c_custkey = o_custkey
                             ▼
                      ┌──────────────┐
                      │    orders    │
                      │ (o_orderkey) │
                      └──────┬───────┘
                             │
                             │ o_orderkey = l_orderkey
                             ▼
                      ┌──────────────┐
                      │   lineitem   │
                      │ (l_orderkey) │
                      └──────┬───────┬─────────────┐
                             │       │             │
                             │       │             │
                 l_partkey = │       │ = l_suppkey │
                             ▼       ▼             ▼
                      ┌──────────┐ ┌──────────┐ ┌────────────┐
                      │   part   │ │ partsupp │ │  supplier   │
                      │ p_partkey│ │ ps_part  │ │ s_suppkey   │
                      └──────────┘ └──────────┘ └────────────┘
```

This join graph is essential for the Semantic Resolver to generate correct SQL queries
from natural language questions.

---


# 🧩 Side-by-Side Logical vs Physical Relationship Diagram

```plaintext
┌─────────────────────────────── LOGICAL MODEL ────────────────────────────────┐
│                                                                               │
│   Region → Nation → Customer → Orders → Lineitem → (Part, Supplier, PartSupp)│
│                                                                               │
│   • Region groups Nations                                                     │
│   • Nations define customer geography                                         │
│   • Customers place Orders                                                    │
│   • Orders contain Lineitems                                                  │
│   • Lineitem references Product & Supplier cost relationships                 │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘


┌────────────────────────────── PHYSICAL MODEL ────────────────────────────────┐
│                                                                               │
│     region                nation                customer                      │
│   (r_regionkey)        (n_nationkey)         (c_custkey)                      │
│        │                     │                    │                           │
│        │ r_regionkey =       │ n_nationkey =      │ c_custkey =               │
│        ▼ n_regionkey         ▼ c_nationkey        ▼ o_custkey                 │
│                                                                               │
│                          orders                                               │
│                        (o_orderkey)                                           │
│                              │                                                │
│                              │ o_orderkey = l_orderkey                        │
│                              ▼                                                │
│                          lineitem                                             │
│                        (l_orderkey)                                           │
│                          /       │        \                                   │
│             l_partkey = /        │         \ = l_suppkey                      │
│                      ▼          ▼                ▼                             │
│                   part       partsupp          supplier                       │
│               (p_partkey)   (ps_part)        (s_suppkey)                      │
│                                                                               │
│  Composite Join Logic: lineitem ↔ partsupp uses BOTH:                         │
│      • l_partkey = ps_part                                                    │
│      • l_suppkey = ps_suppkey                                                 │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

This diagram shows the **business logical view** (top) and the **physical SQL topology** (bottom).

---

Built with ❤️ using **Streamlit**, **LangChain**, and **Snowflake**.
