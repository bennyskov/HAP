# Project Objective: HAP Workspace for Hermes in VS Code

## Objective

HAP is the workspace layer that keeps Hermes-related tooling, runtime setup, and project conventions operating cleanly in VS Code. It is the operational foundation for building and maintaining Hermes-based work, not a business-domain application itself.

## Scope

`HAP` covers the runtime, tooling, and conventions needed to make Hermes work reliably in this development environment.

### `BASE` Scope: System and Runtime Maintenance
- macOS setup required for reliable Hermes operation.
- Homebrew-managed binaries and local CLI dependencies.
- Shell configuration needed for Hermes commands and local tooling.
- Hermes runtime health, updates, gateway status, and configuration under `~/.hermes`.

### `HERMES` Scope: Shared Framework and Conventions
- Shared scripts, helpers, modules, and utilities used across projects.
- Common file structure, naming, and project organization rules.
- Reusable patterns for configuration, data handling, logging, validation, and execution flow.
- Framework-level automation that supports project development and maintenance.
- Documentation and standards that keep Hermes projects consistent with each other.

## AI operating rule

Use the active repository as the source of truth. Prefer current project files over archived, generated, or duplicate content.
