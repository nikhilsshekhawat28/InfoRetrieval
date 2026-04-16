"""
Evaluate fine-tuned models.

Usage:
    python evaluate.py --task summarization --model_path ./output/t5_finetuned
    python evaluate.py --task captioning --model_path ./output/blip_finetuned/best
"""

import argparse
import torch
import numpy as np
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate fine-tuned models")
    parser.add_argument("--task", type=str, required=True, choices=["summarization", "captioning"])
    parser.add_argument("--model_path", type=str, required=True)
    parser.add_argument("--dataset", type=str, default=None)
    parser.add_argument("--max_samples", type=int, default=500)
    parser.add_argument("--batch_size", type=int, default=32)
    return parser.parse_args()


def evaluate_summarization(args):
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    from datasets import load_dataset
    import evaluate

    print(f"Loading model from {args.model_path}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_path)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()

    dataset_name = args.dataset or "xsum"
    if dataset_name == "xsum":
        dataset = load_dataset("xsum", split="test")
        text_col, summary_col = "document", "summary"
    else:
        dataset = load_dataset("cnn_dailymail", "3.0.0", split="test")
        text_col, summary_col = "article", "highlights"

    dataset = dataset.select(range(min(args.max_samples, len(dataset))))
    print(f"Evaluating on {len(dataset)} samples")

    rouge = evaluate.load("rouge")
    predictions = []
    references = []

    for i in range(0, len(dataset), args.batch_size):
        batch = dataset[i : i + args.batch_size]
        inputs = tokenizer(
            [f"summarize: {t}" for t in batch[text_col]],
            max_length=512, truncation=True, padding=True, return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=128, num_beams=4)

        preds = tokenizer.batch_decode(output_ids, skip_special_tokens=True)
        predictions.extend(preds)
        references.extend(batch[summary_col])

        if (i // args.batch_size + 1) % 10 == 0:
            print(f"  Processed {i + len(preds)}/{len(dataset)}")

    results = rouge.compute(predictions=predictions, references=references, use_stemmer=True)
    print("\n" + "=" * 40)
    print("ROUGE Scores:")
    for k, v in results.items():
        print(f"  {k}: {v:.4f}")
    print("=" * 40)


def evaluate_captioning(args):
    from transformers import BlipProcessor, BlipForConditionalGeneration
    from peft import PeftModel
    from datasets import load_dataset
    from nltk.translate.bleu_score import corpus_bleu
    import evaluate

    print(f"Loading BLIP model from {args.model_path}")
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")

    model_path = Path(args.model_path)
    if (model_path / "adapter_config.json").exists():
        base_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        model = PeftModel.from_pretrained(base_model, str(model_path))
    else:
        model = BlipForConditionalGeneration.from_pretrained(str(model_path))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()

    dataset = load_dataset("nlphuji/flickr_1k_test_image_text_retrieval", split="test")
    dataset = dataset.select(range(min(args.max_samples, len(dataset))))
    print(f"Evaluating on {len(dataset)} samples")

    rouge = evaluate.load("rouge")
    predictions = []
    references = []

    for i, item in enumerate(dataset):
        image = item["image"].convert("RGB")
        inputs = processor(images=image, return_tensors="pt").to(device)

        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=100)

        caption = processor.decode(output_ids[0], skip_special_tokens=True)
        predictions.append(caption)

        ref = item["caption"] if isinstance(item["caption"], str) else item["caption"][0]
        references.append(ref)

        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(dataset)}")

    # BLEU
    ref_tokens = [[r.split()] for r in references]
    pred_tokens = [p.split() for p in predictions]
    bleu = corpus_bleu(ref_tokens, pred_tokens)

    # ROUGE-L
    rouge_results = rouge.compute(predictions=predictions, references=references)

    print("\n" + "=" * 40)
    print(f"BLEU Score:    {bleu:.4f}")
    print(f"ROUGE-L Score: {rouge_results['rougeL']:.4f}")
    print("=" * 40)


def main():
    args = parse_args()
    if args.task == "summarization":
        evaluate_summarization(args)
    else:
        evaluate_captioning(args)


if __name__ == "__main__":
    main()
