---
name: UI Development
description: Guide to the Streamlit-based UI, styling, and extension (2026 Edition).
---

# UI Development Skill (2026 Edition)

## 1. Framework
Built with **Streamlit** (v1.37+ features).

## 2. Performance: Fragments
**CRITICAL**: Use `@st.fragment` for high-performance interactive components.
- **Concept**: Rerun *only* the annotated function, not the whole page.
- **Use Case**:
  - Independent counters/timers.
  - Real-time status badges.
  - Form inputs that don't affect global state.

```python
@st.fragment
def show_status(job_id):
    # This reruns every 5s WITHOUT reloading the whole app
    status = db.get_status(job_id)
    st.badge(status)
    time.sleep(5)
    st.rerun()
```

## 3. Styling System (CSS)
We use a **Custom CSS Injection** approach for a "Premium" look.
- **Glassmorphism**: `.glass-card`.
- **Gradients**: `.blast-title`.

## 4. Component Architecture
- **Sidebar**: Config.
- **Main Area**: `st.empty()` placeholders combined with fragments for smooth updates.
