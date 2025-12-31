import os

env_path = ".env"

if os.path.exists(env_path):
    print(f"Reading {env_path}...")
    with open(env_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("=", 1)
        key = parts[0].strip()
        val = parts[1].strip() if len(parts) > 1 else "(NO VALUE)"
        val_preview = val[:4] + "..." if len(val) > 4 else val
        print(f"Line {i + 1}: Key='{key}' Value starts with '{val_preview}'")

        if "GEMINI" in key.upper():
            print(f"  ^^^ FOUND MATCHING KEY: {key}")
else:
    print(".env file not found.")
