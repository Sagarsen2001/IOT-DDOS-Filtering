"""
ml/dataset.py
=============
Synthetic IoT network-flow dataset generator.

PURPOSE
-------
Generates a reproducible CSV dataset of NORMAL and DDoS-like network flows
for training and testing the RandomForest classifier.

IMPORTANT
---------
This synthetic dataset is intended ONLY for prototyping and academic
demonstration. For a production system it should be replaced or augmented
with real packet-capture data processed through Zeek.

LABELS
------
  0 = NORMAL
  1 = DDOS

COLUMNS
-------
  src_ip, dst_ip, src_port, dst_port, protocol,
  duration, packet_count, byte_count,
  packet_rate, byte_rate, avg_packet_size, label
"""

import logging
import random
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

import config

logger = logging.getLogger(__name__)

# Fixed IoT lab subnets used during simulation
_IOT_IPS = [f"10.0.0.{i}" for i in range(1, 11)]
_SERVER_IPS = ["192.168.1.1", "192.168.1.2", "8.8.8.8"]
_PROTOCOLS = ["TCP", "UDP", "ICMP"]
_MQTT_PORT = 1883


def _normal_flow(rng: np.random.Generator) -> dict:
    """Generate one realistic NORMAL IoT sensor flow."""
    duration = rng.uniform(1.0, 60.0)                  # seconds
    packet_count = int(rng.uniform(5, 200))
    avg_size = rng.uniform(64, 512)                    # bytes
    byte_count = int(packet_count * avg_size)

    return {
        "src_ip": rng.choice(_IOT_IPS),
        "dst_ip": rng.choice(_SERVER_IPS),
        "src_port": int(rng.integers(1024, 65535)),
        "dst_port": int(rng.choice([_MQTT_PORT, 80, 443, 53])),
        "protocol": rng.choice(_PROTOCOLS),
        "duration": round(float(duration), 4),
        "packet_count": packet_count,
        "byte_count": byte_count,
        "packet_rate": round(packet_count / max(duration, 0.001), 4),
        "byte_rate": round(byte_count / max(duration, 0.001), 4),
        "avg_packet_size": round(avg_size, 4),
        "label": 0,
    }


def _ddos_flow(rng: np.random.Generator) -> dict:
    """Generate one DDOS-like high-rate flow (strictly within lab subnets)."""
    duration = rng.uniform(0.1, 5.0)                   # short burst
    packet_count = int(rng.uniform(500, 5000))
    avg_size = rng.uniform(64, 128)                    # flood packets are small
    byte_count = int(packet_count * avg_size)

    return {
        "src_ip": rng.choice(_IOT_IPS),
        "dst_ip": rng.choice(_SERVER_IPS),
        "src_port": int(rng.integers(1024, 65535)),
        "dst_port": int(rng.choice([80, 443, 53, _MQTT_PORT])),
        "protocol": rng.choice(["TCP", "UDP", "ICMP"]),
        "duration": round(float(duration), 4),
        "packet_count": packet_count,
        "byte_count": byte_count,
        "packet_rate": round(packet_count / max(duration, 0.001), 4),
        "byte_rate": round(byte_count / max(duration, 0.001), 4),
        "avg_packet_size": round(avg_size, 4),
        "label": 1,
    }


def generate_dataset(
    n_samples: int = config.DATASET_SIZE,
    output_path: Optional[str] = None,
    seed: int = config.RANDOM_SEED,
    ddos_ratio: float = 0.35,
) -> pd.DataFrame:
    """
    Generate a synthetic balanced dataset.

    Parameters
    ----------
    n_samples   : Total number of flow records.
    output_path : CSV path to save to; None = use config.DATASET_PATH.
    seed        : Random seed for reproducibility.
    ddos_ratio  : Fraction of DDoS records (default 35 %).

    Returns
    -------
    pd.DataFrame with labelled flow records.
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)

    n_ddos = int(n_samples * ddos_ratio)
    n_normal = n_samples - n_ddos

    logger.info("Generating %d NORMAL + %d DDOS synthetic flows …", n_normal, n_ddos)

    records = (
        [_normal_flow(rng) for _ in range(n_normal)]
        + [_ddos_flow(rng) for _ in range(n_ddos)]
    )

    df = pd.DataFrame(records)
    # Shuffle so classes are not all at the end
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    save_path = output_path or config.DATASET_PATH
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(save_path, index=False)
    logger.info("Dataset saved to %s (%d rows)", save_path, len(df))

    return df


def load_dataset(path: Optional[str] = None) -> pd.DataFrame:
    """Load the dataset CSV.  Raises FileNotFoundError if not found."""
    csv_path = path or config.DATASET_PATH
    if not Path(csv_path).exists():
        raise FileNotFoundError(
            f"Dataset not found at '{csv_path}'. "
            "Run scripts/generate_sample_dataset.py first."
        )
    df = pd.read_csv(csv_path)
    logger.info("Loaded dataset: %d rows from %s", len(df), csv_path)
    return df
