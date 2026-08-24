# Agent Continuity Entry Point

Read the existing `AGENTS.md` if present, then `docs/agent/PROJECT_KNOWLEDGE.md`, `docs/agent/INTEGRATIONS.md`, and `docs/agent/HANDOFF.md`.

Continuity is part of every build. Before final verification, update durable context for material commands, environment-variable **names**, services, connectors, data sources, constraints, and decisions discovered. After verification, update the handoff if work is incomplete or blocked, including current state, affected files, tests and exact failures, environment state, approval required, and one executable next action. If complete, clear stale steps and set `Status: Complete — no active handoff`.

Never record secrets, values, credentials, keys, customer data, or private infrastructure identifiers. Work autonomously on routine reversible repository tasks. Verify connectors with a harmless read. Pause for production, destructive/data writes, credentials/permissions, auth/security, billing, public publishing, or access outside the task.
