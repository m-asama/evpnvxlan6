<!-- README.backup.en.md - English version of the original backup -->

**Other versions**: [Original](README.backup.md) | [Detail](README.detail.md) | [Simple](README.simpler.md) | [EN Original](README.backup.en.md) | [EN Detail](README.detail.en.md) | [EN Simple](README.simpler.en.md)

# EVPN/VXLAN on NGN IPv6 Network

## What is this?

+ Introduction to EVPN/VXLAN on NGN IPv6 network
+ Built on Ubuntu 24.04 LTS environment using deb packages
+ Modified FRRouting to support EVPN/VXLAN over IPv6
+ Added support for fragmentation on the underlay side, allowing MTU 1500 frames to pass through
+ High-speed forwarding capabilities using DPDK are also available

For forwarding performance comparisons between Linux kernel processing and our custom DPDK application, please see the [benchmark test results](./bench/).

Materials exhibited at Interop25 are available [here](./interop25_m-asama.pdf).

## Brief explanation

Wouldn't it be convenient if EVPN/VXLAN could be used on NGN IPv6 networks?
However, there are several challenges that need to be overcome.

First, FRRouting, which is thought to be the most widely used OSS EVPN implementation, only supports EVPN/VXLAN over IPv4 and does not support EVPN/VXLAN over IPv6.

Second, NGN IPv6 networks have an MTU of 1500, so MTU 1500 Ethernet frames must be fragmented to pass through.
However, the Linux kernel's VXLAN implementation does not support fragmentation and cannot send MTU 1500 Ethernet frames by fragmenting them.

Finally, the Linux kernel's forwarding capabilities cannot achieve very high performance on small PCs and similar devices.
Particularly in situations where many small packets need to be sent, performance is limited.

Therefore, we have implemented the following solutions:

### Modified FRRouting to support EVPN/VXLAN over IPv6

FRRouting's EVPN/VXLAN seems to be designed only for data center use and could not be used with IPv6.
So we made the following modifications to enable IPv6 support:

+ [frr_8.4.4-1.1ubuntu6.3+evpnvxlan6.3.patch](frr_8.4.4-1.1ubuntu6.3+evpnvxlan6.3.patch)

However, only the minimum necessary functions required for L2 VPN with EVPN/VXLAN have been tested.

Specifically, only Route Types 2 (MAC/IP Advertisement Route) and 3 (Inclusive Multicast Ethernet Tag Route) have been tested.
Everything else probably won't work properly.

For example, because the implementation was based on IPv4, there were several places where router ID was used as an address by default, but since router ID cannot be converted to IPv6 addresses, we handled those areas somewhat arbitrarily. (XXX: To be reviewed properly later.)

Also, we have not tested what happens when IPv4 and IPv6 configurations are mixed.
While the Linux kernel can create VXLAN interfaces with the same VNI for both IPv4 and IPv6, the FRRouting side probably won't behave as intended in such cases.

Additionally, while we confirmed that some show commands seem to work, we haven't thoroughly verified them.

### Added support for fragmentation on the underlay side to allow MTU 1500 frames to pass through

As mentioned above, the Linux kernel's VXLAN implementation is not designed to handle fragmentation and reassembly on the underlay side.
We referenced [this article](https://www.cuteip.net/posts/2024/04/09/cuteip-updates-5-vxlan2-dkms/) which provides very detailed information on this topic.

+ [https://www.cuteip.net/posts/2024/04/09/cuteip-updates-5-vxlan2-dkms/](https://www.cuteip.net/posts/2024/04/09/cuteip-updates-5-vxlan2-dkms/)

This time, we used this implementation directly.

+ [linux_6.8.0-55.57+evpnvxlan6.2.patch](linux_6.8.0-55.57+evpnvxlan6.2.patch)

However, this modification may not be essential when using the DPDK-based data plane introduced next.
The DPDK-based data plane we implemented supports fragmentation, and packets processed by it don't go through the Linux kernel.
However, packets that cannot be processed by the DPDK-based custom data plane are passed to the Linux kernel for processing, so without this modification, packets requiring fragmentation or reassembly that are passed to the Linux kernel would not be handled properly.

### Implementation of high-speed forwarding capabilities using DPDK

We wrote a DPDK application that processes VXLAN communication to achieve faster forwarding processing than using the Linux kernel's forwarding capabilities.
It has the following features:

+ Creates one virtual NIC corresponding to each physical NIC, allowing IP addresses and routing configurations to be set just like regular NICs
+ Captures routing and bridging configurations made on the Linux kernel side via Netlink, and processes all packets received by physical NICs within the DPDK application when possible; packets that cannot be processed are passed to virtual NICs for Linux kernel processing
+ All packets destined for the local system are delivered to the Linux kernel side through virtual NICs

Note that Netfilter rules configured on the virtual NIC side do not apply to this DPDK application.
While Netfilter rules will apply to packets that the DPDK application cannot process and passes to the Linux kernel side (so BGP connection sources can be filtered with Netfilter), VXLAN communication is handled entirely within the DPDK application, so attempting to filter it with Netfilter may not work as expected.
(Probably multicast and other traffic that cannot be processed by the DPDK application will be filtered, but unicast communication will pass through.
See the "Supplementary notes" section at the end for more details.)

If performance is not particularly problematic, it is possible to use only the Linux kernel for all processing without using this DPDK application.

## Usage

When you want to enable VXLAN fragmentation support in the Linux kernel, install the Linux kernel deb package available [here](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/) and boot with it.
Alternatively, manually create a Linux kernel deb package with [linux_6.8.0-55.57+evpnvxlan6.2.patch](linux_6.8.0-55.57+evpnvxlan6.2.patch) applied and install it.

When you want to process VXLAN with the DPDK application, install the deb package named gdp available [here](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/).

However, you need to install the dpdk-related deb packages required by the DPDK application first.
Run `apt install dpdk` to install these packages before installing gdp.

In addition to the dpdk package, you need to install the PMD (Poll Mode Driver) for the NIC you want to use.
In Ubuntu, PMD packages are provided with names like `librte-net-(NIC name)24`.
For example, if you want to use a NIC that works with Intel's igc driver, install the igc PMD with `apt install librte-net-igc24`.

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

Finally, replace the FRRouting deb package with the one available [here](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/).
It's easiest to first install the official frr and its dependent deb packages with `apt install frr`, then replace them with `dpkg -i`.

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

Also, for some reason, you need to add the following command, otherwise BGP packets may not be sent at all:

```
ipv6 nht resolve-via-default
```

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

For detailed FRRouting configuration, refer to [this documentation](https://docs.frrouting.org/en/latest/evpn.html).

If everything works properly, you should see something like this:

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

## Supplementary notes

If Ethernet frames are accepted from any source as long as the VNI matches, wouldn't this be a security problem?
The troublesome part is that Netfilter filters don't work on the DPDK application side, so if we were to address this, we would need to reject VXLAN packets from VTEPs other than those received via Route Type 3 (Inclusive Multicast Ethernet Tag Route).

We are not currently considering making the DPDK application source code publicly available.
However, if you've physically met me at least once, I can give you access rights if you tell me your GitHub account.
If you'd like to take a look, please contact me via DM on X.

If you notice any strange behavior, please open an issue here and I'll try to address it if possible.