ip netns add evpnvxlan6
ip netns set evpnvxlan6 1

ip link set enp1s0f0 netns evpnvxlan6
ip link set enp1s0f1 netns evpnvxlan6

ip netns exec evpnvxlan6 ip link set enp1s0f0 up
ip netns exec evpnvxlan6 ip link set enp1s0f1 up

ip netns exec evpnvxlan6 ip address add 2001:db8:0:1::2/64 dev enp1s0f0
ip netns exec evpnvxlan6 ip -6 neigh add 2001:db8:0:1::1 lladdr a8:b8:e0:05:97:75 dev enp1s0f0

ip netns exec evpnvxlan6 ip link add br50 type bridge
ip netns exec evpnvxlan6 ip link set br50 addrgenmode none
ip netns exec evpnvxlan6 ip link add vni550 type vxlan local 2001:db8:0:1::2 dstport 4789 id 550 nolearning
ip netns exec evpnvxlan6 ip link set vni550 master br50 addrgenmode none
ip netns exec evpnvxlan6 ip link set vni550 type bridge_slave neigh_suppress on learning off
ip netns exec evpnvxlan6 sysctl -w net.ipv4.conf.br50.forwarding=0
ip netns exec evpnvxlan6 sysctl -w net.ipv6.conf.br50.forwarding=0
ip netns exec evpnvxlan6 ip link set vni550 up
ip netns exec evpnvxlan6 ip link set br50 up
ip netns exec evpnvxlan6 ip link set enp1s0f1 master br50

ip netns exec evpnvxlan6 bridge fdb add fe:54:00:aa:bb:cc dev vni550 dst 2001:db8:0:1::1
#ip netns exec evpnvxlan6 bridge fdb add fe:54:00:aa:bb:cc dev vni550 master
#ip netns exec evpnvxlan6 bridge fdb add a8:b8:e0:05:97:76 dev enp1s0f1 master

echo 4 > /proc/irq/`grep enp1s0f0-TxRx-0 /proc/interrupts | awk '{print $1}' | cut -d: -f1`/smp_affinity
echo 4 > /proc/irq/`grep enp1s0f0-TxRx-1 /proc/interrupts | awk '{print $1}' | cut -d: -f1`/smp_affinity
echo 4 > /proc/irq/`grep enp1s0f0-TxRx-2 /proc/interrupts | awk '{print $1}' | cut -d: -f1`/smp_affinity
echo 4 > /proc/irq/`grep enp1s0f0-TxRx-3 /proc/interrupts | awk '{print $1}' | cut -d: -f1`/smp_affinity

echo 8 > /proc/irq/`grep enp1s0f1-TxRx-0 /proc/interrupts | awk '{print $1}' | cut -d: -f1`/smp_affinity
echo 8 > /proc/irq/`grep enp1s0f1-TxRx-1 /proc/interrupts | awk '{print $1}' | cut -d: -f1`/smp_affinity
echo 8 > /proc/irq/`grep enp1s0f1-TxRx-2 /proc/interrupts | awk '{print $1}' | cut -d: -f1`/smp_affinity
echo 8 > /proc/irq/`grep enp1s0f1-TxRx-3 /proc/interrupts | awk '{print $1}' | cut -d: -f1`/smp_affinity

echo performance > /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor
echo performance > /sys/devices/system/cpu/cpu3/cpufreq/scaling_governor

echo 3400000 > /sys/devices/system/cpu/cpu2/cpufreq/scaling_min_freq
echo 3400000 > /sys/devices/system/cpu/cpu3/cpufreq/scaling_min_freq
