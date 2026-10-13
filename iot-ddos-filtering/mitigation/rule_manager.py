"""
mitigation/rule_manager.py
===========================
Single interface for installing and removing blocking rules,
coordinating between the Ryu client and the OVS manager.

Both are tried when in REAL mode; the OVS manager serves as a
fallback when the Ryu REST API is unreachable.
"""

import logging
from typing import Any, Dict

import config
from network.ovs_manager import add_block_rule, remove_block_rule
from ryu.ddos_controller import RyuClient

logger = logging.getLogger(__name__)

# Module-level Ryu client (shared across requests via the decision engine)
_ryu_client: RyuClient = RyuClient()


def install_block_rule(source_ip: str) -> Dict[str, Any]:
    """
    Block a source IP by contacting Ryu first, then OVS as fallback.

    Returns the result dict from whichever backend succeeded.
    """
    logger.info("Installing block rule for src=%s", source_ip)

    # Primary path: Ryu REST API
    result = _ryu_client.block_source_ip(source_ip)
    if result.get("success"):
        return result

    # Fallback: direct OVS command
    logger.warning("Ryu block failed — trying direct OVS rule for src=%s", source_ip)
    return add_block_rule(source_ip, demo_mode=config.DEMO_MODE)


def remove_block_rule_for_ip(source_ip: str) -> Dict[str, Any]:
    """Remove a blocking rule for source_ip via Ryu or OVS."""
    logger.info("Removing block rule for src=%s", source_ip)

    result = _ryu_client.unblock_source_ip(source_ip)
    if result.get("success"):
        return result

    return remove_block_rule(source_ip, demo_mode=config.DEMO_MODE)


def list_blocked_ips() -> list:
    """Return currently tracked blocked IPs."""
    return _ryu_client.list_blocked_sources()
