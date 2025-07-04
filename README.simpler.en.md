<!-- README.simpler.en.md - English version of the simplified README -->

**Other versions**: [Original](README.backup.md) | [Detail](README.detail.md) | [Simple](README.simpler.md) | [EN Original](README.backup.en.md) | [EN Detail](README.detail.en.md) | [EN Simple](README.simpler.en.md)

# FRR Patch for IPv6 EVPN/VXLAN

## What is this?

A comprehensive solution for implementing EVPN/VXLAN in IPv6 environments such as NGN IPv6 networks. Provides **FRRouting IPv6 support patches**, **Linux kernel fragmentation support patches**, **high-performance DPDK applications**, and **pre-built deb packages** for easy setup on Ubuntu 24.04 LTS environments.

+ **[Benchmark Test Results](./bench/)** - Performance comparison between Linux kernel and DPDK (3-4x performance improvement)
+ **[Interop25 Presentation Materials](./interop25_m-asama.pdf)** - Project overview and implementation details
+ **[Package Distribution Site](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/)** - Pre-built deb packages

## Reference Links

+ **[VXLAN Fragmentation Article](https://www.cuteip.net/posts/2024/04/09/cuteip-updates-5-vxlan2-dkms/)** - Reference for Linux kernel patch
+ **[FRRouting EVPN Official Documentation](https://docs.frrouting.org/en/latest/evpn.html)** - Detailed configuration methods

## Brief Explanation

EVPN/VXLAN in IPv6 environments faced **3 challenges**:

1. **FRRouting IPv4 Limitation** - No support for EVPN/VXLAN over IPv6
2. **Lack of Fragmentation Processing** - Unable to fragment Ethernet frames in MTU 1500 environments
3. **Forwarding Performance Limitations** - Low throughput on small PCs

To solve these issues, we implemented the following solutions:

### 1️⃣ FRRouting IPv6 Support

[frr_8.4.4-1.1ubuntu6.3+evpnvxlan6.3.patch](frr_8.4.4-1.1ubuntu6.3+evpnvxlan6.3.patch) enables EVPN/VXLAN over IPv6. Only Route Types 2/3 have been tested.

### 2️⃣ Linux Kernel Fragmentation Support

[linux_6.8.0-55.57+evpnvxlan6.2.patch](linux_6.8.0-55.57+evpnvxlan6.2.patch) enables VXLAN fragmentation processing in MTU 1500 environments. Required even in DPDK mode for Linux kernel fallback cases.

### 3️⃣ DPDK High-Speed Forwarding

The **gdp** application achieves 3-4x the forwarding performance of the Linux kernel. Converts physical NICs to virtual NICs (tnpXsX) for high-speed DPDK processing.

**Note**: Netfilter rules do not apply to VXLAN communication processed by DPDK.

## Usage

### Installation Steps

Download and install the following from the [package distribution site](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/):

1. **Linux Kernel** - Fragmentation support version
2. **DPDK Application (gdp)** - For high-speed forwarding (optional)
3. **FRRouting** - IPv6 EVPN support version

#### DPDK Prerequisites

```bash
apt install dpdk librte-net-igc24  # Select PMD according to your NIC
```

#### DPDK Application Configuration

When you install gdp, a file called `/etc/default/gdp` is created, which you need to edit.
`/etc/default/gdp` has the following default content:

```
GDP_OPTS="-l 2-3 --log-level=gdp:debug"
GDP_NRHP="1024"
GDP_HPNODE="node0"
GDP_ORIGIFS="
	enp1s0
	enp2s0
	enp3s0
	enp4s0
"
GDP_PCIDEVS="
	0000:01:00.0
	0000:02:00.0
	0000:03:00.0
	0000:04:00.0
"
```

`GDP_OPTS` specifies the command-line options for starting the DPDK application.

The default `-l 2-3` specifies that the 3rd CPU core (index 2) and 4th CPU core (index 3) should be used for DPDK packet processing.
This DPDK application requires two CPU cores to be specified.
The DPDK application uses one of the two specified cores for busy-poll packet processing.
The other is used for blocking operations like Netlink.
Therefore, when you check CPU usage with the `top` command, you'll see that the gdp process is constantly using about 100% CPU.

`--log-level=gdp:debug` configures the DPDK application to start with debug output enabled.
With this setting, debug messages will be output to logs. You can remove this if it's not needed.

`GDP_NRHP` specifies the size of hugepages to be allocated on the Linux side.
This specifies the number of 2MB pages to allocate, so the default value of 1024 will allocate 2GB as hugepages.

`GDP_HPNODE` specifies the NUMA node on which to allocate hugepages.
The default setting should be fine.

`GDP_ORIGIFS` lists the physical NICs that you want the DPDK application to process.
The gdp application temporarily detaches physical NICs from Linux kernel drivers and makes them available for DPDK use when starting, but when gdp is restarted, this process has already been done and should be skipped.
This `GDP_ORIGIFS` is used to determine whether the detachment has already been performed when the gdp application starts.
(If the physical NICs specified here don't exist, the detachment process is not performed.)

`GDP_PCIDEVS` lists the PCI addresses of the physical NICs that you want the DPDK application to process.
Check the PCI addresses of physical NICs with the `lspci` command.

When the gdp application starts, it creates virtual NICs by deriving names from PCI addresses.
For example, if the name was originally enp1s0, it creates a virtual NIC with the name tnp1s0, where the first character is changed to 't'.

If you already have Netplan configuration that sets addresses for enp1s0, change it to tnp1s0, etc.

After setting `systemctl enable gdp.service` to start gdp at boot time, reboot to make the DPDK application available.

### FRRouting Installation and Configuration

```bash
apt install frr  # First install the official version
dpkg -i <modified_frrouting_package>  # Replace with modified version
```

#### Enabling EVPN Daemon

To use EVPN, modify `/etc/frr/daemons` so that bgpd starts.
Change the line that says `bgpd=no` to `bgpd=yes`.

For example, if you want to do EVPN/VXLAN with two other nodes at `2001:db8:0:2::11` and `2001:db8:0:3::11` from your node at `2001:db8:0:1::11`, the configuration would look like this:

```
router bgp 64512
 neighbor 2001:db8:0:2::11 remote-as internal
 neighbor 2001:db8:0:2::11 update-source 2001:db8:0:1::11
 neighbor 2001:db8:0:3::11 remote-as internal
 neighbor 2001:db8:0:3::11 update-source 2001:db8:0:1::11
 !
 address-family ipv6 unicast
  network 2001:db8:0:1::11/128
 exit-address-family
 !
 address-family l2vpn evpn
  neighbor 2001:db8:0:2::11 activate
  neighbor 2001:db8:0:3::11 activate
  advertise-all-vni
 exit-address-family
exit
```

#### Additional BGP Configuration

Also, you need to configure the following command, otherwise BGP packets may not be sent:

```
ipv6 nht resolve-via-default
```

### Network Interface Configuration

Then, for example, if tnp3s0 is the WAN side (connected to the NGN IPv6 network), tnp4s0 is the LAN side (the side where you want to extend the L2 VPN), and the VNI you want to extend is 550, configure as follows:

```
ip link add br50 type bridge
ip link set br50 addrgenmode none
ip link add vni550 type vxlan local 2001:db8:0:1::11 dstport 4789 id 550 nolearning
ip link set vni550 master br50 addrgenmode none
ip link set vni550 type bridge_slave neigh_suppress on learning off
sysctl -w net.ipv4.conf.br50.forwarding=0
sysctl -w net.ipv6.conf.br50.forwarding=0
ip link set vni550 up
ip link set br50 up
ip link set tnp4s0 master br50
```

In the above example, a VXLAN interface with VNI 550 is created with the name vni550 and connected to a bridge interface named br50.
Finally, the LAN-side interface tnp4s0 is also attached to br50.
(The WAN-side interface tnp3s0 is assumed to be already configured.)

For detailed FRRouting configuration, refer to the [FRRouting EVPN official documentation](#frrouting-evpn-docs).

### Operation Verification

If everything works properly, you should see results like this:

```
# show bgp summary 

IPv4 Unicast Summary (VRF default):
BGP router identifier 192.168.1.11, local AS number 64512 vrf-id 0
BGP table version 0
RIB entries 0, using 0 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor         V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
2001:db8:0:2::11 4      64512         4         5        0    0    0 00:00:08            0        0 N/A
2001:db8:0:3::11 4      64512         4         5        0    0    0 00:00:08            0        0 N/A

Total number of neighbors 2

L2VPN EVPN Summary (VRF default):
BGP router identifier 192.168.1.11, local AS number 64512 vrf-id 0
BGP table version 0
RIB entries 1, using 192 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor         V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
2001:db8:0:2::11 4      64512         4         5        0    0    0 00:00:08            0        1 N/A
2001:db8:0:3::11 4      64512         4         5        0    0    0 00:00:08            0        1 N/A

Total number of neighbors 2
```

```
# show evpn vni detail 
VNI: 550
 Type: L2
 Tenant VRF: default
 VxLAN interface: vni550
 VxLAN ifIndex: 10
 SVI interface: br50
 SVI ifIndex: 9
 Local VTEP IP: 2001:db8:0:1::11
 Mcast group: 
 Remote VTEPs for this VNI:
  2001:db8:0:3::11 flood: HER
  2001:db8:0:2::11 flood: HER
 Number of MACs (local and remote) known for this VNI: 3
 Number of ARPs (IPv4 and IPv6, local and remote) known for this VNI: 0
 Advertise-gw-macip: No
 Advertise-svi-macip: No
```

```
# show evpn mac vni all 

VNI 550 #MACs (local and remote) 3

Flags: N=sync-neighs, I=local-inactive, P=peer-active, X=peer-proxy
MAC               Type   Flags Intf/Remote ES/VTEP            VLAN  Seq #'s
52:54:00:56:18:ff local        tnp4s0                               0/0
72:eb:58:30:cb:c5 remote       2001:db8:0:3::11                     0/0
0a:5a:bf:b4:cc:16 remote       2001:db8:0:2::11                     0/0
```

## Supplementary Notes

If Ethernet frames are accepted from any source as long as the VNI matches, this could pose a security problem.
The challenge is that Netfilter filters don't work on the DPDK application side, so if we were to address this, we would need to reject VXLAN packets from VTEPs other than those received via Route Type 3 (Inclusive Multicast Ethernet Tag Route).

We are not currently considering making the DPDK application source code publicly available.
However, if you've physically met me at least once, I can give you access rights if you tell me your GitHub account.
If you'd like to take a look, please contact me via DM on X.

If you notice any strange behavior, please open an issue here and I'll try to address it if possible.