# Dataset Preparation

## Overview

This directory holds labeled frames used to fine-tune Moondream2 for home
security classification. The dataset is built from your own family videos or
image collections — it never leaves your machine.

## Structure

```
dataset/
  known/
    <name>/        frame_0001.jpg, frame_0002.jpg ...
  unknown/
    stranger/      frames of unknown persons / empty house
  manifest.json   [{image, label, split}]
```

## Step 1 — Record source material

- **Known persons**: Record 2–5 minute videos per person in varied lighting,
  angles, and clothing. 100–300 extracted frames per person is a good target.
- **Unknown**: Record the empty doorway/entry or use stock footage of strangers.

## Step 2 — Extract frames

```bash
# From a video file (extracts 1 frame/second by default)
python dataset/prepare.py --source videos/edu.mp4 --label edu

# Custom fps
python dataset/prepare.py --source videos/edu.mp4 --label edu --fps 2

# From an image folder
python dataset/prepare.py --source photos/edu/ --label edu

# Unknown persons
python dataset/prepare.py --source videos/stranger.mp4 --label unknown
```

All frames are resized to 378×378 px (Moondream2 native input) and saved as
JPEG q90. The manifest is updated incrementally — run the command multiple times
to add more footage.

## Step 3 — Augment training data

```bash
# 3× augmented copies per original (default)
python dataset/augment.py

# 5× augmented copies
python dataset/augment.py --factor 5
```

Augmentation is applied to `train` split only. Augmented frames get `_aug_N`
suffix and are added to manifest.json automatically.

## manifest.json schema

```json
[
  { "image": "known/edu/frame_0001.jpg", "label": "edu", "split": "train" },
  { "image": "known/edu/frame_0042.jpg", "label": "edu", "split": "val" },
  { "image": "unknown/stranger/frame_0003.jpg", "label": "unknown", "split": "train" }
]
```

## Tips

- Aim for at least 80 train frames per known person before augmentation.
- Include night-mode / IR footage if your camera supports it.
- The `val` split should reflect real-world variance — don't put augmented
  copies in val.
- Never commit raw video files — `.gitignore` excludes `.mp4`, `.mov`, etc.
