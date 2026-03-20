---
name: Project Maintenance
description: Routine tasks for keeping the workspace clean, organized, and up-to-date.
---

# Project Maintenance Skill

## 1. Cleaning
- **Temp Files**: `blast_output/` and `.tmp/` accumulate data.
- **Action**: Run a cleanup script (or manual deletion) weekly.
  - Safe to delete: `*.tmp`, `__pycache__`, `logs/*.log` (if archived).

## 2. Dependency Updates
- **Check**: `pip list --outdated`.
- **Update**: `pip install -U -r requirements.txt`.
- **Lock**: Consider `pip-tools` or `poetry` for deterministic builds in future.

## 3. Git Hygiene
- **Commit Messages**: Semantic Commits (`feat:`, `fix:`, `docs:`).
- **Branches**: `main` is stable. Feature branches for big changes.
- **Ignore**: Verify `.gitignore` covers `venv`, `.env`, and output files.

## 4. Documentation
- **Keep Current**: Update `README.md` and `skills/*.md` when code changes.
- **Verify**: Run `verify_foundation.py` after major refactors.
