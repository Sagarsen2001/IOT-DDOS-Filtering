"""
ryu/ddos_controller.py
=======================
Ryu OpenFlow controller for the IoT DDoS filtering project.

This file contains TWO components:

1.  RyuDDoSController (class)
    --------------------------
    A Ryu application class that runs inside the Ryu framework process.
    It handles OpenFlow events from OVS and exposes a REST API for the
    Flask backend to request blocking/unblocking of source IPs.

    Run with:
        ryu-manager ryu/ddos_controller.py --observe-links

2.  RyuClient (class)
    ------------------
    A lightweight REST client used by the Flask backend to communicate
    with the running Ryu controller over its built-in REST API.
    This does NOT require Ryu to be imported — it uses only `requests`.

DEMO MODE
---------
When DEMO_MODE is True or Ryu is unreachable, RyuClient returns
simulated success responses clearly marked with "simulated": True.
"""

import logging
from typing import Any, Dict, List, Optional

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Part 1: Ryu Application (requires ryu to be installed and run separately)
# ---------------------------------------------------------------------------

RYU_APP_AVAILABLE = False

try:
    from ryu.base import app_manager
    from ryu.controller import ofp_event
    from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
    from ryu.lib.packet import ethernet, ipv4, packet
    from ryu.ofproto import ofproto_v1_3

    RYU_APP_AVAILABLE = True

    class RyuDDoSController(app_manager.RyuApp):
        """
        OpenFlow 1.3 controller for DDoS mitigation in the IoT lab.

        Features
        --------
        - Installs a default table-miss flow to send unknown packets to controller.
        - Learns MAC→port mappings for basic L2 forwarding.
        - Accepts block/unblock commands from the Flask backend via Ryu REST API.
        - Installs DROP rules for blocked source IPs with configurable timeouts.
        """

        OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # mac_to_port[dpid][mac] = port
            self.mac_to_port: Dict[int, Dict[str, int]] = {}
            # Track blocked IPs per datapath: blocked_ips[dpid] = {ip: cookie}
            self.blocked_ips: Dict[int, Dict[str, int]] = {}
            self._cookie_counter = 1000

        @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
        def switch_features_handler(self, ev):
            """Install table-miss flow on switch connect."""
            datapath = ev.msg.datapath
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser

            # Table-miss: send to controller
            match = parser.OFPMatch()
            actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
            self._add_flow(datapath, 0, match, actions)
            logger.info("Switch %016x connected — table-miss flow installed", datapath.id)

        @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
        def packet_in_handler(self, ev):
            """Handle packet-in: learn MAC and forward or flood."""
            msg = ev.msg
            datapath = msg.datapath
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            in_port = msg.match["in_port"]

            pkt = packet.Packet(msg.data)
            eth = pkt.get_protocol(ethernet.ethernet)
            if eth is None:
                return

            dpid = datapath.id
            self.mac_to_port.setdefault(dpid, {})
            self.mac_to_port[dpid][eth.src] = in_port

            out_port = self.mac_to_port[dpid].get(eth.dst, ofproto.OFPP_FLOOD)
            actions = [parser.OFPActionOutput(out_port)]

            if out_port != ofproto.OFPP_FLOOD:
                match = parser.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_src=eth.src)
                self._add_flow(datapath, 10, match, actions)

            data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
            out = parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=data,
            )
            datapath.send_msg(out)

        def block_source_ip(self, datapath, source_ip: str, idle_timeout: int = 300) -> bool:
            """Install a DROP rule for source_ip on the given datapath."""
            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto

            cookie = self._cookie_counter
            self._cookie_counter += 1

            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=source_ip)
            actions = []  # Empty actions = DROP
            self._add_flow(
                datapath, priority=200, match=match, actions=actions,
                idle_timeout=idle_timeout, cookie=cookie,
            )

            self.blocked_ips.setdefault(datapath.id, {})[source_ip] = cookie
            logger.warning("SECURITY: Blocking src=%s on dpid=%016x (cookie=%d)",
                           source_ip, datapath.id, cookie)
            return True

        def _add_flow(self, datapath, priority, match, actions,
                      idle_timeout=0, hard_timeout=0, cookie=0):
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser

            inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
            mod = parser.OFPFlowMod(
                datapath=datapath,
                cookie=cookie,
                priority=priority,
                match=match,
                instructions=inst,
                idle_timeout=idle_timeout,
                hard_timeout=hard_timeout,
            )
            datapath.send_msg(mod)

except ImportError:
    logger.info(
        "Ryu framework not installed — RyuDDoSController unavailable. "
        "Use RyuClient for REST-based communication."
    )


# ---------------------------------------------------------------------------
# Part 2: REST Client (no Ryu dependency — uses `requests`)
# ---------------------------------------------------------------------------

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests library not installed — RyuClient will use demo mode")


class RyuClient:
    """
    Client for communicating with the Ryu REST API from the Flask backend.

    Ryu's built-in REST API endpoint for flow management:
        POST /stats/flowentry/add
        DELETE /stats/flowentry/delete

    In DEMO MODE or when Ryu is unreachable, all operations are simulated.
    """

    def __init__(
        self,
        host: str = config.RYU_HOST,
        port: int = config.RYU_PORT,
        demo_mode: bool = config.DEMO_MODE,
        timeout: int = 5,
    ) -> None:
        self._base_url = f"http://{host}:{port}"
        self._demo_mode = demo_mode
        self._timeout = timeout
        self._blocked: Dict[str, str] = {}  # source_ip → rule_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_reachable(self) -> bool:
        """Return True if the Ryu REST API responds."""
        if not REQUESTS_AVAILABLE:
            return False
        try:
            resp = _requests.get(f"{self._base_url}/stats/switches", timeout=self._timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def block_source_ip(
        self,
        source_ip: str,
        datapath_id: int = 1,
        priority: int = 200,
        idle_timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Request Ryu to install a DROP rule for source_ip.

        Returns a result dict with success, simulated, action, source_ip, message.
        """
        rule_id = f"ryu-block-{source_ip.replace('.', '-')}"

        if self._demo_mode or not self._is_ryu_available():
            logger.info("[DEMO] Simulated Ryu block rule for src=%s", source_ip)
            self._blocked[source_ip] = rule_id
            return {
                "success": True,
                "simulated": True,
                "action": "BLOCK",
                "source_ip": source_ip,
                "rule_id": rule_id,
                "message": f"Simulated OVS blocking rule for {source_ip}",
            }

        # Real Ryu REST call
        flow_entry = {
            "dpid": datapath_id,
            "cookie": abs(hash(source_ip)) % (2**32),
            "cookie_mask": 0xFFFFFFFF,
            "priority": priority,
            "idle_timeout": idle_timeout,
            "hard_timeout": 0,
            "match": {"dl_type": 2048, "nw_src": source_ip},
            "actions": [],   # Empty = DROP
        }
        try:
            resp = _requests.post(
                f"{self._base_url}/stats/flowentry/add",
                json=flow_entry,
                timeout=self._timeout,
            )
            success = resp.status_code == 200
            if success:
                self._blocked[source_ip] = rule_id
                logger.warning("SECURITY: Ryu installed BLOCK rule for src=%s", source_ip)
            return {
                "success": success,
                "simulated": False,
                "action": "BLOCK",
                "source_ip": source_ip,
                "rule_id": rule_id,
                "message": resp.text[:200] if not success else f"Block rule installed for {source_ip}",
            }
        except Exception as exc:
            logger.error("Ryu block request failed: %s", exc)
            return {
                "success": False,
                "simulated": False,
                "action": "BLOCK",
                "source_ip": source_ip,
                "message": str(exc),
            }

    def unblock_source_ip(self, source_ip: str, datapath_id: int = 1) -> Dict[str, Any]:
        """Request Ryu to remove the DROP rule for source_ip."""
        if self._demo_mode or not self._is_ryu_available():
            logger.info("[DEMO] Simulated Ryu unblock for src=%s", source_ip)
            self._blocked.pop(source_ip, None)
            return {
                "success": True,
                "simulated": True,
                "action": "UNBLOCK",
                "source_ip": source_ip,
                "message": f"Simulated unblock for {source_ip}",
            }

        flow_entry = {
            "dpid": datapath_id,
            "match": {"dl_type": 2048, "nw_src": source_ip},
        }
        try:
            resp = _requests.delete(
                f"{self._base_url}/stats/flowentry/delete",
                json=flow_entry,
                timeout=self._timeout,
            )
            success = resp.status_code == 200
            if success:
                self._blocked.pop(source_ip, None)
            return {
                "success": success,
                "simulated": False,
                "action": "UNBLOCK",
                "source_ip": source_ip,
                "message": resp.text[:200] if not success else f"Block rule removed for {source_ip}",
            }
        except Exception as exc:
            logger.error("Ryu unblock request failed: %s", exc)
            return {"success": False, "action": "UNBLOCK", "source_ip": source_ip, "message": str(exc)}

    def list_blocked_sources(self) -> List[str]:
        """Return a list of currently blocked source IPs tracked by this client."""
        return list(self._blocked.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_ryu_available(self) -> bool:
        if not REQUESTS_AVAILABLE:
            return False
        try:
            resp = _requests.get(f"{self._base_url}/stats/switches", timeout=self._timeout)
            return resp.status_code == 200
        except Exception:
            return False
