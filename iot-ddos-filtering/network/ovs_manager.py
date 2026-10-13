"""
network/ovs_manager.py
=======================
Centralised interface to Open vSwitch (OVS) management commands.

All subprocess calls to `ovs-vsctl` and `ovs-ofctl` go through this module.
This prevents raw shell strings scattered across the codebase and ensures:
  - Commands are validated before execution.
  - stdout/stderr are captured.
  - Non-zero exit codes raise meaningful errors.
  - Failures are logged clearly.

DEMO MODE
---------
When DEMO_MODE is True or OVS is unavailable, all write operations
(add-flow, del-flow) are simulated and clearly flagged in the response.
"""

import logging
import shutil
import subprocess
from typing import Any, Dict, List, Optional

import config

logger = logging.getLogger(__name__)

# OVS priority for blocking rules (higher than default forwarding)
BLOCK_RULE_PRIORITY = 200


def _is_ovs_available() -> bool:
    """Return True if ovs-vsctl binary exists on PATH."""
    return shutil.which("ovs-vsctl") is not None


def _run(cmd: List[str], timeout: int = 10) -> Dict[str, Any]:
    """
    Execute an OVS command safely.

    Returns
    -------
    dict with keys: success, stdout, stderr, returncode.
    """
    logger.debug("OVS command: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning(
                "OVS command failed (rc=%d): %s\nSTDERR: %s",
                result.returncode, " ".join(cmd), result.stderr.strip(),
            )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        logger.error("OVS command timed out: %s", " ".join(cmd))
        return {"success": False, "stdout": "", "stderr": "timeout", "returncode": -1}
    except FileNotFoundError as exc:
        logger.error("OVS binary not found: %s", exc)
        return {"success": False, "stdout": "", "stderr": str(exc), "returncode": -1}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_ovs_available() -> bool:
    """Return True if OVS tools are present and the service is reachable."""
    if not _is_ovs_available():
        return False
    result = _run(["ovs-vsctl", "show"])
    return result["success"]


def list_switches() -> List[str]:
    """Return a list of OVS bridge/switch names."""
    result = _run(["ovs-vsctl", "list-br"])
    if not result["success"]:
        return []
    return [s.strip() for s in result["stdout"].splitlines() if s.strip()]


def get_switch_status(switch_name: str = config.OVS_SWITCH_NAME) -> Dict[str, Any]:
    """Return basic status info for a switch."""
    result = _run(["ovs-vsctl", "show"])
    return {
        "switch": switch_name,
        "available": result["success"],
        "raw": result.get("stdout", "")[:500],
    }


def list_flow_rules(switch_name: str = config.OVS_SWITCH_NAME) -> List[str]:
    """Dump current OpenFlow rules on the switch."""
    result = _run(["ovs-ofctl", "dump-flows", switch_name])
    if not result["success"]:
        return []
    return [line.strip() for line in result["stdout"].splitlines() if line.strip()]


def add_block_rule(
    source_ip: str,
    switch_name: str = config.OVS_SWITCH_NAME,
    demo_mode: bool = config.DEMO_MODE,
    priority: int = BLOCK_RULE_PRIORITY,
    idle_timeout: int = 300,
) -> Dict[str, Any]:
    """
    Install a DROP rule for a given source IP.

    In DEMO MODE: log the action and return a simulated success response.
    In REAL MODE: call `ovs-ofctl add-flow`.

    Parameters
    ----------
    source_ip    : The IP address to block.
    switch_name  : OVS bridge name.
    demo_mode    : True → simulate only.
    priority     : OpenFlow priority (default 200).
    idle_timeout : Seconds of inactivity before rule expires (default 300).

    Returns
    -------
    dict with success, simulated, action, source_ip, message.
    """
    rule_id = f"block-{source_ip.replace('.', '-')}"

    if demo_mode or not _is_ovs_available():
        logger.info(
            "[DEMO] Simulated OVS block rule for src=%s on switch=%s",
            source_ip, switch_name,
        )
        return {
            "success": True,
            "simulated": True,
            "action": "BLOCK",
            "source_ip": source_ip,
            "rule_id": rule_id,
            "message": f"Simulated OVS blocking rule installed for {source_ip}",
        }

    # Real OVS: install a flow that drops all packets from source_ip
    flow_spec = (
        f"priority={priority},"
        f"ip,nw_src={source_ip},"
        f"idle_timeout={idle_timeout},"
        f"actions=drop"
    )
    result = _run(["ovs-ofctl", "add-flow", switch_name, flow_spec])
    return {
        "success": result["success"],
        "simulated": False,
        "action": "BLOCK",
        "source_ip": source_ip,
        "rule_id": rule_id,
        "message": result["stderr"] if not result["success"] else f"Flow rule installed for {source_ip}",
    }


def remove_block_rule(
    source_ip: str,
    switch_name: str = config.OVS_SWITCH_NAME,
    demo_mode: bool = config.DEMO_MODE,
) -> Dict[str, Any]:
    """
    Remove an existing DROP rule for a source IP.

    In DEMO MODE: simulated.
    In REAL MODE: call `ovs-ofctl del-flows`.
    """
    if demo_mode or not _is_ovs_available():
        logger.info("[DEMO] Simulated OVS unblock for src=%s", source_ip)
        return {
            "success": True,
            "simulated": True,
            "action": "UNBLOCK",
            "source_ip": source_ip,
            "message": f"Simulated OVS unblock for {source_ip}",
        }

    flow_spec = f"ip,nw_src={source_ip}"
    result = _run(["ovs-ofctl", "del-flows", switch_name, flow_spec])
    return {
        "success": result["success"],
        "simulated": False,
        "action": "UNBLOCK",
        "source_ip": source_ip,
        "message": result["stderr"] if not result["success"] else f"Flow rule removed for {source_ip}",
    }
