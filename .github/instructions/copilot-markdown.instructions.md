---
description: "Applies to markdown and documentation updates. Keeps formatting, section structure, and pasted tables readable in collaborative editing."
applyTo: "**/*.md"
---

# Keeping Columns Aligned When Pasting

Use built-in VS Code features and optionally one extension to prevent tabs from breaking column alignment.

## Key Rules

- Use a **monospaced font** (e.g. JetBrains Mono, Consolas, Menlo)
- Use **spaces only** — tabs render differently in every app
- In Teams, paste inside a **code block** to preserve alignment

---

## Options

### 1. Built-in VS Code (no extension needed)

- **Command Palette:** `Convert Indentation to Spaces`
- **Settings to enable:**
  - `Editor: Insert Spaces` = on
  - `Editor: Detect Indentation` = off
  - `Editor: Tab Size` = 2 or 4
  - `View: Render Whitespace` = all (makes tabs visible)

---

### 2. EditorConfig Extension (recommended)

**Extension:** [EditorConfig for VS Code](https://marketplace.visualstudio.com/items?itemName=EditorConfig.EditorConfig)

Automatically enforces indentation rules per project. Add a `.editorconfig` file to the repo root:

```ini
root = true

[*]
indent_style = space
indent_size = 2
end_of_line = lf
insert_final_newline = true
```

---

### 3. Prettier (optional)

Normalizes indentation on save for supported file types.

- Enable `Editor: Format on Save` = on

---

## VS Code Settings JSON Snippet

```json
{
  "editor.insertSpaces": true,
  "editor.detectIndentation": false,
  "editor.tabSize": 2,
  "editor.renderWhitespace": "all",
  "editor.fontFamily": "JetBrains Mono, Menlo, Monaco, 'Courier New', monospace",
  "editor.fontLigatures": true,
  "editor.formatOnSave": true
}
```

Open with: `Cmd+Shift+P` → `Preferences: Open User Settings (JSON)`
