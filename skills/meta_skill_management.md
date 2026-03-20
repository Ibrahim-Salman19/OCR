---
name: Meta-Skill Management
description: How to identify knowledge gaps and create new skills for the agent.
---

# Meta-Skill Management

## 1. Identification
When to create a new skill?
- **Repetition**: The agent explains something > 2 times.
- **Complexity**: A task requires > 5 steps to verify.
- **Domain Specifics**: Unique constraints (e.g., "Our specific way of handling PDF metadata").

## 2. Creation Process
1. **Draft**: Create `skills/topic_name.md`.
2. **Metadata**: Add YAML frontmatter (`name`, `description`).
3. **Structure**:
   - **Concepts**: What is this?
   - **Commands**: How to do it?
   - **Best Practices**: How to do it *well*?
4. **Verify**: Use the skill in a task to ensure it's actionable.

## 3. Discovery
- **Agent**: The agent should scan `skills/` at the start of complex tasks.
- **User**: The user can ask "What skills do you have?" (Agent lists them).

## 4. Updates
- Skills are living documents.
- If a tool changes, update the relevant skill immediately.
