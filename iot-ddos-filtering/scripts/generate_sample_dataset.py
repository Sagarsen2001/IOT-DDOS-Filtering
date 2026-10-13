"""
scripts/generate_sample_dataset.py
====================================
Convenience script to generate and save the synthetic IoT traffic dataset.

Usage
-----
    python scripts/generate_sample_dataset.py
    python scripts/generate_sample_dataset.py --size 10000 --seed 42
"""

import argparse
import sys
import os

# Make sure the project root is on the path when running as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
config.configure_logging()

from ml.dataset import generate_dataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic IoT traffic dataset")
    parser.add_argument("--size", type=int, default=config.DATASET_SIZE,
                        help=f"Number of flow records (default: {config.DATASET_SIZE})")
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED,
                        help=f"Random seed (default: {config.RANDOM_SEED})")
    parser.add_argument("--output", default=config.DATASET_PATH,
                        help=f"Output CSV path (default: {config.DATASET_PATH})")
    args = parser.parse_args()

    df = generate_dataset(n_samples=args.size, output_path=args.output, seed=args.seed)
    print(f"\nDataset generated: {len(df)} rows")
    print(f"Label distribution:\n{df['label'].value_counts().rename({0:'NORMAL',1:'DDOS'}).to_string()}")
    print(f"Saved to: {args.output}")
