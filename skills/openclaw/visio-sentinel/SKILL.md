---
name: visio-sentinel
description: Home security vision AI running locally — classify camera frames, manage known persons, view alerts, and control the daemon. No cloud, no subscription.
---

# visio-sentinel

Local-first home security system powered by a fine-tuned Moondream2 vision model
served by Ollama. Classifies camera frames, routes Telegram alerts for unknown
persons, and logs every event as structured JSON.

---

## CLI controller

Use `visio_ctl.py` for all agent interactions:

```bash
# Daemon health and last event
python visio_ctl.py status

# Recent events (last N, default 10)
python visio_ctl.py events [N]

# List / manage known persons
python visio_ctl.py persons
python visio_ctl.py add-person <name>
python visio_ctl.py remove-person <name>

# Start / stop daemon
python visio_ctl.py start
python visio_ctl.py stop

# Stream live events
python visio_ctl.py tail
```

---

## Key configuration

`.env` file in the installation directory:

```
CAMERA_SOURCE=0                    # USB index or rtsp://... URL
FRAME_SAMPLE_INTERVAL=2            # seconds between frames
CONFIDENCE_THRESHOLD=0.80          # below → treat as unknown
UNKNOWN_ALERT_HOUR_START=22        # night window start
UNKNOWN_ALERT_HOUR_END=6           # night window end
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_CHAT_ID=<id>
HA_ENABLED=false
HA_WEBHOOK_URL=
SNAPSHOT_DIR=./snapshots
LOG_PATH=./logs/events.jsonl
```

Edit `agent/skills/home_security.md` to manage known persons and thresholds
without retraining.

---

## Alert priorities

| Priority | Condition |
|---|---|
| `INFO` | Known person, any time — log only |
| `WARNING` | Unknown person, daytime — Telegram + snapshot |
| `CRITICAL` | Unknown person, night window — Telegram + snapshot |
| `ERROR` | Parse or inference failure — log only |

---

## Common workflows

**Was anyone detected today?**
```bash
python visio_ctl.py events 100
```

**Add a new family member (no retraining needed for rules):**
```bash
python visio_ctl.py add-person alice
```
Then collect photos and retrain the vision model:
```bash
python dataset/prepare.py --source videos/alice.mp4 --label alice
python dataset/augment.py
python training/finetune.py
```

**Restart after changing camera source:**
```bash
python visio_ctl.py stop
# Edit .env: CAMERA_SOURCE=rtsp://...
python visio_ctl.py start
```

---

## References

- `.env.example` — all environment variables with defaults
- `training/config.yaml` — model hyperparameters
- `agent/skills/home_security.md` — alert rules and known persons
- `logs/events.jsonl` — structured event log
- `snapshots/` — JPEG snapshots for WARNING/CRITICAL events
