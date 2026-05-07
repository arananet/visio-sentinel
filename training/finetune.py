"""
Unified fine-tuning entry point. Detects backend and delegates to the right module.
"""

import argparse
import json
import platform
import sys
from pathlib import Path

import yaml


def get_backend() -> str:
    if platform.system() == "Darwin":
        return "mlx"
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    raise RuntimeError("No supported backend found. Need Apple Silicon or NVIDIA GPU.")


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_manifest(manifest_path: str, image_root: str) -> list[dict]:
    manifest = json.loads(Path(manifest_path).read_text())
    return [e for e in manifest if e["split"] == "train"]


def build_qa_dataset(entries: list[dict], templates: list[dict]) -> list[dict]:
    """Build (image_path, question, answer) triples from manifest + templates."""
    samples = []
    for entry in entries:
        label = entry["label"]
        for tpl in templates:
            if label == "unknown":
                answer = tpl["answer_unknown"]
            else:
                answer = tpl["answer_known"].format(label=label)
            samples.append({
                "image": entry["image"],
                "question": tpl["question"],
                "answer": answer,
            })
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune Moondream2")
    parser.add_argument("--config", default="training/config.yaml")
    args = parser.parse_args()

    backend = get_backend()
    print(f"Detected backend: {backend}")

    cfg = load_config(args.config)
    entries = load_manifest(cfg["dataset"]["manifest"], cfg["dataset"]["image_root"])
    print(f"Training samples (pre-template): {len(entries)}")

    samples = build_qa_dataset(entries, cfg["qa_templates"])
    print(f"QA pairs built: {len(samples)}")

    adapter_path = str(Path(cfg["model"]["output_dir"]) / "lora-adapter")

    if backend == "mlx":
        from training.finetune_mlx import run as run_mlx
        run_mlx(cfg, samples, adapter_path)
    else:
        from training.finetune_cuda import run as run_cuda
        run_cuda(cfg, samples, adapter_path, cfg["dataset"]["image_root"])

    print(f"\nAdapter saved to: {adapter_path}")
    print(f"Next step: python training/export_gguf.py --merged output/merged --out output/home-security.gguf")


if __name__ == "__main__":
    main()
