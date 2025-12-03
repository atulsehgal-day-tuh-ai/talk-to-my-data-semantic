# scripts/build_embeddings_index.py

import json
import os
from pathlib import Path

from utils.config_loader import load_env
from src.semantic.semantic_model import SemanticModel
from src.semantic.embedding_store import build_index_from_model

# Load OPENAI_API_KEY etc.
load_env()

project_root = Path(__file__).resolve().parents[1]

model_path = project_root / "src" / "semantic" / "model_tpch.yml"
out_path = project_root / "artifacts" / "semantic_embeddings_tpch.json"
out_path.parent.mkdir(parents=True, exist_ok=True)

# Load semantic model
model = SemanticModel.from_yaml(str(model_path))

# IMPORTANT: tell the embedding builder which model to use
index = build_index_from_model(
    model,
    embedding_model="text-embedding-3-large"   # ← REQUIRED
)

# Save index
with out_path.open("w", encoding="utf-8") as f:
    json.dump(index.to_dict(), f, indent=2)

print(f"Saved embedding index to {out_path}")
