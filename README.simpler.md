<!-- README.simpler.md - 簡素化版README -->

**他のバージョン**: [オリジナル版](README.backup.md) | [詳細版](README.detail.md)

# IPv6 EVPN/VXLAN のための FRR パッチ

## これは何？

フレッツの閉域 IPv6 網などの IPv6 環境で EVPN/VXLAN を実現するための包括的なソリューションです。**FRRouting の IPv6 対応パッチ**、**Linux カーネルのフラグメント対応パッチ**、**高性能 DPDK アプリケーション**、そして**ビルド済み deb パッケージ**を提供し、Ubuntu 24.04 LTS 環境で簡単に構築できます。


+ **[ベンチマーク試験結果](./bench/)** - Linux カーネルと DPDK の性能比較（3-4倍の性能向上）
+ **[Interop25 発表資料](./interop25_m-asama.pdf)** - プロジェクトの概要と実装内容
+ **[パッケージ配布サイト](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/)** - ビルド済み deb パッケージ

## 参考リンク

+ **[VXLAN fragmentation 解説記事](https://www.cuteip.net/posts/2024/04/09/cuteip-updates-5-vxlan2-dkms/)** - Linux カーネルパッチの参考
+ **[FRRouting EVPN 公式ドキュメント](https://docs.frrouting.org/en/latest/evpn.html)** - 設定方法の詳細

## 簡単な説明

IPv6 環境での EVPN/VXLAN には **3つの課題** がありました：

1. **FRRouting の IPv4 限定** - IPv6 での EVPN/VXLAN に未対応
2. **フラグメント処理の欠如** - MTU 1500 環境で Ethernet フレームを分割不可
3. **転送性能の限界** - 小型 PC での低スループット

これらを解決するため、以下の対応を行いました：

### 1️⃣ FRRouting IPv6 対応

[frr_8.4.4-1.1ubuntu6.3+evpnvxlan6.3.patch](frr_8.4.4-1.1ubuntu6.3+evpnvxlan6.3.patch) により IPv6 での EVPN/VXLAN を実現。Route Type 2/3 のみテスト済み。

### 2️⃣ Linux カーネル フラグメント対応

[linux_6.8.0-55.57+evpnvxlan6.2.patch](linux_6.8.0-55.57+evpnvxlan6.2.patch) により MTU 1500 環境での VXLAN フラグメント処理を実現。DPDK モードでも Linux カーネルへのフォールバック時に必要。

### 3️⃣ DPDK 高速転送機能

**gdp** アプリケーションにより Linux カーネルの 3-4 倍の転送性能を実現。物理 NIC を仮想 NIC（tnpXsX）に変換し、DPDK で高速処理。

**注意**: DPDK 処理される VXLAN 通信には Netfilter が適用されません。

## 使い方

### インストール手順

[パッケージ配布サイト](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/) から以下をダウンロード・インストール：

1. **Linux カーネル** - フラグメント対応版
2. **DPDK アプリケーション (gdp)** - 高速転送用（オプション）
3. **FRRouting** - IPv6 EVPN 対応版

#### DPDK 事前準備

```bash
apt install dpdk librte-net-igc24  # NIC に応じて PMD を選択
```

#### DPDK アプリケーションの設定

gdp をインストールすると `/etc/default/gdp` というファイルができるのでこちらを編集します。
`/etc/default/gdp` はデフォルトで以下のような内容になっています。

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

`GDP_OPTS` は DPDK アプリを起動する際のコマンドラインオプションを指定します。

デフォルトの `-l 2-3` は CPU コアの 3 番目(インデックス 2)と 4 番目(インデックス 3)を DPDK のパケット処理に用いるよう指定しています。
この DPDK アプリでは 2 つ CPU コアを指定する必要があります。
DPDK アプリでは指定した 2 つのうち 1 つをビジーポールのパケット処理に用います。
もう 1 つをブロッキングの Netlink などに用います。
ので、 `top` コマンドなどで CPU 使用率を確認すると gdp というプロセスが常に 100% ほど使っているような状態になります。

`--log-level=gdp:debug` はこの DPDK アプリをデバッグ出力するよう設定して起動するよう設定しています。
この設定があるとデバッグのメッセージをログに出力するようになるので、もし不要であれば削っても大丈夫です。

`GDP_NRHP` は Linux 側に確保してもらう hugepages の大きさを指定します。
2MB ページを確保する数を指定するのでデフォルトの 1024 を指定した場合 2GB が hugepages として確保されます。

`GDP_HPNODE` は hugepages を確保する NUMA ノードを指定します。
デフォルト設定のままで問題ないと思われます。

`GDP_ORIGIFS` には DPDK アプリで処理をさせたい物理 NIC を列挙します。
gdp アプリは起動時に物理 NIC を一旦 Linux のカーネルのドライバから切り離し DPDK で用いれるようにしますが、 gdp を再起動した場合はすでにその処理は行われているためスキップする必要があります。
この `GDP_ORIGIFS` は gdp アプリが起動する際にその切り離しがすでに行われているか否かを判断するために用います。
(ここに指定した物理 NIC が存在しない時は切り離しの処理をしない。)

`GDP_PCIDEVS` には DPDK アプリで処理させたい物理 NIC の PCI アドレスを列挙します。
物理 NIC の PCI アドレスは `lspci` コマンドで確認してください。

gdp アプリは起動すると PCI アドレスから名前を考え仮想 NIC を作成します。
通常 enp1s0 のような名前だった場合 1 文字目が t に変わった tnp1s0 のような名前で作成します。

すでに Netplan で enp1s0 などにアドレスなどを設定する設定があるときは tnp1s0 などに書き換えておきます。

`systemctl enable gdp.service` で起動時に gdp を起動するよう設定してから再起動することで DPDK アプリが使えるようになります。

### FRRouting のインストールと設定

```bash
apt install frr  # 公式版をまずインストール
dpkg -i <修正版FRRoutingパッケージ>  # 修正版に差し替え
```

#### EVPN デーモンの有効化

EVPN を用いるために `/etc/frr/daemons` を bgpd が起動するよう修正します。
`bgpd=no` となっている箇所を `bgpd=yes` に書き換えます。

例えば自分が `2001:db8:0:1::11` で `2001:db8:0:2::11` と `2001:db8:0:3::11` の 2 台と EVPN/VXLAN したいような時は以下のような感じの設定になると思います。

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

#### BGP 設定の追加設定

また、以下のコマンドを設定しないと BGP のパケットが送信されない場合があるようです。

```
ipv6 nht resolve-via-default
```

### ネットワークインターフェースの設定

その上で、例えば tnp3s0 が WAN 側(フレッツの閉域 IPv6 網に接続された側)で、 tnp4s0 が LAN 側(L2 VPN を延伸したい側)で、延伸したい VNI が 550 の場合、以下のような設定を行います。

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

上記の例では VNI が 550 の VXLAN インターフェースを vni550 という名前で作成し、それを br50 という名前のブリッジインターフェースに接続しています。
最後に LAN 側のインターフェースである tnp4s0 も br50 にアタッチしています。
(WAN 側のインターフェースである tnp3s0 はすでに設定されているものとしています。)

FRRouting の詳しい設定は [FRRouting EVPN 公式ドキュメント](#frrouting-evpn-docs) を参照してください。

### 動作確認

正常に動作すればこのような結果になります。

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

## 補足というかメモというか

送信元がどこからでも VNI が一致してしまっていたら Ethernet フレームを受け付けてしまうことになり、セキュリティ上の問題があると考えられます。
課題となるのは DPDK アプリ側では Netfilter のフィルタが効かないため、対応するとすれば Route Type 3(Inclusive Multicast Ethernet Tag Route) で受け取った VTEP 以外からの VXLAN パケットを受け付けないようにする必要があることです。

DPDK アプリのソースコードを一般に公開することは現時点では考えていません。
が、物理的に一度でもあったことがあるような方であれば GitHub アカウントを教えてもらえれば参照権限つけます。
みてみたいという方は X の DM ででも連絡ください。

何かおかしな動きをするのに気づいた方はここでイシューをあげていただければ可能であれば対応すると思います。
