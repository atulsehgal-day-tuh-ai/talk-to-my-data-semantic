"""
Talk-to-My-Data: Semantic SQL Streamlit Application

This script represents the Frontend/UI layer of the application.
It connects the user (via browser) to the Semantic Engine (Backend).

Architecture Flow:
1. User Input (Natural Language)
2. Semantic Resolver (Intent -> Plan)
3. Join Resolver (Topology -> Path)
4. SQL Generator (Plan + Path -> SQL)
5. Database Execution (Snowflake -> DataFrame)
6. UI Rendering (Streamlit)

Key Streamlit Concepts Used:
- @st.cache_resource: Loads heavy objects (Model, Embeddings) only once to save memory/time.
- st.session_state: "Memory" that persists variables across browser re-runs.
- st.status: The container used to show the "Thinking..." animation.
"""

import streamlit as st
import pandas as pd
import json
import os
import time
from pathlib import Path
import sys
from dataclasses import asdict

# =============================================================================
# 0. PATH SETUP (CRITICAL FIX)
# =============================================================================
# Streamlit runs scripts from the top level. We must manually add the project root
# to sys.path BEFORE importing our custom modules, or Python won't find 'src'.
# -----------------------------------------------------------------------------
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# =============================================================================
# 1. IMPORTS
# =============================================================================
# Now that sys.path is fixed, we can import from 'src' without errors.

# --- Semantic Engine Components (The "Backend") ---
from src.semantic.semantic_model import SemanticModel
from src.semantic.semantic_resolver import SemanticResolver
from src.semantic.join_graph import JoinGraph
from src.semantic.join_resolver import JoinResolver
from src.semantic.sql_generator import SQLGenerator
from src.semantic.embedding_store import EmbeddingIndex
from langchain_openai import OpenAIEmbeddings

# --- Database Connector (Separation of Concerns) ---
from src.db_connector import get_db_connection

# --- Configuration Loader ---
from utils.config_loader import load_env

# =============================================================================
# 2. APP CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title="Talk to My Data (Semantic)",
    page_icon="🤖",
    layout="wide", # Use full screen width for data tables
    initial_sidebar_state="expanded"
)

# Load env vars (API Keys, Snowflake Creds) immediately
load_env()


# =============================================================================
# 3. INITIALIZATION & CACHING (The "Brain")
# =============================================================================
# @st.cache_resource ensures we only load the heavy model/embeddings ONCE.
# Without this, every interaction would reload the YAML (slow).
@st.cache_resource
def get_semantic_engine():
    """
    Initializes the Semantic Engine stack.
    Returns a dictionary with all core components ready to use.
    """
    print("--- [SYSTEM] Initializing Semantic Engine... ---")
    
    # 1. Load Semantic Model (YAML)
    # The 'Source of Truth' for business definitions.
    model_path = project_root / "src/semantic/model_tpch.yml"
    if not model_path.exists():
        st.error(f"❌ Critical Error: Model file not found at {model_path}")
        st.stop()
        
    model = SemanticModel.from_yaml(str(model_path))
    
    # 2. Load Embeddings (JSON)
    # Allows fuzzy matching (e.g., "cust" -> "customer").
    emb_path = project_root / "artifacts/semantic_embeddings_tpch.json"
    embedding_index = None
    
    if emb_path.exists():
        try:
            with emb_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                embedding_index = EmbeddingIndex.from_dict(data)
            print("✅ Embeddings loaded successfully.")
        except Exception as e:
            print(f"⚠️ Warning: Failed to load embeddings: {e}")
    else:
        print("⚠️ Warning: No embedding file found. Running in keyword-only mode.")
    
    # 3. Setup Embedding Model
    # Must match the model used in build_embeddings_index.py (text-embedding-3-large).
    # Used to convert User Questions into Vectors.
    emb_model = OpenAIEmbeddings(model="text-embedding-3-large")
    
    # 4. Initialize Logic Components
    
    # Semantic Resolver: The "Planner" (Uses LLM + Embeddings)
    sem_resolver = SemanticResolver(
        model, 
        embedding_index=embedding_index, 
        embedding_model=emb_model
    )
    
    # Join Graph: The "Map" (Knows tables and edges)
    # We construct it from the model to learn the topology.
    jg = JoinGraph.from_model(model)
    
    # Join Resolver: The "Navigator" (Finds paths on the map)
    # CORRECTED: Only passing 'jg' as confirmed by your validation notebook.
    join_resolver = JoinResolver(jg)
    
    # SQL Generator: The "Translator" (Writes the Snowflake query)
    sql_gen = SQLGenerator()
    
    print("--- [SYSTEM] Engine Initialization Complete ---")
    
    return {
        "model": model,
        "sem_resolver": sem_resolver,
        "join_resolver": join_resolver,
        "sql_gen": sql_gen
    }

# Load the engine. If it fails (e.g. bad API key), stop the app.
try:
    engine = get_semantic_engine()
except Exception as e:
    st.error(f"Failed to load Semantic Engine: {e}")
    st.stop()


# =============================================================================
# 4. DATABASE HELPER
# =============================================================================
def execute_sql_safely(sql):
    """
    Executes SQL using the centralized db_connector.
    Handles connection errors gracefully and returns a Pandas DataFrame.
    """
    conn = None
    try:
        # Get connection from src/db_connector.py
        conn = get_db_connection()
        
        # Execute query
        cur = conn.cursor()
        cur.execute(sql)
        
        # Fetch results
        result = cur.fetchall()
        
        # Get column names from the cursor description
        columns = [desc[0] for desc in cur.description]
        
        # Convert to Pandas DataFrame for easy Streamlit rendering
        df = pd.DataFrame(result, columns=columns)
        return df
        
    except Exception as e:
        # Raise error so UI can display it
        raise e 
    finally:
        if conn:
            conn.close()

# =============================================================================
# 5. UI LAYOUT & SIDEBAR
# =============================================================================
st.title("🤖 Talk to My Data")
st.caption("Enterprise Semantic Search powered by Snowflake & OpenAI")

# Sidebar: Shows system health
with st.sidebar:
    st.header("Engine Status")
    st.success("✅ Semantic Model Loaded")
    
    if engine["sem_resolver"].embedding_index:
        st.success(f"✅ Embeddings Active ({len(engine['sem_resolver'].embedding_index.items)} items)")
    else:
        st.warning("⚠️ Embeddings Inactive")
    
    st.markdown("---")
    st.info("""
    **Architecture:**
    1. **Plan:** Identify Intent (LLM)
    2. **Resolve:** Find Join Paths (Graph BFS)
    3. **Compile:** Generate SQL
    4. **Execute:** Snowflake Data
    """)

# =============================================================================
# 6. CHAT HISTORY (SESSION STATE)
# =============================================================================
# Streamlit re-runs script on interaction. We use session_state to remember chat.
if "messages" not in st.session_state:
    st.session_state.messages = []

# Redraw previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # If message has metadata (SQL/DataFrame), show it
        if "sql" in message:
            with st.expander("🔍 View Generated SQL"):
                st.code(message["sql"], language="sql")
        if "df" in message:
            st.dataframe(message["df"], hide_index=True)

# =============================================================================
# 7. MAIN INTERACTION LOOP
# =============================================================================
if prompt := st.chat_input("Ask a question (e.g., 'profit by quarter in 1992')"):
    
    # A. Display User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # B. Process Request
    with st.chat_message("assistant"):
        
        # Container for the "Thinking..." visualization
        status_container = st.status("🧠 Analyzing your question...", expanded=True)
        
        try:
            # --- STEP 1: SEMANTIC RESOLUTION ---
            status_container.write("**Step 1: Understanding Intent**")
            
            # Detects intent using LLM + Embeddings
            plan = engine["sem_resolver"].plan_from_question(prompt)
            
            # Show the user what we understood
            with st.expander("See Semantic Plan", expanded=False):
                # Build a nice list of grouping keys (Time + Dimensions)
                groups = []
                if plan.time_grain:
                    groups.append(f"{plan.time_grain} ({plan.time_dimension.name})")
                for d in plan.group_by_dimensions:
                    groups.append(d.name)
                
                group_str = ", ".join(groups) if groups else "None"

                st.markdown(f"""
                * **Measure:** `{plan.measure.name}` (Table: `{plan.measure.table}`)
                * **Time Dimension:** `{plan.time_dimension.name if plan.time_dimension else 'None'}`
                * **Time Grain:** `{plan.time_grain if plan.time_grain else 'None'}`
                * **Time Filter:** `{plan.time_filter}`
                * **Effective Grouping:** `{group_str}`
                """)

            # Inside the 'See Semantic Plan' expander block
            with st.expander("See Semantic Plan (JSON)", expanded=False):
                st.json(asdict(plan))
            
            # --- STEP 2: JOIN RESOLUTION ---
            status_container.write("**Step 2: Resolving Join Path**")
            
            # Determines correct graph path (Composite Joins handled here)
            joins = engine["join_resolver"].joins_for_plan(plan)
            
            # Show the user the path we took
            # Visualize the Path
            with st.expander("See Join Path", expanded=False):
                if not joins:
                    st.info("Single Table Query (No Joins Needed)")
                else:
                    for i, edge in enumerate(joins):
                        # --- UPDATED LINE BELOW ---
                        # We now show Table.Column -> Table.Column
                        st.markdown(f"**{i+1}.** `{edge.source}.{edge.source_column}` 🔗 `{edge.target}.{edge.target_column}`")
                        
                    st.caption("Composite joins (e.g. PartKey + SuppKey) merged automatically.")

            # --- STEP 3: SQL GENERATION ---
            status_container.write("**Step 3: Compiling Snowflake SQL**")
            
            # Writes the final query
            sql = engine["sql_gen"].sql_from_plan(plan, joins)
            
            # Show the raw SQL
            with st.expander("See Generated SQL", expanded=False):
                st.code(sql, language="sql")

            # --- STEP 4: EXECUTION ---
            status_container.write("**Step 4: Running Query**")
            
            # Hit the database
            df = execute_sql_safely(sql)
            
            # Mark "Thinking" as complete
            status_container.update(label="✅ Complete!", state="complete", expanded=False)

            # --- STEP 5: FINAL OUTPUT ---
            if df is not None and not df.empty:
                # 1. Show Data
                st.dataframe(df, hide_index=True)

                # 2. Response Text
                row_count = len(df)
                response_text = f"I found **{row_count} rows** for your query about **{plan.measure.name}**."
                st.write(response_text)
                
                # 3. Save to History
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response_text,
                    "sql": sql,
                    "df": df
                })
                
            else:
                st.warning("Query executed successfully, but returned 0 rows.")
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": "I ran the query but found no data matching your filters.",
                    "sql": sql
                })

        except Exception as e:
            # Error Handling: Show red box and log error
            status_container.update(label="❌ Error Occurred", state="error")
            st.error(f"I couldn't process that question.\n\n**Reason:** `{e}`")
            st.session_state.messages.append({
                "role": "assistant", 
                "content": f"⚠️ Error: {str(e)}"
            })