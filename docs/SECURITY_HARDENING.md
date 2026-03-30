# 🛡️ Security Hardening Guide

The B.L.A.S.T. OCR Engine follows a **Defensive-by-Design** strategy. In March 2026, the system underwent a comprehensive forensic audit, resulting in the following hardening measures.

## 1. XXE (XML External Entity) Protection

OCR processing often involves parsing XML-based formats like `.pptx` and `.docx`. By default, standard XML parsers in Python may attempt to resolve external entities, leading to Local File Disclosure (LFD).

-   **Mitigation**: We utilize the `defusedxml` library to globally patch the standard library XML parsers.
-   **Implementation**: `defusedxml.defuse_stdlib()` is called at the entry point of the application, disabling DTDs and external entity resolution.

## 2. Multi-User Session Isolation

In the Streamlit interface, global state pollution can lead to **Cross-User Data Bleeding**, where one user sees another's sensitive document.

-   **Mitigation**: B.L.A.S.T. enforces **Strict Logical Segregation**.
-   **Implementation**:
    -   `st.session_state` is managed via `clear()` instead of total override.
    -   Temporary output directories are generated using **UUID4** per-session (e.g., `/tmp/blast_output/[uuid]/`).
    -   Cleanup loops catch `PermissionError` on Windows to ensure no lingering file handles survive session termination.

## 3. SQL Injection Prevention

The database layer tracks job metadata and performance. Maliciously crafted filenames could theoretically be used for SQL injection.

-   **Mitigation**: All database interactions use the **SQLAlchemy ORM executor**.
-   **Implementation**: We avoid raw string concatenation for queries. The `create_job` and `update_job_status` methods use parameterized objects, ensuring data is never executed as SQL code.

## 4. SQLite WAL Mode Deadlocks

SQLite's default "DEFERRED" transaction mode can lead to shared-lock deadlocks under high concurrency.

-   **Mitigation**: We enforce **Immediate Transactions**.
-   **Implementation**: The engine is initialized with `isolation_level='IMMEDIATE'`. This acquires a `RESERVED` lock upfront, preventing the "Shared -> Exclusive" escalation deadlock scenario.

---

## 🔒 Security Summary Checklist

-   [x] `defusedxml` patched? **Yes.**
-   [x] Parameterized Queries? **Yes.**
-   [x] UUID Subdirectories? **Yes.**
-   [x] Scoped Session Isolation? **Yes.**

## 🔗 Next Steps
-   [Performance Tuning](PERFORMANCE_TUNING.md)
-   [API Reference](API_REFERENCE.md)
