"""
Fine-tune T5-base on XSum / CNN-DailyMail for summarization.
Run on HPC cluster with GPU (e.g., Nvidia H200).

Usage:
    python train_t5_xsum.py --dataset xsum --epochs 3 --batch_size 16
"""

import argparse
import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    DataCollatorForSeq2Seq,
)
import evaluate
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune T5 for summarization")
    parser.add_argument("--model_name", type=str, default="google/flan-t5-base")
    parser.add_argument("--dataset", type=str, default="xsum", choices=["xsum", "cnn_dailymail"])
    parser.add_argument("--output_dir", type=str, default="./output/t5_finetuned")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--max_input_length", type=int, default=512)
    parser.add_argument("--max_target_length", type=int, default=128)
    parser.add_argument("--max_train_samples", type=int, default=None)
    parser.add_argument("--max_eval_samples", type=int, default=1000)
    return parser.parse_args()


def main():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_name)

    # Load dataset
    if args.dataset == "xsum":
        dataset = load_dataset("xsum")
        text_col, summary_col = "document", "summary"
    else:
        dataset = load_dataset("cnn_dailymail", "3.0.0")
        text_col, summary_col = "article", "highlights"

    # Subsample if needed
    train_dataset = dataset["train"]
    eval_dataset = dataset["validation"]
    if args.max_train_samples:
        train_dataset = train_dataset.select(range(min(args.max_train_samples, len(train_dataset))))
    if args.max_eval_samples:
        eval_dataset = eval_dataset.select(range(min(args.max_eval_samples, len(eval_dataset))))

    print(f"Train: {len(train_dataset)} samples, Eval: {len(eval_dataset)} samples")

    # Tokenize
    def preprocess(examples):
        inputs = [f"summarize: {doc}" for doc in examples[text_col]]
        model_inputs = tokenizer(
            inputs, max_length=args.max_input_length, truncation=True, padding="max_length"
        )
        labels = tokenizer(
            examples[summary_col], max_length=args.max_target_length, truncation=True, padding="max_length"
        )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    train_dataset = train_dataset.map(preprocess, batched=True, remove_columns=train_dataset.column_names)
    eval_dataset = eval_dataset.map(preprocess, batched=True, remove_columns=eval_dataset.column_names)

    # Metrics
    rouge = evaluate.load("rouge")

    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        predictions = np.where(predictions != -100, predictions, tokenizer.pad_token_id)
        decoded_preds = tokenizer.batch_decode(predictions, skip_special_tokens=True)
        labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
        decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)
        result = rouge.compute(predictions=decoded_preds, references=decoded_labels, use_stemmer=True)
        return {k: round(v * 100, 4) for k, v in result.items()}

    # Training arguments
    training_args = Seq2SeqTrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_steps=500,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=100,
        predict_with_generate=True,
        generation_max_length=args.max_target_length,
        fp16=torch.cuda.is_available(),
        load_best_model_at_end=True,
        metric_for_best_model="rouge1",
        report_to="none",
    )

    # Data collator
    data_collator = DataCollatorForSeq2Seq(tokenizer, model=model, padding=True)

    # Trainer
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    # Train
    print("Starting training...")
    trainer.train()

    # Save
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"Model saved to {args.output_dir}")

    # Final evaluation
    results = trainer.evaluate()
    print("\nFinal Evaluation:")
    for k, v in results.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
