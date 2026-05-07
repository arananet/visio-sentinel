---
name: visio-sentinel
description: >
  Use when the user asks about home security camera events, unknown person alerts,
  camera status, or wants to manage known persons, configure alert thresholds,
  or start/stop the visio-sentinel vision AI daemon. Use when the user says
  "who is at the door", "show me recent security events", "add person to security
  system", or "is the security camera running".
version: 1.0.0
author: arananet
license: MIT
metadata:
  hermes:
    tags: [smart-home, security, camera, vision, ai, ollama, local-first]
    related_skills: [home-assistant, telegram-notifications, local-ai]
    config:
      - key: skills.config.visio_sentinel_dir
        description: Absolute path to the visio-sentinel installation directory
        default: ~/visio-sentinel
        prompt: "Where is visio-sentinel installed? (e.g. ~/visio-sentinel)"
      - key: skills.config.visio_env_file
        description: Path to the .env file used by the daemon
        default: ~/visio-sentinel/.env
        prompt: "Path to visio-sentinel .env file?"
---

# visio-sentinel

**visio-sentinel** is a local-first, offline home security system.
It fine-tunes a small vision model (Moondream2) on your family's photos, runs it
via Ollama, and streams alerts to Telegram (or Home Assistant) when an unknown
person is detected.

Installation directory: `${HERMES_SKILL_DIR}/../../../../`
Use the configured path: `skills.config.visio_sentinel_dir`

---

## Available CLI commands

All commands run via `visio_ctl.py` from the installation directory.

```bash
# Show daemon status and last event
python visio_ctl.py status

# Show the last N events (default 10)
python visio_ctl.py events [N]

# List known persons configured in the skill file
python visio_ctl.py persons

# Add a new known person
python visio_ctl.py add-person <name>

# Remove a known person
python visio_ctl.py remove-person <name>

# Stream live events (tail the event log)
python visio_ctl.py tail

# Start the daemon in the background
python visio_ctl.py start

# Stop the daemon
python visio_ctl.py stop
```

---

## Configuration

All runtime config lives in `.env`. Key variables:

| Variable | Purpose | Default |
|---|---|---|
| `CAMERA_SOURCE` | USB index (0,1,…) or RTSP URL | `0` |
| `FRAME_SAMPLE_INTERVAL` | Seconds between samples | `2` |
| `MOTION_PIXEL_THRESHOLD` | Pixel delta to trigger emit | `500000` |
| `CONFIDENCE_THRESHOLD` | Below this → treat as unknown | `0.80` |
| `UNKNOWN_ALERT_HOUR_START` | Night window start (24h) | `22` |
| `UNKNOWN_ALERT_HOUR_END` | Night window end (24h) | `6` |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | — |
| `TELEGRAM_CHAT_ID` | Your chat or group ID | — |
| `HA_ENABLED` | Enable Home Assistant webhook | `false` |
| `HA_WEBHOOK_URL` | Home Assistant webhook URL | — |
| `SNAPSHOT_DIR` | Where to save alert snapshots | `./snapshots` |
| `LOG_PATH` | Structured JSON event log | `./logs/events.jsonl` |

Alert rules are in `agent/skills/home_security.md` — edit `Known Persons` and
`Thresholds` there to manage family members and confidence settings.

---

## Common tasks

### Check if someone unknown was detected today

```bash
python visio_ctl.py events 50 | grep -i unknown
```

### Add a new family member

```bash
python visio_ctl.py add-person alice
# Then collect photos/video of alice and retrain:
python dataset/prepare.py --source videos/alice.mp4 --label alice
python dataset/augment.py
python training/finetune.py
```

### Restart daemon after config change

```bash
python visio_ctl.py stop
# Edit .env as needed
python visio_ctl.py start
```

### Check confidence on a specific frame (one-shot)

```bash
python inference/analyzer.py  # prompts with a 1x1 test image
```

---

## Event log format

Every classified frame appends one JSON line to `LOG_PATH`:

```json
{"ts": "2026-05-07T14:32:01Z", "person": "edu", "known": true, "confidence": 0.94, "priority": "INFO", "error": null}
```

Priority levels: `INFO` (known person), `WARNING` (unknown, daytime),
`CRITICAL` (unknown, night window), `ERROR` (parse/inference failure).

---

## Troubleshooting

- **Daemon not running**: `python visio_ctl.py start` — check `.env` is present
- **Always unknown**: lower `CONFIDENCE_THRESHOLD` or add more training data
- **No Telegram alerts**: verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
- **RTSP won't open**: check URL format `rtsp://user:pass@ip:554/stream`
- **Metal OOM on Mac**: reduce `training.batch_size` in `training/config.yaml`
