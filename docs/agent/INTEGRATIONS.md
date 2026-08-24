# Integrations and Connector Contract

| Service | Purpose | Evidence | Write boundary |
|---|---|---|---|
| GitHub | Source/review | Verified | Branch and PR within task |

Add services only when verified. Prefer authenticated MCP, then approved CLI/SDK, then controlled browser work. Verify target account/project with a harmless read. Keep credentials in approved secret systems. Production, data, auth/security, credential, billing, messaging, and destructive changes remain approval gates unless explicitly authorized.
