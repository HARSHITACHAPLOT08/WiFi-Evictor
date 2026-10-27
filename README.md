<div align="center">

```
  ███████╗██╗   ██╗██╗ ██████╗████████╗ ██████╗ ██████╗ 
  ██╔════╝██║   ██║██║██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗
  █████╗  ██║   ██║██║██║        ██║   ██║   ██║██████╔╝ 
  ██╔══╝  ╚██╗ ██╔╝██║██║        ██║   ██║   ██║██╔══██╗ 
  ███████╗ ╚████╔╝ ██║╚██████╗   ██║   ╚██████╔╝██║  ██║ 
  ╚══════╝  ╚═══╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝ 
```

# The Evictor — WiFi Deauthentication Toolkit

**A sleek, surgical aircrack-ng wrapper for ethical WiFi penetration testing**

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
![Shell](https://img.shields.io/badge/Shell-Bash-green?style=flat-square&logo=gnu-bash)
![Platform](https://img.shields.io/badge/Platform-Kali%20Linux-purple?style=flat-square&logo=linux)
![License](https://img.shields.io/badge/License-MIT-orange?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

> ⚠️ **For authorized penetration testing and educational use only.**  
> Using this tool against networks you do not own or have written permission to test is **illegal**.

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎯 **Surgical Kick** | Evict a single client by MAC — leaves all others connected |
| 💥 **Broadcast Mode** | Disconnect ALL clients simultaneously with one command |
| 🗺️ **Dynamic BSSID Resolution** | Target by SSID name — auto-resolves the BSSID anywhere you go |
| 📋 **Client Enumeration** | Scan and list every device connected to a target AP |
| 🔄 **Monitor Mode Manager** | Auto-enables/disables monitor mode via `airmon-ng` |
| 📝 **Session Logging** | Every action timestamped and saved to `evictor.log` |
| ⚡ **Zero Dependencies** | Pure Python stdlib + aircrack-ng suite |

---

## 📁 Project Structure

```
Wifi-Evictor/
├── evictor.py      ← Core Python engine (all logic)
├── kick            ← Bash shorthand: ./kick <MAC> [options]
├── broadcast       ← Bash shorthand: ./broadcast [options]
├── demo.html       ← Interactive browser demo (no Linux required)
└── README.md
```

---

## ⚙️ Prerequisites

### 1. OS Requirement
Kali Linux, Parrot OS, or any Debian-based distro.

### 2. Install aircrack-ng
```bash
sudo apt update && sudo apt install -y aircrack-ng
```

### 3. Make scripts executable
```bash
chmod +x kick broadcast
```

### 4. Find your wireless interface
```bash
iwconfig    # Look for wlan0, wlan1, etc.
```

---

## 🚀 Quick Start

```bash
# Clone the repo
git clone https://github.com/HARSHITACHAPLOT08/WiFi-Evictor.git
cd WiFi-Evictor
chmod +x kick broadcast

# Scan for nearby APs and clients
sudo python3 evictor.py --ssid "YourNetwork" scan

# Surgical kick — evict a single device
./kick AA:BB:CC:DD:EE:FF --ssid "YourNetwork"

# Broadcast — kick everyone off the AP
./broadcast --ssid "YourNetwork" --continuous
```

---

## 📖 Detailed Usage

### 🎯 Mode 1 — Surgical Kick (`./kick [MAC]`)

Evict one specific client. All other devices remain connected.

```bash
# Auto-resolve AP by SSID (works at any location)
./kick DC:A6:32:AB:CD:EF --ssid "HomeNetwork"

# Explicit BSSID + channel (fastest — no scan needed)
./kick DC:A6:32:AB:CD:EF --bssid C8:3A:35:4E:2F:11 --channel 6

# Custom interface + 128-frame burst
./kick DC:A6:32:AB:CD:EF --ssid "HomeNetwork" --iface wlan1 --count 128

# Continuous kick until Ctrl+C
./kick DC:A6:32:AB:CD:EF --ssid "HomeNetwork" --continuous
```

**Directly via Python:**
```bash
sudo python3 evictor.py --ssid "HomeNetwork" kick DC:A6:32:AB:CD:EF
```

---

### 💥 Mode 2 — Broadcast (Kick All Clients)

Two sub-strategies to handle all scenarios:

**Strategy A — True Broadcast Frame** *(default, fastest)*  
Sends a single deauth to `FF:FF:FF:FF:FF:FF`. Disconnects everyone simultaneously.

```bash
./broadcast --ssid "HomeNetwork"
./broadcast --ssid "HomeNetwork" --continuous
./broadcast --bssid C8:3A:35:4E:2F:11 --channel 6 --count 200
```

**Strategy B — Per-Client Enumeration** *(`--enum-clients`)*  
Scans for all associated MACs first, then kicks each individually.  
More precise — useful when the AP filters broadcast deauth frames.

```bash
./broadcast --ssid "HomeNetwork" --enum-clients
```

---

### 🔍 Mode 3 — Scan & Discover

```bash
# List all nearby APs (full airodump-ng output)
sudo python3 evictor.py scan

# Resolve SSID and list all connected clients
sudo python3 evictor.py --ssid "HomeNetwork" scan
```

---

## 🗺️ Dynamic BSSID Resolution — How It Works

The `--ssid` flag is the core of location-agnostic operation.

```
Location A (Home):   HomeNetwork  →  BSSID: C8:3A:35:4E:2F:11  CH: 6
Location B (Office): HomeNetwork  →  BSSID: F8:1A:67:CC:DD:EE  CH: 11
```

**With `--ssid HomeNetwork` the tool:**
1. Puts the interface into monitor mode via `airmon-ng`
2. Runs a passive `airodump-ng` scan for `--scan-time` seconds (default: 15s)
3. Parses the CSV output to match the ESSID → extracts BSSID + channel
4. Automatically passes the correct BSSID to `aireplay-ng`

**No hardcoded MACs. Works everywhere.**

---

## 🏁 Full CLI Reference

```
sudo python3 evictor.py [GLOBAL OPTIONS] <MODE> [MODE OPTIONS]

Global Options:
  -i, --iface   IFACE    Wireless interface          (default: wlan0)
  --bssid       MAC      Target AP BSSID
  --channel,-c  CH       AP channel
  --ssid        NAME     Target SSID → auto-resolves BSSID + channel
  --scan-time   SEC      Scan duration for SSID resolution (default: 15)
  --count,-n    N        Deauth frames per burst (default: 64; 0=continuous)
  --continuous           Loop until Ctrl+C

Modes:
  kick    <CLIENT_MAC>   Evict one specific client
  broadcast              Evict all clients (--enum-clients for per-MAC mode)
  scan                   Passive AP scan / client enumeration
```

---

## 🔄 Typical Pentest Workflow

```bash
# 1. Discover the AP and enumerate its clients
sudo python3 evictor.py --ssid "TargetNetwork" --scan-time 20 scan

# 2. Surgically kick one specific device
./kick DC:A6:32:AB:CD:EF --ssid "TargetNetwork"

# 3. Broadcast eviction stress test
./broadcast --ssid "TargetNetwork" --continuous

# 4. Review timestamped session log
cat evictor.log
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    evictor.py                       │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ MonitorMode │  │resolve_bssid │  │  deauth() │  │
│  │  (context   │  │  (airodump   │  │(aireplay  │  │
│  │  manager)   │  │   CSV parse) │  │  -ng)     │  │
│  └──────┬──────┘  └──────┬───────┘  └─────┬─────┘  │
│         │                │                │        │
│  airmon-ng          airodump-ng      aireplay-ng   │
└─────────────────────────────────────────────────────┘
       ↑                  ↑                 ↑
   kick (bash)      broadcast (bash)    Python CLI
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `aireplay-ng: no answer` | Ensure monitor mode is active; try `--count 200` |
| Interface not found | Run `iwconfig` to confirm interface name |
| SSID not found in scan | Increase `--scan-time 30`; move closer to AP |
| Monitor mode already enabled | Run `airmon-ng stop wlan0mon` first |
| No clients showing | Use `scan` mode first to confirm associations |
| Permission denied | Run with `sudo` |

---

## 📜 Legal & Ethical Notice

This tool is intended **exclusively** for:
- ✅ Testing your **own** WiFi networks
- ✅ Authorized red team / penetration test engagements
- ✅ CTF competitions and isolated lab environments
- ✅ Educational understanding of 802.11 deauthentication

**Always obtain written authorization before testing any network.**  
The authors take no responsibility for misuse of this tool.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Made with ⚡ for ethical hackers
</div>
