"""
LoRA fine-tuning on Apple Silicon via mlx-lm.
"""

import base64
import json
import logging
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def _to_base64_jpeg(image_path: Path) -> str:
    with Image.open(image_path).convert("RGB") as img:
        buf = __import__("io").BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode()


def _build_jsonl(samples: list[dict], image_root: str, out_path: Path) -> None:
    root = Path(image_root)
    with out_path.open("w") as f:
        for sample in samples:
            record = {
                "image": _to_base64_jpeg(root / sample["image"]),
                "question": sample["question"],
                "answer": sample["answer"],
            }
            f.write(json.dumps(record) + "\n")


def run(cfg: dict, samples: list[dict], adapter_path: str) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "train.jsonl"
        _build_jsonl(samples, cfg["dataset"]["image_root"], jsonl_path)
        logger.info("MLX-LM JSONL written: %d records", len(samples))

        mlx_cfg = cfg["mlx"]
        t_cfg = cfg["training"]
        cmd = [
            "python", "-m", "mlx_lm.lora",
            "--model", cfg["model"]["base_id"],
            "--train",
            "--data", tmpdir,
            "--iters", str(mlx_cfg["iters"]),
            "--batch-size", str(t_cfg["batch_size"]),
            "--lora-layers", str(mlx_cfg["lora_layers"]),
            "--adapter-path", adapter_path,
        ]
        logger.info("Running: %s", " ".join(cmd))
        subprocess.run(cmd, check=True)

    logger.info("MLX-LM training complete. Adapter at: %s", adapter_path)


if __name__ == "__main__":
    import yaml

    cfg = yaml.safe_load(open("training/config.yaml"))
    import json
    manifest = json.loads(open(cfg["dataset"]["manifest"]).read())
    train_entries = [e for e in manifest if e["split"] == "train"]
    from training.finetune import build_qa_dataset
    samples = build_qa_dataset(train_entries, cfg["qa_templates"])
    run(cfg, samples, str(Path(cfg["model"]["output_dir"]) / "lora-adapter"))
