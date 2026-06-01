#!/usr/bin/env python3
"""
Unsloth Fine-Tuning Scaffold for PMOVES.AI

Trains LoRA adapters on local models for agent-specific distillation.
Designed for DGX Spark (128GB unified memory) and 5090 (32GB) nodes.

Usage:
    python pmoves/tools/unsloth_finetune.py --model unsloth/gemma-4-31B-it \
        --dataset DARKXSIDE/pmoves-agent-traces --output pmoves-gemma4-lora

Make target:
    make -C pmoves unsloth-finetune MODEL=unsloth/gemma-4-31B-it DATASET=DARKXSIDE/pmoves-agent-traces
"""

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))


def main():
    parser = argparse.ArgumentParser(description="PMOVES Unsloth LoRA Fine-Tuning")
    parser.add_argument("--model", required=True, help="HF model ID (e.g. unsloth/gemma-4-31B-it)")
    parser.add_argument("--dataset", required=True, help="HF dataset ID or local JSONL path")
    parser.add_argument("--output", default="pmoves-lora-output", help="Output adapter name")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-seq-length", type=int, default=8192)
    parser.add_argument("--rank", type=int, default=16, help="LoRA rank")
    parser.add_argument("--dry-run", action="store_true", help="Print config without training")
    args = parser.parse_args()

    try:
        from unsloth import FastLanguageModel
        from transformers import TrainingArguments
        from trl import SFTTrainer
    except ImportError as e:
        print(f"ERROR: Unsloth not installed. Run: uv pip install unsloth")
        sys.exit(1)

    print(f"=== PMOVES Unsloth Fine-Tuning ===")
    print(f"Model: {args.model}")
    print(f"Dataset: {args.dataset}")
    print(f"Output: {args.output}")
    print(f"Rank: {args.rank} | Epochs: {args.epochs} | Batch: {args.batch_size}")

    if args.dry_run:
        print("DRY RUN — config validated, skipping training.")
        return

    # Load model with Unsloth 4-bit quantization
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq_length,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )

    # Add LoRA adapters
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.rank,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=args.rank * 2,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # Training arguments optimized for PMOVES agent traces
    training_args = TrainingArguments(
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=60,
        learning_rate=2e-4,
        fp16=not FastLanguageModel.is_bfloat16_supported(),
        bf16=FastLanguageModel.is_bfloat16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir=args.output,
        report_to="none",
    )

    # TODO: Load dataset from HF Hub or local JSONL
    # trainer = SFTTrainer(
    #     model=model,
    #     tokenizer=tokenizer,
    #     train_dataset=dataset,
    #     dataset_text_field="text",
    #     max_seq_length=args.max_seq_length,
    #     args=training_args,
    # )
    # trainer.train()

    print(f"\nTODO: Wire dataset loading for {args.dataset}")
    print(f"Adapter will be saved to: {args.output}")
    print(f"Next: huggingface-cli upload {args.output}")


if __name__ == "__main__":
    main()
