# Tonight Live Resolve Slice

RAMBLA's temporary live surface is served by the existing FastAPI application at
`http://127.0.0.1:8767/`. It exposes only:

- Probe Resolve
- Dry Run PUNCH_IN
- Apply to Duplicate

The live adapter requires `RAMBLA_RESOLVE_MCP_ROOT`,
`RAMBLA_RESOLVE_BRIDGE_CONFIG`, and `RAMBLA_LIVE_DATA_ROOT`. It connects directly
to the authenticated in-Resolve bridge and never selects a native transport.
Apply accepts a persisted Dry Run plan once, allocates the first free
`REEL_AI_vNN` timeline, applies uniform centered zoom `1.08`, reads the result
back, and verifies that `REEL_MASTER` is unchanged.

The external control plane is
[`samuelgursky/davinci-resolve-mcp`](https://github.com/samuelgursky/davinci-resolve-mcp),
version `3.2.0`, MIT licensed. The source was inspected at upstream commit
`c8fbe1887324de9d897e6036efcde60417e33e8c`. It is installed separately in an
isolated environment and is not vendored into RAMBLA.
