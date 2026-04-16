"""
Fine-tune BLIP image captioning model on Flickr8k using LoRA (PEFT).
Run on HPC cluster with GPU (e.g., Nvidia H200).

Usage:
    python train_blip_flickr8k.py --epochs 5 --batch_size 128
"""

import argparse
import torch
from torch.utils.data import DataLoader, Dataset
from PIL import Image
from pathlib import Path
from transformers import BlipProcessor, BlipForConditionalGeneration
from peft import LoraConfig, get_peft_model
from datasets import load_dataset


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune BLIP on Flickr8k with LoRA")
    parser.add_argument("--output_dir", type=str, default="./output/blip_finetuned")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    return parser.parse_args()


class Flickr8kDataset(Dataset):
    def __init__(self, hf_dataset, processor):
        self.dataset = hf_dataset
        self.processor = processor

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        item = self.dataset[idx]
        image = item["image"].convert("RGB")
        # Use first caption if multiple exist
        caption = item["caption"] if isinstance(item["caption"], str) else item["caption"][0]

        encoding = self.processor(
            images=image,
            text=caption,
            padding="max_length",
            max_length=64,
            truncation=True,
            return_tensors="pt",
        )
        # Squeeze batch dimension
        return {k: v.squeeze(0) for k, v in encoding.items()}


def main():
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load processor and model
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

    # Apply LoRA
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["query", "value"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    model.to(device)

    # Load Flickr8k dataset
    print("Loading Flickr8k dataset...")
    dataset = load_dataset("nlphuji/flickr_1k_test_image_text_retrieval")

    # For full Flickr8k, you can also use a local dataset:
    # dataset = load_dataset("imagefolder", data_dir="path/to/flickr8k")

    # Split: 80% train, 10% val, 10% test
    full = dataset["test"]  # Flickr8k comes as test split
    split = full.train_test_split(test_size=0.2, seed=42)
    train_data = split["train"]
    val_test = split["test"].train_test_split(test_size=0.5, seed=42)
    val_data = val_test["train"]
    test_data = val_test["test"]

    print(f"Train: {len(train_data)}, Val: {len(val_data)}, Test: {len(test_data)}")

    # Create DataLoaders
    train_dataset = Flickr8kDataset(train_data, processor)
    val_dataset = Flickr8kDataset(val_data, processor)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=4)

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)

    # Training loop
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    best_val_loss = float("inf")

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0
        for batch_idx, batch in enumerate(train_loader):
            batch = {k: v.to(device) for k, v in batch.items()}

            outputs = model(**batch)
            loss = outputs.loss

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

            if (batch_idx + 1) % 10 == 0:
                print(f"  Epoch {epoch}, Batch {batch_idx+1}/{len(train_loader)}, Loss: {loss.item():.4f}")

        avg_train_loss = total_loss / len(train_loader)
        print(f"Epoch {epoch}/{args.epochs} - Average Train Loss: {avg_train_loss:.4f}")

        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                outputs = model(**batch)
                val_loss += outputs.loss.item()

        avg_val_loss = val_loss / len(val_loader)
        print(f"  Validation Loss: {avg_val_loss:.4f}")

        # Save checkpoint
        checkpoint_dir = output_dir / f"model-epoch-{epoch}"
        model.save_pretrained(str(checkpoint_dir))
        print(f"  Weights saved to {checkpoint_dir}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            model.save_pretrained(str(output_dir / "best"))
            print(f"  New best model saved!")

    # Save final model
    model.save_pretrained(str(output_dir / "final"))
    print(f"\nTraining complete. Best val loss: {best_val_loss:.4f}")
    print(f"Models saved to {output_dir}")


if __name__ == "__main__":
    main()
