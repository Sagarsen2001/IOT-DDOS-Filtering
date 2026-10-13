"""
network/mininet_topology.py
============================
Mininet topology definition for the IoT lab network.

Topology
--------
    h1..h5  (IoT sensor nodes)  ─┐
    h6      (attacker node)      ├── s1 (OVS) ── controller (Ryu)
    h7      (server / gateway)  ─┘

Usage (on Ubuntu with Mininet installed)
----------------------------------------
    sudo python network/mininet_topology.py

DEMO MODE
---------
If Mininet is not available, this module logs a warning and returns
without raising an exception so the rest of the system still starts.
"""

import logging
import shutil

logger = logging.getLogger(__name__)


def is_mininet_available() -> bool:
    """Return True if the mn binary is on PATH."""
    return shutil.which("mn") is not None


def start_topology(controller_ip: str = "127.0.0.1", controller_port: int = 6653):
    """
    Build and start the Mininet IoT topology.

    Must be called with root privileges (sudo).
    Returns the Mininet net object, or None in DEMO MODE.
    """
    if not is_mininet_available():
        logger.warning(
            "Mininet not found — topology will not be started. "
            "Running in DEMO MODE without real network emulation."
        )
        return None

    try:
        from mininet.net import Mininet
        from mininet.node import RemoteController, OVSSwitch
        from mininet.topo import Topo
        from mininet.log import setLogLevel

        setLogLevel("info")

        class IoTTopo(Topo):
            def build(self):
                # IoT sensor hosts
                sensors = [self.addHost(f"h{i}", ip=f"10.0.0.{i}/24") for i in range(1, 6)]
                # Attacker host (used for DDoS simulation only inside the lab)
                attacker = self.addHost("h6", ip="10.0.0.6/24")
                # Gateway / server
                server = self.addHost("h7", ip="192.168.1.1/24")
                # OVS switch
                switch = self.addSwitch("s1", cls=OVSSwitch, failMode="standalone")

                for h in sensors + [attacker, server]:
                    self.addLink(h, switch)

        topo = IoTTopo()
        net = Mininet(
            topo=topo,
            controller=lambda name: RemoteController(
                name, ip=controller_ip, port=controller_port
            ),
            switch=OVSSwitch,
        )
        net.start()
        logger.info("Mininet topology started (controller=%s:%d)", controller_ip, controller_port)
        return net

    except ImportError:
        logger.error(
            "Mininet Python bindings not installed. "
            "Install with: sudo apt install mininet"
        )
        return None
    except Exception as exc:
        logger.error("Failed to start Mininet topology: %s", exc)
        return None


def stop_topology(net) -> None:
    """Cleanly stop the Mininet network."""
    if net is None:
        return
    try:
        net.stop()
        logger.info("Mininet topology stopped")
    except Exception as exc:
        logger.error("Error stopping Mininet: %s", exc)
