import os
from pathlib import Path

def load_env(env_file="configs/dev.env"):
    env_path = Path(__file__).resolve().parents[1] / env_file
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
        print(f"✅ Loaded environment variables from {env_file}")
    else:
        print(f"⚠️  No .env file found at {env_file}")