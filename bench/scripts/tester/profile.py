
from scapy.all import Ether, IP, IPv6, IPv6ExtHdrFragment, UDP, VXLAN

from trex_stl_lib.api import *

class Vxlan6Profile(object):

    def __init__(self):
        self.table = {
                'imix': [
                    { 'size':   60, 'pps': 28, 'isg': 0.0, },
                    { 'size':  590, 'pps': 16, 'isg': 1.0, },
                    { 'size': 1514, 'pps':  4, 'isg': 2.0, },
                    #{ 'size': 1276, 'pps':  4, 'isg': 2.0, },
                ],
                'udp64b': [
                    { 'size':   60, 'pps':  1, 'isg': 0.0, },
                ],
                'udp128b': [
                    { 'size':  124, 'pps':  1, 'isg': 0.0, },
                ],
                'udp256b': [
                    { 'size':  252, 'pps':  1, 'isg': 0.0, },
                ],
                'udp512b': [
                    { 'size':  508, 'pps':  1, 'isg': 0.0, },
                ],
                'udp1024b': [
                    { 'size': 1020, 'pps':  1, 'isg': 0.0, },
                ],
                'udp1280b': [
                    { 'size': 1276, 'pps':  1, 'isg': 0.0, },
                ],
                'udp1518b': [
                    { 'size': 1514, 'pps':  1, 'isg': 0.0, },
                ],
        }

    def create_stream(self, direction, size, pps, isg, vm):
        mode = STLTXCont(pps = pps)
        base_pkt = None
        pad = None
        packets = []
        if direction == 0 and size == 1514:
            # decap 方向の udp1518b は UDP チェックサム値などをハードコードする。
            # MAC アドレスなどを実際の環境に置き換える際は UDP チェックサム値も再計算する必要がある。
            vm.add_cmd(STLVmFlowVar(name='fragid',size=4,min_value=0,max_value=0xffffffff,op='random'))
            vm.add_cmd(STLVmWrFlowVar(fv_name='fragid',pkt_offset='IPv6ExtHdrFragment.id'))
            base_pkt  = Ether(dst='a8:b8:e0:05:97:d5')
            base_pkt /= IPv6(src='2001:db8:0:1::1', dst='2001:db8:0:1::2')
            base_pkt /= IPv6ExtHdrFragment(nh=17,offset=181)
            pad = 82 * 'x'
            packets += [STLPktBuilder(pkt = base_pkt/pad, vm = vm)]
            base_pkt  = Ether(dst='a8:b8:e0:05:97:d5')
            base_pkt /= IPv6(src='2001:db8:0:1::1', dst='2001:db8:0:1::2')
            base_pkt /= IPv6ExtHdrFragment(nh=17,m=1)
            base_pkt /= UDP(sport=48642,dport=4789,chksum=0x10a2,len=1530)
            base_pkt /= VXLAN(vni=550,flags=8)
            base_pkt /= Ether(src='fe:54:00:aa:bb:cc', dst='a8:b8:e0:05:97:76')
            base_pkt /= IP(src='169.254.0.1', dst='169.254.0.2', chksum=0x2111, len=1500)
            base_pkt /= UDP(sport=49152,dport=9,chksum=0x85fa,len=1480)
            pad = 1390 * 'x'
            packets += [STLPktBuilder(pkt = base_pkt/pad, vm = vm)]
        elif direction == 0:
            base_pkt  = Ether(dst='a8:b8:e0:05:97:d5')
            base_pkt /= IPv6(src='2001:db8:0:1::1', dst='2001:db8:0:1::2')
            base_pkt /= UDP(sport=49152,dport=4789)
            base_pkt /= VXLAN(vni=550,flags=8)
            base_pkt /= Ether(src='fe:54:00:aa:bb:cc', dst='a8:b8:e0:05:97:76')
            base_pkt /= IP(src='169.254.0.1', dst='169.254.0.2')
            base_pkt /= UDP(sport=49152,dport=9)
            pad = max(0, 14 + 40 + 8 + 8 + size - len(base_pkt)) * 'x'
            packets += [STLPktBuilder(pkt = base_pkt/pad, vm = vm)]
        else:
            base_pkt  = Ether(src='a8:b8:e0:05:97:76', dst='fe:54:00:aa:bb:cc')
            base_pkt /= IP(src='169.254.0.2', dst='169.254.0.1')
            base_pkt /= UDP(sport=49152,dport=9)
            pad = max(0, size - len(base_pkt)) * 'x'
            packets += [STLPktBuilder(pkt = base_pkt/pad, vm = vm)]
        if len(packets) > 1:
            return [
                STLStream(isg = isg, packet = packets[0], mode = mode),
                STLStream(isg = isg, packet = packets[1], mode = mode),
            ]
        else:
            return [STLStream(isg = isg, packet = packets[0], mode = mode)]

    def get_streams(self, direction, base, count, table_name, **kwargs):
        vm = STLScVmRaw()
        if direction == 0:
            pass
        else:
            pass
        #vm.fix_chksum()
        streams = []
        for x in self.table[table_name]:
            streams += self.create_stream(direction, x['size'], x['pps'], x['isg'], vm)
        return streams

def register():
    return Vxlan6Profile()
