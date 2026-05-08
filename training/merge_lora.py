"""
Merge LoRA adapter into base model weights.
"""

import argparse
import platform
import subprocess
from pathlib import Path

import yaml


def merge_cuda(cfg: dict, adapter_path: str, merged_path: str) -> None:
    from peft import AutoPeftModelForCausalLM

    model = AutoPeftModelForCausalLM.from_pretrained(
        adapter_path,
        device_map="auto",
        trust_remote_code=True,
    )
    merged = model.merge_and_unload()
    merged.save_pretrained(merged_path)
    print(f"Merged model saved to: {merged_path}")


def merge_mlx(cfg: dict, adapter_path: str, merged_path: str) -> None:
    cmd = [
        "python", "-m", "mlx_lm.fuse",
        "--model", cfg["model"]["base_id"],
        "--adapter-path", adapter_path,
        "--save-path", merged_path,
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"Merged model saved to: {merged_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge LoRA adapter into base model")
    parser.add_argument("--config", default="training/config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    adapter_path = str(Path(cfg["model"]["output_dir"]) / "lora-adapter")
    merged_path = str(Path(cfg["model"]["output_dir"]) / "merged")

    if platform.system() == "Darwin":
        merge_mlx(cfg, adapter_path, merged_path)
    else:
        merge_cuda(cfg, adapter_path, merged_path)


if __name__ == "__main__":
    main()
