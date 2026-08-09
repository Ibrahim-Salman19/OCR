---
name: Python Mastery
description: Guide to Python coding standards, best practices, and patterns used in B.L.A.S.T. (2026 Edition)
---

# Python Mastery Skill (2026 Edition)

## 1. Modern Tooling
We adopt the "Speed First" toolchain.
- **Installer**: Use **`uv`** instead of `pip`.
  - Why: 10-100x faster, Rust-based, unified venv management.
  - Cmd: `uv pip install -r requirements.txt`
- **Linter/Formatter**: Use **`Ruff`** instead of `flake8`/`black`/`isort`.
  - Why: Single binary, instant execution, replaces 10+ tools.
  - Config: `pyproject.toml` (standardized).

## 2. Type Hinting
We enforce strict typing for better tooling support.
- **Use**: `List`, `Dict`, `Optional`, `Union`, `Callable`.
- **Why**: Catches bugs early. Ruff's type-checking rules integrations help here.

## 3. Asynchronous Patterns
B.L.A.S.T. uses a mix of sync and async.
- **Sync**: `pdf2image`, `opencv` (CPU-bound).
- **Async**: UI updates.
- **Pattern**: When wrapping blocking calls in async, use `run_in_executor`.

## 4. Documentation
- **Docstrings**: Google Style.
  ```python
  def func(arg1: int) -> int:
      """
      Description.
      
      Args:
          arg1: Description.
      """
  ```
