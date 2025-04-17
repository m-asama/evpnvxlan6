# フレッツの閉域 IPv6 網で EVPN/VXLAN

## これは何？

+ フレッツの閉域 IPv6 網で EVPN/VXLAN する方法の紹介
+ Ubuntu 24.04 LTS の環境に deb パッケージを入れて構築
+ FRRouting を IPv6 でも EVPN/VXLAN できるように改造
+ アンダーレイ側でのフラグメントに対応し MTU 1500 のフレームも通るよう修正
+ DPDK を用いた高速な転送機能も利用可能

Linux カーネルで処理した場合と独自 DPDK アプリで処理した場合の転送性能については [こちらのベンチマーク試験結果](./bench/) をご覧ください。

## 簡単な説明

フレッツの閉域 IPv6 網で EVPN/VXLAN できたら便利じゃないですか。
でもそのためにはいくつか乗り越えなければならない課題があります。

まず OSS の EVPN 実装で最も広く用いられていると思われる FRRouting が IPv4 での EVPN/VXLAN にしか対応しておらず、 IPv6 での EVPN/VXLAN に対応していません。

次にフレッツの閉域 IPv6 網は MTU 1500 なので MTU 1500 の Ethernet フレームは分割しないと通せません。
ところが Linux カーネルの VXLAN 実装はフラグメントに対応しておらず、 MTU 1500 の Ethernet フレームを分割して送ることができません。

最後に Linux カーネルの転送機能では小型 PC などではそんなに性能が出せません。
特に小さなパケットをたくさん送らなければならないような状況ではあまり性能が出せません。

そこで以下の対応をしてみました。

### FRRouting を IPv6 でも EVPN/VXLAN できるように改造

FRRouting の EVPN/VXLAN はデータセンターでの利用しか想定していないためか IPv6 で利用することができないようでした。
そこでとりあえず以下のような修正を行い IPv6 でも利用できるよう改造しました。

+ [frr_8.4.4-1.1ubuntu6.3+evpnvxlan6.3.patch](frr_8.4.4-1.1ubuntu6.3+evpnvxlan6.3.patch)

但し EVPN/VXLAN で L2 VPN をする際に必要となる必要最低限の機能しかテストしていません。

具体的には Route Type は 2(MAC/IP Advertisement Route) と 3(Inclusive Multicast Ethernet Tag Route) しかテストしていません。
それ以外はおそらくまともに動かないと思います。

例えば IPv4 を前提とした作りになっていたためかデフォルトの値としてルータ ID をアドレスとして用いているような箇所がいくつかありましたがルータ ID は IPv6 アドレスに変換できないのでその辺を適当に処理しています。(XXX: 後でちゃんと見直す。)

また、 IPv4 の設定と IPv6 の設定を混在させたときにどうなるかも検証していません。
Linux カーネルの方は同じ VNI の VXLAN インターフェースを IPv4 と IPv6 の両方で作成することもできるようですがそれをやった時に FRRouting 側はおそらく意図した動作をしないような気がします。

あと show 系のコマンドもいくつかは動作していそうなことを確認しましたがちゃんとは確認していません。

### アンダーレイ側でのフラグメントに対応し MTU 1500 のフレームも通るよう修正

前述の通り Linux カーネルの VXLAN 実装はアンダーレイ側でフラグメントとリアセンブルの処理を行うようになっていません。
この辺の話は [こちら](https://www.cuteip.net/posts/2024/04/09/cuteip-updates-5-vxlan2-dkms/) がとても詳しく参考にさせていただきました。

+ [https://www.cuteip.net/posts/2024/04/09/cuteip-updates-5-vxlan2-dkms/](https://www.cuteip.net/posts/2024/04/09/cuteip-updates-5-vxlan2-dkms/)

今回はこちらをそのまま利用させていただきました。

+ [linux_6.8.0-55.57+evpnvxlan6.2.patch](linux_6.8.0-55.57+evpnvxlan6.2.patch)

ただ、こちらの対応は次で紹介する DPDK を用いたデータプレーンを用いる場合は必須ではないかもしれません。
今回実装した DPDK を用いたデータプレーンはフラグメントに対応しており、それで処理されるパケットに関しては Linux カーネルを通らないためです。
ただ DPDK を用いた独自データプレーンで処理できないものは Linux カーネルに処理を投げるようになっており、フラグメントやリアセンブルが必要なパケットを Linux カーネルに投げるような状況が生じた際はこの修正がないとうまく処理できない事態となります。

### DPDK を用いた高速な転送機能の実装

Linux カーネルの転送機能を用いるよりも高速に転送処理を行えるよう VXLAN の通信を処理する DPDK アプリを書きました。
以下のような特徴を持ちます。

+ 物理 NIC ひとつに対応する仮想 NIC をひとつ作成し通常の NIC と同じように IP アドレスを設定したりルーティングの設定をしたりできる
+ Linux カーネル側で行ったルーティングやブリッジングの設定を Netlink で捕捉し物理 NIC で受信したパケットを DPDK アプリ内で全て処理できる時はそのまま処理し、できないものは仮想 NIC に流し込み Linux カーネルに処理を任せる
+ 自分宛のパケットは全て仮想 NIC を通して Linux カーネル側へ届く

注意事項として、この DPDK アプリは仮想 NIC 側に設定した Netfilter のルールが適用されません。
DPDK アプリが自身で処理することができず Linux カーネル側に処理を投げたものは Netfilter が効くので BGP の接続元を Netfilter で絞ることは可能ですが、 VXLAN の通信は DPDK アプリ内で閉じてしまうためそれを Netfilter で絞ろうとしても期待した動作をしない可能性があります。
(おそらくマルチキャストなどの DPDK アプリで処理できないものは効くがユニキャストの通信は通ってしまうような動作をすることになる。
末尾の "補足というかメモというか" も参照してください。)

性能が特に問題にならないようであればこの DPDK アプリを使わず全て Linux カーネルで処理させることも可能です。

## 使い方

Linux カーネル側で VXLAN のフラグメントに対応させたい時は [ここ](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/) にある Linux カーネルの deb パッケージをインストールしそれで起動します。
もしくは自力で [linux_6.8.0-55.57+evpnvxlan6.2.patch](linux_6.8.0-55.57+evpnvxlan6.2.patch) を適用した Linux カーネル deb パッケージを作成しそれをインストールします。

DPDK アプリで VXLAN を処理させたい時は [ここ](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/) にある gdp という名前の deb パッケージをインストールします。

でもその前に DPDK アプリが必要とする dpdk 関連の deb パッケージをインストールする必要があります。
`apt install dpdk` を実行しそれらをインストールしてから gdp をインストールしてください。

dpdk パッケージに加え、使いたい NIC の PMD(Poll Mode Driver) もインストールする必要があります。
Ubuntu では `librte-net-(NIC 名)24` といった名前で PMD のパッケージが用意されています。
例えば Intel の igc ドライバで動作する NIC を利用したいときは `apt install librte-net-igc24` で igc 用の PMD をインストールしておきます。

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
とりあえずこのままで問題ないと思います。

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

最後に FRRouting の deb パッケージを [ここ](https://www.ginzado.ne.jp/~m-asama/evpnvxlan6/) にあるものに差し替えます。
一旦 `apt install frr` で公式の frr とその依存 deb パッケージをインストールしてから `dpkg -i` で差し替えるのが簡単だと思います。

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

あとよくわかりませんが以下のコマンドを入れないと BGP のパケットが一切出て行かない場合があるようです。

```
ipv6 nht resolve-via-default
```

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

FRRouting の詳しい設定は [こちら](https://docs.frrouting.org/en/latest/evpn.html) を参照してください。

ちゃんと動けばこんな感じになると思います。

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

送信元がどこからでも VNI が一致してしまっていたら Ethernet フレームを受け付けてしまうことになるような気がするんだけどまずくないか？？
めんどくさいのは DPDK アプリ側は Netfilter のフィルタが効かないのでやるとしたら Route Type 3(Inclusive Multicast Ethernet Tag Route) 受け取った VTEP 以外からの VXLAN パケットを受け付けないとかか。

DPDK アプリのソースコードを一般に公開することは現時点では考えていません。
が、物理的に一度でもあったことがあるような方であれば GitHub アカウントを教えてもらえれば参照権限つけます。
みてみたいという方は X の DM ででも連絡ください。

何かおかしな動きをするのに気づいた方はここでイシューをあげていただければ可能であれば対応すると思います。
