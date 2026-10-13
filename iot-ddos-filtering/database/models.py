"""
database/models.py
==================
Plain Python dataclasses mirroring the DB tables.
Used for type-safe data passing between layers.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Device:
    device_id: str
    ip_address: str
    mac_address: Optional[str] = None
    status: str = "active"
    id: Optional[int] = None
    created_at: Optional[str] = None
    last_seen: Optional[str] = None


@dataclass
class TrafficFlow:
    source_ip: str
    destination_ip: str
    source_port: Optional[int] = None
    destination_port: Optional[int] = None
    protocol: Optional[str] = None
    duration: Optional[float] = None
    packet_count: Optional[int] = None
    byte_count: Optional[int] = None
    packet_rate: Optional[float] = None
    byte_rate: Optional[float] = None
    avg_packet_size: Optional[float] = None
    label: Optional[str] = None
    timestamp: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Prediction:
    traffic_flow_id: Optional[int]
    prediction: str
    probability: float
    confidence: float
    predicted_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Alert:
    source_ip: str
    alert_type: str
    device_id: Optional[str] = None
    severity: str = "HIGH"
    message: Optional[str] = None
    status: str = "open"
    created_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class MitigationAction:
    source_ip: str
    action: str
    device_id: Optional[str] = None
    rule_id: Optional[str] = None
    reason: Optional[str] = None
    success: bool = True
    simulated: bool = True
    created_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class EvaluationMetrics:
    model_version: str
    accuracy: Optional[float] = None
    precision_score: Optional[float] = None
    recall_score: Optional[float] = None
    f1_score: Optional[float] = None
    fpr: Optional[float] = None
    tpr: Optional[float] = None
    recorded_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class SystemEvent:
    event_type: str
    message: Optional[str] = None
    severity: str = "INFO"
    created_at: Optional[str] = None
    id: Optional[int] = None
