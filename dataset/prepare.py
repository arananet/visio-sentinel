"""
Frame extractor: video file or image folder → labeled dataset with manifest.
"""

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

import cv2
from PIL import Image

NATIVE_SIZE = (378, 378)
JPEG_QUALITY = 90


def _save_jpeg(img: Image.Image, path: Path) -> None:
    img = img.resize(NATIVE_SIZE, Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", quality=JPEG_QUALITY)


def _extract_from_video(
    source: str, label: str, fps: float, output_root: Path
) -> list[Path]:
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {source}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(native_fps / fps))
    label_dir = output_root / "known" / label
    frames: list[Path] = []
    frame_idx = 0
    saved_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step == 0:
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            path = label_dir / f"frame_{saved_idx:04d}.jpg"
            _save_jpeg(img, path)
            frames.append(path)
            saved_idx += 1
        frame_idx += 1

    cap.release()
    return frames


def _extract_from_folder(source: str, label: str, output_root: Path) -> list[Path]:
    src = Path(source)
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    image_files = sorted(p for p in src.rglob("*") if p.suffix.lower() in extensions)
    if not image_files:
        raise RuntimeError(f"No images found in folder: {source}")

    subdir = "unknown" if label == "unknown" else "known"
    label_dir = output_root / subdir / label
    frames: list[Path] = []

    for idx, src_path in enumerate(image_files):
        img = Image.open(src_path).convert("RGB")
        path = label_dir / f"frame_{idx:04d}.jpg"
        _save_jpeg(img, path)
        frames.append(path)

    return frames


def _assign_splits(frames: list[Path], split_ratio: float) -> list[tuple[Path, str]]:
    shuffled = frames.copy()
    random.shuffle(shuffled)
    n_train = math.ceil(len(shuffled) * split_ratio)
    result = []
    for i, p in enumerate(shuffled):
        result.append((p, "train" if i < n_train else "val"))
    return result


def _load_manifest(path: Path) -> list[dict]:
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_manifest(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract labeled frames for training")
    parser.add_argument("--source", required=True, help="Video file or image folder")
    parser.add_argument("--label", required=True, help="Identity label, e.g. 'edu'")
    parser.add_argument("--fps", type=float, default=1.0, help="Extraction rate (video only)")
    parser.add_argument("--output", default="./dataset", help="Output root directory")
    parser.add_argument("--split", type=float, default=0.85, help="Train ratio, e.g. 0.85")
    args = parser.parse_args()

    output_root = Path(args.output)
    source = args.source

    if Path(source).is_file():
        frames = _extract_from_video(source, args.label, args.fps, output_root)
    else:
        frames = _extract_from_folder(source, args.label, output_root)

    split_frames = _assign_splits(frames, args.split)

    manifest_path = output_root / "manifest.json"
    entries = _load_manifest(manifest_path)
    existing_images = {e["image"] for e in entries}

    new_entries = []
    for path, split in split_frames:
        rel = str(path.relative_to(output_root))
        if rel not in existing_images:
            new_entries.append({"image": rel, "label": args.label, "split": split})

    entries.extend(new_entries)
    _save_manifest(manifest_path, entries)

    train_count = sum(1 for _, s in split_frames if s == "train")
    val_count = len(split_frames) - train_count
    print(f"Label '{args.label}': {len(split_frames)} frames ({train_count} train, {val_count} val)")
    print(f"Manifest updated: {manifest_path} ({len(entries)} total entries)")


if __name__ == "__main__":
    main()
