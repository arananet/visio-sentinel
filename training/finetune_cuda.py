"""
QLoRA fine-tuning on NVIDIA GPU via bitsandbytes + peft + transformers.
"""

import base64
import logging
from io import BytesIO
from pathlib import Path

import torch
from PIL import Image
from peft import LoraConfig, get_peft_model
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoProcessor,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)

logger = logging.getLogger(__name__)


class MoondreamQADataset(Dataset):
    def __init__(self, samples: list[dict], image_root: str, processor) -> None:
        self.samples = samples
        self.image_root = Path(image_root)
        self.processor = processor

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict:
        sample = self.samples[idx]
        img = Image.open(self.image_root / sample["image"]).convert("RGB")
        text = f"Question: {sample['question']}\nAnswer: {sample['answer']}"
        encoded = self.processor(images=img, text=text, return_tensors="pt")
        return {k: v.squeeze(0) for k, v in encoded.items()}


def run(cfg: dict, samples: list[dict], adapter_path: str, image_root: str) -> None:
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )

    model_id = cfg["model"]["base_id"]
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    lora_cfg = cfg["lora"]
    lora_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["alpha"],
        lora_dropout=lora_cfg["dropout"],
        target_modules=lora_cfg["target_modules"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    dataset = MoondreamQADataset(samples, image_root, processor)

    t = cfg["training"]
    training_args = TrainingArguments(
        output_dir=adapter_path,
        num_train_epochs=t["epochs"],
        per_device_train_batch_size=t["batch_size"],
        gradient_accumulation_steps=t["gradient_accumulation_steps"],
        learning_rate=t["learning_rate"],
        fp16=t["fp16"],
        save_steps=t["save_steps"],
        logging_steps=t["logging_steps"],
        warmup_ratio=t["warmup_ratio"],
        dataloader_pin_memory=False,
    )

    trainer = Trainer(model=model, args=training_args, train_dataset=dataset)
    trainer.train()
    model.save_pretrained(adapter_path)
    logger.info("Adapter saved to %s", adapter_path)


if __name__ == "__main__":
    import yaml
    import json

    cfg = yaml.safe_load(open("training/config.yaml"))
    manifest = json.loads(open(cfg["dataset"]["manifest"]).read())
    train_entries = [e for e in manifest if e["split"] == "train"]
    from training.finetune import build_qa_dataset
    samples = build_qa_dataset(train_entries, cfg["qa_templates"])
    run(cfg, samples, str(Path(cfg["model"]["output_dir"]) / "lora-adapter"), cfg["dataset"]["image_root"])
