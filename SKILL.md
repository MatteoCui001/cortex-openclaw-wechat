# cortex-openclaw-wechat

Connect your local Cortex knowledge infrastructure to WeChat via OpenClaw.

## What it does

- **Ingest**: Forward links, articles, and text notes from WeChat into Cortex
- **Inbox**: View and act on Cortex notifications (read / ack / dismiss)
- **Feedback**: Rate signals (useful / not_useful / wrong / save_for_later)
- **Push**: Receive Cortex webhook notifications via a local relay

## First-time setup

On first use, the skill runs a bootstrap that:
1. Checks macOS, Python 3.12+, uv, PostgreSQL 16+, pgvector, zhparser
2. Clones or locates your Cortex repo at `~/Projects/cortex`
3. Runs `make dev` to install dependencies
4. Creates `config.local.yaml` with your settings
5. Runs database migrations (001-009)
6. Starts the local Cortex API server
7. Saves connection config for future sessions

## Commands (via WeChat)

| Input | Action |
|-------|--------|
| Forward a link | `POST /events/ingest` with URL |
| Send text | `POST /events/ingest` as note |
| `inbox` or `收件箱` | `GET /notifications` |
| `read <id>` | `POST /notifications/{id}/read` |
| `ack <id>` | `POST /notifications/{id}/ack` |
| `dismiss <id>` | `POST /notifications/{id}/dismiss` |
| `useful <id>` / `not_useful <id>` | `POST /signals/{id}/feedback` |

## Architecture

```
WeChat -> OpenClaw (iLink) -> Skill (command router)
                                  |
                                  v
                           Local Cortex API (127.0.0.1:8420)
                                  |
                                  v (webhook)
                           Local Relay (127.0.0.1:8421)
                                  |
                                  v
                           OpenClaw Sink -> WeChat push
```

## Configuration

After bootstrap, config is stored at `~/.cortex/skill_config.yaml`:

```yaml
cortex:
  base_url: http://127.0.0.1:8420/api/v1
  workspace: default
openclaw:
  ingress_url: http://127.0.0.1:8422
relay:
  port: 8421
  enabled: true
```
