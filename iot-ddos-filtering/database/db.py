"""
database/db.py
==============
SQLite connection management using thread-safe connection-per-request pattern.
"""

import sqlite3
import logging
import threading
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

# Thread-local storage so each thread gets its own connection
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """
    Return a thread-local SQLite connection, creating it if necessary.
    Row factory is set so rows behave like dicts.
    """
    if not hasattr(_local, "conn") or _local.conn is None:
        db_path = Path(config.DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")  # Better concurrent reads
        conn.execute("PRAGMA busy_timeout=30000;") # Wait up to 30s on concurrent writes
        conn.execute("PRAGMA foreign_keys=ON;")
        _local.conn = conn
        logger.debug("Opened new SQLite connection for thread %s", threading.current_thread().name)
    return _local.conn


def close_connection() -> None:
    """Close the thread-local connection if open."""
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def init_db() -> None:
    """
    Create all required tables if they do not already exist.
    Safe to call on every startup.
    """
    conn = get_connection()
    try:
        _create_tables(conn)
        conn.commit()
        seed_default_devices()
        logger.info("Database initialised at %s", config.DATABASE_PATH)
    except sqlite3.Error as exc:
        logger.error("Database initialisation failed: %s", exc)
        raise


def seed_default_devices() -> None:
    """Seed initial IoT devices if the table has no records."""
    default_devices = [
        ("sensor-thermostat-01", "10.0.0.1", "00:1B:44:11:3A:B7", "active"),
        ("camera-security-02",   "10.0.0.2", "00:1B:44:22:8C:19", "active"),
        ("smart-gateway-03",     "10.0.0.3", "00:1B:44:33:DE:44", "active"),
        ("lighting-ctrl-04",     "10.0.0.4", "00:1B:44:44:0F:7A", "active"),
        ("motion-sensor-05",     "10.0.0.5", "00:1B:44:55:2E:3C", "active"),
        ("iot-node-bot-06",      "10.0.0.6", "00:1B:44:66:9A:88", "active"),
    ]
    try:
        conn = get_connection()
        count = conn.execute("SELECT count(*) FROM devices").fetchone()[0]
        if count == 0:
            for dev_id, ip, mac, st in default_devices:
                conn.execute(
                    """
                    INSERT INTO devices (device_id, ip_address, mac_address, status, last_seen)
                    VALUES (?, ?, ?, ?, datetime('now'))
                    """,
                    (dev_id, ip, mac, st)
                )
            conn.commit()
            logger.info("Seeded %d default IoT devices into database", len(default_devices))
    except Exception as exc:
        logger.warning("Error seeding devices: %s", exc)


def _create_tables(conn: sqlite3.Connection) -> None:
    """Execute all CREATE TABLE IF NOT EXISTS statements."""
    conn.executescript("""
        -- IoT devices registered in the system
        CREATE TABLE IF NOT EXISTS devices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT    NOT NULL UNIQUE,
            ip_address  TEXT    NOT NULL,
            mac_address TEXT,
            status      TEXT    NOT NULL DEFAULT 'active',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            last_seen   TEXT
        );

        -- Captured / generated network flows
        CREATE TABLE IF NOT EXISTS traffic_flows (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT    NOT NULL DEFAULT (datetime('now')),
            source_ip        TEXT    NOT NULL,
            destination_ip   TEXT    NOT NULL,
            source_port      INTEGER,
            destination_port INTEGER,
            protocol         TEXT,
            duration         REAL,
            packet_count     INTEGER,
            byte_count       INTEGER,
            packet_rate      REAL,
            byte_rate        REAL,
            avg_packet_size  REAL,
            label            TEXT
        );

        -- ML predictions linked to flows
        CREATE TABLE IF NOT EXISTS predictions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            traffic_flow_id INTEGER REFERENCES traffic_flows(id),
            prediction     TEXT    NOT NULL,
            probability    REAL    NOT NULL,
            confidence     REAL    NOT NULL,
            predicted_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- Security alerts
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT,
            source_ip   TEXT    NOT NULL,
            alert_type  TEXT    NOT NULL,
            severity    TEXT    NOT NULL DEFAULT 'HIGH',
            message     TEXT,
            status      TEXT    NOT NULL DEFAULT 'open',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- Mitigation actions taken
        CREATE TABLE IF NOT EXISTS mitigation_actions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT,
            source_ip   TEXT    NOT NULL,
            action      TEXT    NOT NULL,
            rule_id     TEXT,
            reason      TEXT,
            success     INTEGER NOT NULL DEFAULT 1,
            simulated   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- Saved model evaluation metrics
        CREATE TABLE IF NOT EXISTS evaluation_metrics (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version   TEXT    NOT NULL,
            accuracy        REAL,
            precision_score REAL,
            recall_score    REAL,
            f1_score        REAL,
            fpr             REAL,
            tpr             REAL,
            recorded_at     TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- General system event log
        CREATE TABLE IF NOT EXISTS system_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT    NOT NULL,
            severity    TEXT    NOT NULL DEFAULT 'INFO',
            message     TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );
    """)
