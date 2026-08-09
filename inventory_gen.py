from pathlib import Path


def count_lines(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except:
        return "N/A"


def generate_inventory():
    root = Path(".")
    print("## COMPLETE FILE INVENTORY")
    print("\n### Directory Structure")
    print("```")
    # Simple tree view (abbreviated)
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            if not any(
                excluded in str(path)
                for excluded in [
                    ".git",
                    "__pycache__",
                    "venv",
                    "cache",
                    "logs",
                    "output",
                ]
            ):
                depth = len(path.parts) - 1
                print(f"{'│   ' * depth}├── {path.name}/")
    print("```")

    print("\n### Python Files")
    print("| # | File Path | Lines | Purpose | Status |")
    print("|---|-----------|-------|---------|--------|")

    i = 1
    py_files = sorted(list(root.rglob("*.py")))
    for p in py_files:
        if any(excluded in str(p) for excluded in [".git", "venv"]):
            continue
        lines = count_lines(p)
        status = "⏳ Not audited"
        print(f"| {i} | {p} | {lines} | ... | {status} |")
        i += 1

    print("\n### Config/Data Files")
    print("| File | Type | Purpose |")
    print("|------|------|---------|")
    for p in sorted(list(root.rglob("*"))):
        if p.name in ["requirements.txt", ".env", "config.py"] or p.suffix in [
            ".json",
            ".toml",
            ".yaml",
        ]:
            if not any(
                excluded in str(p) for excluded in [".git", "venv", "cache", "logs"]
            ):
                print(f"| {p} | {p.suffix} | ... |")


if __name__ == "__main__":
    generate_inventory()
