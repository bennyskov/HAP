# Hermes Learning Model

In Hermes Agent, "learning" means breaking out of the usual stateless AI pattern. Instead of forgetting everything after a session ends, Hermes keeps a persistent learning loop that improves over time.

The system turns successful work into reusable procedures. It captures what worked, refines it, and retrieves it later when similar tasks appear.

This is not just memory. It is operational memory that becomes reusable behavior.

---

## The learning loop

Hermes follows a repeated five-step cycle:

[Task Execution] → [Outcome Evaluation] → [Skill Extraction] → [Skill Refinement] → [Skill Retrieval]

### 1. Task execution

The agent receives a goal, breaks it into steps, and uses its available tools to complete the task. That may include file operations, Python execution, shell commands, or other environment actions.

### 2. Outcome evaluation

After execution, Hermes compares the result with the original objective. It looks for feedback in two forms:

- Explicit feedback: the user corrects, changes, or refines the result.
- Implicit feedback: the user accepts the output without further changes.

### 3. Skill extraction

When a task is successful and non-trivial, Hermes creates or updates a skill document. This is not a generic note. It is a structured reusable instruction describing when a workflow works and why.

The skill is written in a structured Markdown format aligned with the agentskills pattern. It captures the logic of: "when the context looks like this, this approach is effective."

### 4. Skill refinement

Skills are not static. Hermes revisits them as new tasks arrive. If it finds a cleaner approach, a better sequence, or a better match to the user’s preferred working style, it updates the stored skill.

### 5. Skill retrieval

When a new request appears, Hermes searches its skill registry and loads the most relevant skill into context. This reduces the need to solve the same problem from scratch and cuts wasted tokens, retry loops, and avoidable mistakes.

---

## Memory structure

Hermes organizes learned behavior across different memory layers:

- Procedural memory: reusable workflow skills.
- User memory: communication style, preferences, standards, and repeated patterns.
- Context memory: the current task and relevant project state.

The procedural layer is usually segmented to avoid polluting the main prompt context. A short summary is kept at a shallow level, and the full workflow is retrieved only when needed.

---

## Why this matters

Most AI systems rely on prompts or static retrieval. Hermes treats learning as an executable system.

It records successful workflows, updates them over time, and uses them to adapt to the user’s environment. The result is a more specialized assistant that becomes more aligned with the user’s actual working patterns instead of staying generic.

This is the key difference: Hermes does not just remember chat history. It converts successful behavior into reusable operational knowledge.
