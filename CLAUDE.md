# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains **evpnvxlan6**, a research project implementing EVPN/VXLAN over IPv6 on Linux systems. The project addresses limitations in existing open-source implementations by providing:

1. **FRRouting IPv6 EVPN Support**: Patches to enable EVPN/VXLAN over IPv6 in FRRouting
2. **Linux Kernel Fragmentation Support**: Kernel modifications to handle IPv6 fragmentation in VXLAN
3. **High-Performance DPDK Implementation**: Custom DPDK application ("gdp") for accelerated packet processing

## Development Environment

This project doesn't use traditional build systems. Development involves:

- **Patch Application**: Apply patches to Ubuntu 24.04 LTS packages
- **Package Installation**: Install pre-built .deb packages from https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/
- **Configuration**: Set up DPDK, FRRouting, and network interfaces

### Required Dependencies

```bash
# DPDK and PMD drivers
apt install dpdk librte-net-igc24  # Adjust PMD for your NIC

# FRRouting (install official first, then replace with patched version)
apt install frr
```

## Key Components

### 1. Patches

- **FRRouting Patch** (`frr_8.4.4-1.1ubuntu6.3+evpnvxlan6.3.patch`):
  - Converts IPv4-only EVPN to support IPv6
  - Replaces `struct in_addr` with `struct ipaddr` throughout codebase
  - Modifies 38 files across BGP EVPN and Zebra modules
  - Supports Route Type 2 (MAC/IP Advertisement) and Route Type 3 (Inclusive Multicast)

- **Linux Kernel Patch** (`linux_6.8.0-55.57+evpnvxlan6.2.patch`):
  - Enables VXLAN IPv6 fragmentation support
  - Modifies `drivers/net/vxlan/vxlan_core.c`
  - Allows MTU 1500 Ethernet frames over IPv6 networks

### 2. DPDK Application ("gdp")

- **Architecture**: Creates virtual NICs (tnpXsX) that replace physical NICs (enpXsX)
- **Performance**: Provides 3-4x throughput improvement over Linux kernel
- **Hybrid Processing**: DPDK handles fast path, Linux kernel handles control plane
- **Configuration**: `/etc/default/gdp` for DPDK options and NIC assignments

### 3. Benchmarking Framework

Located in `bench/` directory:

- **Test Scripts**: `bench/scripts/dut/` (DUT setup) and `bench/scripts/tester/` (Cisco TRex)
- **Traffic Patterns**: 8 packet sizes from 64B to 1518B
- **Test Directions**: Encapsulation, decapsulation, and bidirectional
- **Performance Measurement**: Binary search for zero-loss throughput

## Common Development Tasks

### Running Benchmarks

```bash
# Set up DUT with Linux kernel processing
cd bench/scripts/dut
./linux.sh

# Set up DUT with DPDK processing
./gdp.sh

# Run benchmarks from tester
cd bench/scripts/tester
python3 bench.py
```

### FRRouting Configuration

```bash
# Enable BGP daemon
echo "bgpd=yes" >> /etc/frr/daemons

# Basic EVPN configuration example
vtysh -c "conf t" -c "router bgp 64512" -c "neighbor 2001:db8::1 remote-as internal"
```

### Network Interface Setup

```bash
# Create VXLAN interface over IPv6
ip link add vni550 type vxlan local 2001:db8::11 dstport 4789 id 550 nolearning

# Bridge setup for L2 VPN
ip link add br50 type bridge
ip link set vni550 master br50
ip link set eth1 master br50
```

## Architecture Notes

### Data Plane Options

1. **Linux Kernel Only**: Standard kernel VXLAN with fragmentation patch
2. **DPDK Hybrid**: High-performance DPDK with kernel fallback
   - DPDK processes unicast VXLAN traffic
   - Kernel handles multicast, control plane, and complex packets

### Performance Characteristics

- **Linux Kernel**: ~1Gbps sustained performance
- **DPDK 1-core**: ~2Gbps sustained performance
- **DPDK 2-core**: ~4Gbps sustained performance
- **Fragmentation Impact**: Significant performance degradation for MTU 1500+ packets

### Security Considerations

- DPDK bypass Netfilter rules for processed traffic
- BGP filtering works (falls back to kernel)
- VXLAN unicast traffic bypasses iptables when using DPDK

## Testing Infrastructure

- **Hardware**: Intel N100-based systems with 10Gbps SFP+ interfaces
- **Test Tool**: Cisco TRex for traffic generation
- **Measurement**: Zero-loss throughput with binary search algorithm
- **Metrics**: PPS (packets per second), BPS (bits per second), power consumption

## Limitations and Notes

- Only Route Type 2 and 3 EVPN routes are tested
- IPv4/IPv6 mixed configurations not validated
- DPDK application source code not publicly available
- Designed for NTT Flets IPv6 network (MTU 1500)

## Target Environment

- **OS**: Ubuntu 24.04 LTS
- **Network**: IPv6-only underlay (NTT Flets)
- **Use Case**: L2 VPN extension over IPv6 WAN
- **Performance**: Low-latency, high-throughput packet processing