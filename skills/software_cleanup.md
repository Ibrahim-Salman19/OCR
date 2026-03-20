---
name: Software Cleanup (Vibe Check)
description: A systematic guide to professionalizing "vibe coded" software—moving from fast chaos to structured reliability.
---

# Software Cleanup: The "Vibe Check"

This skill is for when you've written code "in the zone" (fast, messy, effective) and now need to make it maintainable for the long haul.

## 1. The Vibe Audit (Identification)
Use grep/ripgrep to find "smells" typical of vibe coding:
- **Magic Numbers**: Hardcoded values (e.g., `time.sleep(5)`, `if x > 100`).
- **Mega-Functions**: Functions > 50 lines doing 3+ things.
- **Global Mutations**: Modifying global state willy-nilly.
- **Copy-Paste**: Similar blocks repeated 3+ times.

**Command**:
```bash
# Find TODOs and FIXMEs left behind
grep -r "TODO" .
grep -r "FIXME" .
```

## 2. The Deterministic Detox (Linting & Formatting)
Stop arguing about style. Enforce it automatically.
- **Tool**: **`Ruff`** (The 2026 Standard).
- **Rule Set**: Use `select = ["E", "F", "I", "UP", "B"]` in `pyproject.toml`.
  - `E/F`: Standard errors (flake8).
  - `I`: Import sorting (isort).
  - `UP`: Upgrade syntax (pyupgrade).
  - `B`: Bugbear (common bugs).

**Command**:
```bash
ruff check --fix .
ruff format .
```

## 3. The Structure Upgrade (Architecture)
Refactor "Script" code into "Library" code.

### Step A: Configuration Injection
**Bad (Hardcoded)**:
```python
def process():
    file = open("data.txt") ...
```

**Good (Injected)**:
```python
def process(file_path: str):
    ...
```

### Step B: The "Main" Guard
Ensure no code runs on import. All scripts must have:
```python
if __name__ == "__main__":
    main()
```

### Step C: Logging > Print
Replace all `print()` statements with structured logging.
- **Why**: `print` vanishes in production or clutters output. `logger` can be filtered, filed, and formatted.

## 4. The Safety Net (Typing & Tests)
- **Type Hints**: Add types to function signatures. `def foo(x: int) -> str:`
- **Smoke Tests**: Write one test that runs the whole pipeline end-to-end on a tiny input.
  - If this passes, you haven't broken the world.

## 5. The "Vibe" Checklist
Before merging/deploying, ask:
1. [ ] Can a stranger run this without asking me for help? (README check)
2. [ ] Does it crash if the internet disconnects? (Error handling check)
3. [ ] Are there secrets (API keys) in the code? (Security check)
