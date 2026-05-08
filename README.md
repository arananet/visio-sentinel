# visio-sentinel

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white) ![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?logo=opencv&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white) ![OpenSpec](https://img.shields.io/badge/OpenSpec-enforced-blueviolet) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Vision-based home security system using fine-tuned Moondream2 running locally via Ollama, orchestrated by a lightweight async agent that classifies camera frames and routes alerts based on identity confidence.

**No cloud. No subscriptions. Fully offline.**

---

## Architecture

```
Camera (USB / RTSP)
        │
        ▼
 inference/sampler.py          ← async frame generator + motion gate
        │ base64 JPEG frames
        ▼
 inference/analyzer.py         ← Ollama /api/generate → AnalysisResult
        │ {person, known, confidence, timestamp}
        ▼
 agent/agent.py                ← rule evaluator (home_security.md skill)
        │
   ┌────┴────────────────┐
   │                     │
   ▼                     ▼
logs/events.jsonl    snapshots/          ← WARNING / CRITICAL only
                         │
                    ┌────┴──────────┐
                    ▼               ▼
             telegram.py    homeassistant.py
```

Fine-tuning pipeline:

```
Raw video / images
       │
 dataset/prepare.py     ← extract 378×378 frames + manifest.json
       │
 dataset/augment.py     ← albumentations pipeline (train split only)
       │
 training/finetune.py   ← detects Apple Silicon or NVIDIA, delegates ↓
   ├─ finetune_mlx.py   ← mlx_lm.lora (Apple Silicon)
   └─ finetune_cuda.py  ← QLoRA bitsandbytes + peft (NVIDIA)
       │
 training/merge_lora.py ← fuse adapter into base weights
       │
 training/export_gguf.py ← q4_K_M GGUF via llama.cpp
       │
 ollama create home-security -f training/Modelfile
```

---

## Hardware Requirements

### Apple Silicon (primary target)

| | Minimum | Recommended |
|---|---|---|
| Chip | M3 Pro | M4 Pro |
| Unified memory | 18 GB | 24 GB+ |
| Est. training time | 5 h / 1000 samples | 3 h / 1000 samples |

- Ollama uses Metal backend automatically
- Fine-tuning uses **MLX-LM** — bitsandbytes has no Metal support

### NVIDIA GPU

| | Minimum | Recommended |
|---|---|---|
| GPU | RTX 3080 (10 GB VRAM) | RTX 4080+ |
| System RAM | 32 GB | 64 GB |
| CUDA | 12.x + cuDNN | latest |
| Est. training time | 3 h / 1000 samples | 2 h / 1000 samples |

- Ollama uses CUDA backend automatically
- Fine-tuning uses **bitsandbytes QLoRA**

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/arananet/visio-sentinel.git
cd visio-sentinel
bash setup.sh   # installs OpenSpec git hooks
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Ollama

**macOS:**
```bash
brew install ollama
ollama serve   # starts the local server
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env — set CAMERA_SOURCE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, etc.
```

---

## Dataset Preparation

See [`dataset/README.md`](dataset/README.md) for the full guide.

Quick start:

```bash
# Extract frames from your family videos (1 frame/sec default)
python dataset/prepare.py --source videos/person_a.mp4 --label edu
python dataset/prepare.py --source videos/stranger.mp4 --label unknown

# Augment training split 3× to reduce overfitting
python dataset/augment.py --factor 3
```

Target: **≥ 100 train frames per known person** before augmentation.

---

## Training

### Apple Silicon

```bash
python training/finetune.py --config training/config.yaml
```

The router auto-detects Darwin and delegates to `finetune_mlx.py`, which shells out to `mlx_lm.lora`.

### NVIDIA GPU

```bash
python training/finetune.py --config training/config.yaml
```

Detects CUDA, delegates to `finetune_cuda.py` (QLoRA: nf4, double-quant, fp16).

### Merge adapter

```bash
python training/merge_lora.py --config training/config.yaml
# Output: output/merged/
```

---

## GGUF Export and Ollama Registration

### Build llama.cpp

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make -j$(nproc)                    # Linux / Windows with CUDA
# macOS: make -j$(sysctl -n hw.logicalcpu)
pip install -r requirements.txt    # Python deps for convert script
cd ..
```

### Export to GGUF

```bash
export LLAMA_CPP_DIR=./llama.cpp
python training/export_gguf.py --merged output/merged --out output/home-security.gguf
```

### Register with Ollama

```bash
ollama create home-security -f training/Modelfile
ollama run home-security           # smoke test
```

---

## Running the Agent

```bash
python agent/agent.py
```

The agent:
1. Reads `.env` and `agent/skills/home_security.md`
2. Opens the camera (USB index or RTSP URL from `CAMERA_SOURCE`)
3. Samples frames every `FRAME_SAMPLE_INTERVAL` seconds when motion is detected
4. Classifies each frame via Ollama
5. Logs every event as a JSON line to `LOG_PATH`
6. Sends Telegram alerts + snapshots on WARNING or CRITICAL
7. Shuts down cleanly on SIGINT / SIGTERM

### Customizing alert rules

Edit `agent/skills/home_security.md`:

```markdown
## Known Persons
- edu
- person_b
- person_c

## Thresholds
confidence_min: 0.80
night_start: 22
night_end: 6
```

| Condition | Action | Priority |
|---|---|---|
| Known person, any time | Log only | INFO |
| Unknown person, daytime | Telegram + snapshot | WARNING |
| Unknown person, night window | Telegram + snapshot | CRITICAL |
| Confidence < threshold | Treat as unknown | — |
| Parse / inference error | Log error, no alert | ERROR |

---

## AI Agent Integrations

visio-sentinel ships with ready-to-install skills for
[Hermes Agent](https://github.com/nousresearch/hermes-agent) and
[OpenClaw](https://github.com/openclaw/openclaw), plus a CLI controller
(`visio_ctl.py`) designed to be called by those agents.

### visio_ctl.py — CLI controller

```bash
python visio_ctl.py status              # daemon running? last event?
python visio_ctl.py events [N=10]       # last N events from the log
python visio_ctl.py persons             # list known persons
python visio_ctl.py add-person <name>   # add a known person to skill file
python visio_ctl.py remove-person <name># remove a known person
python visio_ctl.py start               # start daemon in background
python visio_ctl.py stop                # stop daemon
python visio_ctl.py tail                # stream events live
```

### Hermes Agent

Install the skill (symlink, so it stays in sync with the repo):

```bash
bash scripts/install_hermes_skill.sh
```

Then in Hermes: `/visio-sentinel`

The skill teaches Hermes to call `visio_ctl.py`, interpret event logs,
manage known persons, and restart the daemon — all from natural language.
Hermes will prompt you once to set `skills.config.visio_sentinel_dir`.

Manual install:

```bash
mkdir -p ~/.hermes/skills/smart-home
ln -s "$(pwd)/skills/hermes/smart-home/visio-sentinel" \
      ~/.hermes/skills/smart-home/visio-sentinel
```

### OpenClaw

Install the skill:

```bash
bash scripts/install_openclaw_skill.sh
```

Then in any OpenClaw channel: `/visio-sentinel`

Manual install:

```bash
ln -s "$(pwd)/skills/openclaw/visio-sentinel" \
      ~/.openclaw/workspace/skills/visio-sentinel
```

---

## Telegram Bot Setup

1. Open [@BotFather](https://t.me/BotFather) in Telegram
2. Send `/newbot` and follow the prompts — copy the **Bot Token**
3. Send a message to your new bot, then visit:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   and copy your **Chat ID** from the JSON response
4. Set in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=<your token>
   TELEGRAM_CHAT_ID=<your chat id>
   ```

---

## Home Assistant Integration (optional)

Set in `.env`:

```
HA_ENABLED=true
HA_WEBHOOK_URL=http://homeassistant.local:8123/api/webhook/visio-sentinel
```

The agent POSTs `{person, known, confidence, priority, timestamp}` to the
webhook on every WARNING or CRITICAL event.

---

## Running Tests

```bash
pytest tests/
```

All tests are unit tests — no real camera, Ollama, or Telegram credentials required.

---

## Troubleshooting

### `RuntimeError: No supported backend found`

You are on Linux without a CUDA-capable GPU. Either run on Apple Silicon (macOS)
or install CUDA 12.x with an NVIDIA RTX GPU.

### `Cannot open camera source`

- USB: try `CAMERA_SOURCE=1` (increment until it works)
- RTSP: verify the URL format: `rtsp://user:pass@192.168.1.x:554/stream`
- On Linux, ensure your user is in the `video` group: `sudo usermod -aG video $USER`

### Metal / MPS out of memory

Reduce `training.batch_size` and `mlx.lora_layers` in `training/config.yaml`.

### Ollama model not found

Run `ollama list` — if `home-security` is missing, re-run:
```bash
ollama create home-security -f training/Modelfile
```

### Low confidence / always unknown

- Add more training data (aim for ≥ 200 frames per person after augmentation)
- Increase `mlx.iters` or `training.epochs` in `training/config.yaml`
- Ensure training images have similar framing/lighting to camera placement

---

## Project Structure

```
visio-sentinel/
├── dataset/
│   ├── prepare.py          # Frame extractor from video / image folder
│   ├── augment.py          # Albumentations augmentation pipeline
│   ├── manifest.json       # Auto-generated training manifest
│   └── README.md
├── training/
│   ├── config.yaml         # All hyperparameters — single source of truth
│   ├── finetune.py         # Unified entry point (backend router)
│   ├── finetune_mlx.py     # Apple Silicon: mlx-lm LoRA
│   ├── finetune_cuda.py    # NVIDIA: bitsandbytes QLoRA
│   ├── merge_lora.py       # Merge adapter into base weights
│   ├── export_gguf.py      # Convert → GGUF q4_K_M for Ollama
│   └── Modelfile           # Ollama Modelfile
├── inference/
│   ├── sampler.py          # Async RTSP/USB frame sampler + motion gate
│   └── analyzer.py         # Async Ollama client → AnalysisResult
├── agent/
│   ├── agent.py            # Main async daemon
│   ├── skills/
│   │   └── home_security.md
│   └── notifiers/
│       ├── telegram.py
│       └── homeassistant.py
├── tests/
│   ├── test_sampler.py
│   ├── test_analyzer.py
│   └── test_agent.py
├── logs/                   # events.jsonl written here at runtime
├── snapshots/              # JPEG snapshots on WARNING / CRITICAL
├── requirements.txt
├── .env.example
└── CLAUDE.md
```

---

**Developer:** Eduardo Arana — [@arananet](https://github.com/arananet)

**License:** [MIT](LICENSE)

---

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/H2H51MPWG)
