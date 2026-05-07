"""
Augmentation pipeline: expand train-split images to reduce overfitting.
"""

import argparse
import json
from pathlib import Path

import albumentations as A
import numpy as np
from PIL import Image

PIPELINE = A.Compose([
    A.RandomBrightnessContrast(brightness_limit=0.4, contrast_limit=0.4, p=0.8),
    A.HorizontalFlip(p=0.5),
    A.GaussianBlur(blur_limit=(3, 7), p=0.3),
    A.GaussNoise(var_limit=(10, 50), p=0.3),
    A.CoarseDropout(max_holes=4, max_height=60, max_width=60, p=0.4),
    A.RandomShadow(p=0.3),
    A.HueSaturationValue(p=0.2),
])


def _augment_image(src: Path, dst: Path) -> None:
    img = np.array(Image.open(src).convert("RGB"))
    augmented = PIPELINE(image=img)["image"]
    Image.fromarray(augmented).save(dst, format="JPEG", quality=90)


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment training frames")
    parser.add_argument("--manifest", default="./dataset/manifest.json")
    parser.add_argument("--factor", type=int, default=3, help="Augmented copies per original")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    dataset_root = manifest_path.parent
    entries: list[dict] = json.loads(manifest_path.read_text())

    train_entries = [e for e in entries if e["split"] == "train"]
    new_entries: list[dict] = []
    existing_images = {e["image"] for e in entries}

    for entry in train_entries:
        src = dataset_root / entry["image"]
        if not src.exists():
            print(f"Warning: {src} not found, skipping")
            continue
        for n in range(1, args.factor + 1):
            stem = src.stem
            aug_name = f"{stem}_aug_{n}.jpg"
            dst = src.parent / aug_name
            rel = str(dst.relative_to(dataset_root))
            if rel in existing_images:
                continue
            _augment_image(src, dst)
            new_entries.append({"image": rel, "label": entry["label"], "split": "train"})
            existing_images.add(rel)

    entries.extend(new_entries)
    manifest_path.write_text(json.dumps(entries, indent=2))

    label_counts: dict[str, int] = {}
    for e in new_entries:
        label_counts[e["label"]] = label_counts.get(e["label"], 0) + 1
    print(f"Added {len(new_entries)} augmented frames: {label_counts}")
    print(f"Manifest: {manifest_path} ({len(entries)} total entries)")


if __name__ == "__main__":
    main()
