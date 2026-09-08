# mcp.build

**mcp.build** is a community to build open source [MCPs](https://modelcontextprotocol.io) (Model Context Protocol servers) that adopted the [Hal9](https://github.com/hal9ai/hal9) open source agent structure for its ease of use for deployment and interoperability.

**Website:** [hal9ai.github.io/mcp.build](https://hal9ai.github.io/mcp.build/) (GitHub Pages from [`/docs`](./docs))

This repo is structured so **coding agents** (Claude Code, Grok Build, Cursor, Codex, …) can contribute with minimal guesswork. Start at [`AGENTS.md`](./AGENTS.md) and [`docs/llms.txt`](./docs/llms.txt).

## Why Hal9 agents?

Hal9 agents are intentionally simple: read from stdin with `input()`, write to stdout with `print()`. No framework lock-in. That shape maps cleanly to how MCPs expose tools to models, and makes agents easy to:

- **Develop** — plain Python, any library
- **Deploy** — `hal9 deploy` or GitHub Actions to [hal9.com](https://hal9.com)
- **Interoperate** — same agent can run as a chatbot, an API, or an MCP tool

## Agents

| Agent | Description | Path |
| --- | --- | --- |
| **send-email** | Send emails with [Resend](https://resend.com) from natural language prompts (Groq tool use) | [`send-email/`](./send-email) |
| **run-python** | Run Python and install PyPI packages from natural language prompts (Groq tool use) | [`run-python/`](./run-python) |

### send-email

Example prompt:

```text
send email to javier@hal9.ai with text hello!
```

The agent:

1. Reads the prompt via `input()`
2. Calls a Groq model with a `send_email` tool definition
3. Maps the tool call to the Resend API
4. Prints the result via `print()`

**Environment variables**

| Variable | Required | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | API key from [console.groq.com](https://console.groq.com) |
| `RESEND_API_KEY` | Yes | API key from [resend.com](https://resend.com) |
| `RESEND_FROM` | No | Sender address (default: `mcp.build <onboarding@resend.dev>`) |
| `GROQ_MODEL` | No | Model id (default: `qwen/qwen3.6-27b`) |

**Local run**

```bash
cd send-email
pip install -r requirements.txt
export GROQ_API_KEY=...
export RESEND_API_KEY=...
echo "send email to you@example.com with text hello!" | python app.py
```

**Deploy to Hal9**

```bash
export HAL9_TOKEN=...   # from https://hal9.com/devs
hal9 deploy send-email --name send-email --access public \
  --title "Send Email" \
  --description "Send emails via Resend using natural language prompts"
```

On push to `main`, if files under `send-email/` change, [`.github/workflows/send-email.yaml`](./.github/workflows/send-email.yaml) deploys a new version to Hal9 (same pattern as [hal9ai/hal9](https://github.com/hal9ai/hal9) app deploy workflows). Set the `HAL9_TOKEN` repository secret in GitHub Actions.

**Publish to the MCP Registry**

The hosted send-email MCP is published as a remote-only server to the [official MCP Registry](https://registry.modelcontextprotocol.io) under `io.github.hal9ai/send-email`. Metadata lives in [`send-email/server.json`](./send-email/server.json). On push to `main` (when `send-email/` changes), [`.github/workflows/publish-send-email.yaml`](./.github/workflows/publish-send-email.yaml) publishes it using GitHub OIDC — **no extra GitHub secrets**. The registry version is `version` in that file. If it is already published, the job skips. Bump `version` there to ship a new registry entry.

### run-python

Example prompt:

```text
install a package that calculates space orbits and compute the Hohmann transfer time from Earth to Mars and back, departing 2026-09-08
```

The agent:

1. Reads the prompt via `input()`
2. Calls a Groq model with `install_packages` and `run_python` tool definitions
3. Installs requested PyPI packages into a sandbox directory
4. Executes the generated Python in a subprocess and captures stdout/stderr
5. Prints the result via `print()`

**Environment variables**

| Variable | Required | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | No | Model id (default: `qwen/qwen3.6-27b`) |
| `PYTHON_TIMEOUT` | No | Seconds allowed for each Python run (default: `60`) |
| `PIP_TIMEOUT` | No | Seconds allowed for pip install (default: `180`) |
| `PACKAGES_DIR` | No | Directory for installed packages (default: a temp dir) |

**Local run**

```bash
cd run-python
pip install -r requirements.txt
export GROQ_API_KEY=...
echo "print the first 10 primes" | python app.py
```

**Deploy to Hal9**

```bash
export HAL9_TOKEN=...   # from https://hal9.com/devs
hal9 deploy run-python --name run-python --access public \
  --title "Run Python" \
  --description "Run Python code from natural language prompts, with optional PyPI package install"
```

On push to `main`, if files under `run-python/` change, [`.github/workflows/run-python.yaml`](./.github/workflows/run-python.yaml) deploys a new version to Hal9. Set the `HAL9_DEVEL_TOKEN` / `HAL9_NEXT_TOKEN` repository secrets in GitHub Actions.

**Publish to the MCP Registry**

The hosted run-python MCP is published as a remote-only server to the [official MCP Registry](https://registry.modelcontextprotocol.io) under `io.github.hal9ai/run-python`. Metadata lives in [`run-python/server.json`](./run-python/server.json). On push to `main` (when `run-python/` changes), [`.github/workflows/publish-run-python.yaml`](./.github/workflows/publish-run-python.yaml) publishes it using GitHub OIDC. Bump `version` in `server.json` to ship a new registry entry.

## Website (GitHub Pages)

Static site lives in [`docs/`](./docs) — no build step.

| Path | Role |
| --- | --- |
| [`docs/index.html`](./docs/index.html) | Landing page — what mcp.build is + list of available MCPs |
| [`docs/send-email/index.html`](./docs/send-email/index.html) | Dedicated page per MCP (usage, "Add to Claude", etc.) — template for new MCPs |
| [`docs/run-python/index.html`](./docs/run-python/index.html) | run-python MCP page |
| [`docs/css/styles.css`](./docs/css/styles.css) | Styles |
| [`docs/agents.json`](./docs/agents.json) | Machine-readable agent catalog |
| [`docs/llms.txt`](./docs/llms.txt) | Short instructions for LLMs / agents |
| [`AGENTS.md`](./AGENTS.md) | Full rules for coding agents |

**Enable Pages:** repo **Settings → Pages → Build and deployment** → Source: **Deploy from a branch** → Branch: `main` → Folder: `/docs`.

## Contributing an agent (MCP)

This repo is designed so **coding agents** (Claude Code, Grok Build, Cursor, Codex, …)
and humans can contribute a new MCP with minimal guesswork. Full checklist:
[`AGENTS.md`](./AGENTS.md). Use [`send-email/`](./send-email) as the reference
implementation and [`.github/workflows/send-email.yaml`](./.github/workflows/send-email.yaml)
as the deploy pattern.

### Expected layout

```text
# minimum
my-tool/
  app.py               # input() → work → print()
  requirements.txt     # optional
  hal9.yaml            # optional welcome

# also update
.github/workflows/my-tool.yaml
docs/agents.json
docs/my-tool/index.html   # dedicated docs page for the MCP
README.md
```

### Minimal agent

```python
# my-tool/app.py
prompt = input()
# … call APIs, tools, models …
print(result)
```

### Steps

1. Create a new folder at the repo root, e.g. `my-tool/`. Keep the name short, kebab-case.
2. Add `app.py`. Use `input()` / `print()` (or any stdin/stdout) so the agent stays
   Hal9- and MCP-friendly. Prefer no `hal9` package unless you need session state.
3. Add a `requirements.txt` if you need third-party packages.
4. Optionally add `hal9.yaml` with a `welcome:` message.
5. Add a GitHub Actions workflow, `.github/workflows/my-tool.yaml`, that deploys when
   that folder changes:

   ```yaml
   on:
     push:
       branches: [main]
       paths:
         - my-tool/**
         - .github/workflows/my-tool.yaml
   # job: pip install hal9 → checkout → if my-tool/ changed:
   hal9 deploy my-tool --name my-tool --access public \
     --title "My Tool" --description "…"
   ```

   Secret: `HAL9_TOKEN` (agent runtime keys like `GROQ_API_KEY` are configured on the
   Hal9 side / local env — never committed).
6. Register the agent in [`docs/agents.json`](./docs/agents.json) (include an `id`,
   `description`, and `docs_path` pointing at its docs page) and mention it in the
   table above.
7. Add a dedicated docs page at `docs/<my-tool>/index.html` so it shows up at
   `https://hal9ai.github.io/mcp.build/my-tool/` (or `https://mcp.build/my-tool/`).
   Copy [`docs/send-email/index.html`](./docs/send-email/index.html) as a template —
   it covers what the MCP does, how agents use it, and how to add it to Claude and
   other MCP clients.
8. Do not commit secrets; document required env vars in this README.

## License

Contributions are welcome. Individual agents may carry their own licenses; see each folder for details.
