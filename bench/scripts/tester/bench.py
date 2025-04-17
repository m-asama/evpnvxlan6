import sys
sys.path += ['/opt/trex/v3.06/automation/trex_control_plane/interactive']

from trex.stl.api import *

import time
import json
from pprint import pprint
import argparse

def init_result():
    result = {
        'dir_0_opackets': 0,
        'dir_0_ipackets': 0,
        'dir_1_opackets': 0,
        'dir_1_ipackets': 0,
        'dir_0_obytes':   0,
        'dir_0_ibytes':   0,
        'dir_1_obytes':   0,
        'dir_1_ibytes':   0,
        'dir_0_oerrors':  0,
        'dir_0_ierrors':  0,
        'dir_1_oerrors':  0,
        'dir_1_ierrors':  0,
        'lost_0':         0,
        'lost_1':         0,
        'elapsed':        0,
    }
    return result

def vxlan6_test(mult, duration, table_name, direction, base, count):

    result = init_result()

    c = STLClient(server = '127.0.0.1')

    try:
        c.connect()
        c.reset()

        dir_0 = [0]
        dir_1 = [1]

        profile0 = STLProfile.load_py('profile.py', direction = 0, base = base, count = count, table_name = table_name)
        streams0 = profile0.get_streams()

        profile1 = STLProfile.load_py('profile.py', direction = 1, base = base, count = count, table_name = table_name)
        streams1 = profile1.get_streams()

        c.add_streams(streams0, ports = dir_0)
        c.add_streams(streams1, ports = dir_1)

        c.start(ports = (dir_0 + dir_1), mult = '1kpps', duration = 3, total = True)
        c.wait_on_traffic(ports = (dir_0 + dir_1))

        time.sleep(1)

        c.clear_stats()

        ports = []
        if direction == 'decap' or direction == 'both':
            ports += dir_0
        if direction == 'encap' or direction == 'both':
            ports += dir_1
        bt = time.time()
        c.start(ports = ports, mult = mult, force = True, duration = duration, total = False)
        c.wait_on_traffic(ports = ports)
        et = time.time()

        time.sleep(1)

        stats = c.get_stats()

        result['dir_0_opackets'] = stats[0]["opackets"]
        result['dir_0_ipackets'] = stats[0]["ipackets"]
        result['dir_1_opackets'] = stats[1]["opackets"]
        result['dir_1_ipackets'] = stats[1]["ipackets"]
        result['dir_0_obytes']   = stats[0]["obytes"]
        result['dir_0_ibytes']   = stats[0]["ibytes"]
        result['dir_1_obytes']   = stats[1]["obytes"]
        result['dir_1_ibytes']   = stats[1]["ibytes"]
        result['dir_0_oerrors']  = stats[0]["oerrors"]
        result['dir_0_ierrors']  = stats[0]["ierrors"]
        result['dir_1_oerrors']  = stats[1]["oerrors"]
        result['dir_1_ierrors']  = stats[1]["ierrors"]
        result['lost_0']         = result['dir_0_opackets'] - result['dir_1_ipackets']
        result['lost_1']         = result['dir_1_opackets'] - result['dir_0_ipackets']
        result['elapsed']        = et - bt

        if c.get_warnings():
            print("\n\n*** test had warnings ****\n\n")
            for w in c.get_warnings():
                print(w)

    except STLError as e:
        print(e)
        sys.exit(1)

    finally:
        c.disconnect()

    return result

def print_header():
    print("table_name,direction,base,count,pps,dir_0_opackets,dir_0_ipackets,dir_1_opackets,dir_1_ipackets,dir_0_obytes,dir_0_ibytes,dir_1_obytes,dir_1_ibytes,dir_0_oerrors,dir_0_ierrors,dir_1_oerrors,dir_1_ierrors,lost_0,lost_1,elapsed,")

def print_result(table_name, direction, base, count, pps, result):
    if not result:
        result = init_result()
    print("{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11},{12},{13},{14},{15},{16},{17},{18},{19},".format(
        table_name,
        direction,
        base,
        count,
        pps,
        result['dir_0_opackets'],
        result['dir_0_ipackets'],
        result['dir_1_opackets'],
        result['dir_1_ipackets'],
        result['dir_0_obytes'],
        result['dir_0_ibytes'],
        result['dir_1_obytes'],
        result['dir_1_ibytes'],
        result['dir_0_oerrors'],
        result['dir_0_ierrors'],
        result['dir_1_oerrors'],
        result['dir_1_ierrors'],
        result['lost_0'],
        result['lost_1'],
        result['elapsed'],
    ))

parser = argparse.ArgumentParser(description="TRex Stateless for VXLAN6")
parser.add_argument('-c', '--count',
                    dest='count',
                    help='Max instance',
                    default=0,
                    type = int)
args = parser.parse_args()

if args.count == 0:
    exit

init_pps_table = {
    'imix':     10000000000.0 / (( 362 + 20 + 14 + 40 + 8 + 8) * 8),
    'udp64b':   10000000000.0 / ((  64 + 20 + 14 + 40 + 8 + 8) * 8),
    'udp128b':  10000000000.0 / (( 128 + 20 + 14 + 40 + 8 + 8) * 8),
    'udp256b':  10000000000.0 / (( 256 + 20 + 14 + 40 + 8 + 8) * 8),
    'udp512b':  10000000000.0 / (( 512 + 20 + 14 + 40 + 8 + 8) * 8),
    'udp1024b': 10000000000.0 / ((1024 + 20 + 14 + 40 + 8 + 8) * 8),
    'udp1280b': 10000000000.0 / ((1280 + 20 + 14 + 40 + 8 + 8) * 8),
    'udp1518b': 10000000000.0 / ((1518 + 20 + 14 + 40 + 8 + 8) * 8),
}

table_names = [
    'imix',
    'udp64b',
    'udp128b',
    'udp256b',
    'udp512b',
    'udp1024b',
    'udp1280b',
    'udp1518b',
]
directions = [
    'encap',
    'decap',
    'both',
]
#basecounts = [
#    {'base':   0, 'count':    1},
#    {'base':   0, 'count':    4},
#    {'base':   0, 'count':   16},
#    {'base':   0, 'count':   64},
#    {'base':   0, 'count':  256},
#    {'base':   0, 'count': 1020},
#    {'base': 764, 'count':  256},
#]

duration = 30
#iteration = 2
iteration = 15

#                'imix': [
#                    { 'size':   60, 'pps': 28, 'isg': 0.0, },
#                    { 'size':  590, 'pps': 16, 'isg': 1.0, },
#                    { 'size': 1514, 'pps':  4, 'isg': 2.0, },
def test_pass(table_name, direction, pps, duration, result):
    if result['elapsed'] >= duration + 0.05:
        return False
    if table_name == 'imix':
        # imix の場合 64b:594b:1518b が厳密に 7:4:1 にならないようでどうしても数十パケット誤差が生ずるのでそれを考慮。
        if direction == 'both' or direction == 'encap':
            if result['dir_0_ipackets'] < result['dir_1_opackets'] * 1.08333333333333 - (pps * 0.00003):
                return False
        if direction == 'both' or direction == 'decap':
            if result['dir_1_ipackets'] < result['dir_0_opackets'] / 1.08333333333333 - (pps * 0.00003):
                return False
    elif table_name == 'udp1518b':
        if direction == 'both' or direction == 'encap':
            if result['dir_0_ipackets'] != result['dir_1_opackets'] * 2:
                return False
        if direction == 'both' or direction == 'decap':
            if result['dir_1_ipackets'] * 2 != result['dir_0_opackets']:
                return False
    else:
        if result['lost_0'] != 0 or result['lost_1'] != 0:
            return False
    return True

print_header()
best_results = []
for table_name in table_names:
#    for basecount in basecounts:
#        if basecount['base'] + basecount['count'] > args.count:
#            continue
    for direction in directions:
        last_fail_pps = init_pps_table[table_name] * 2
        last_pass_pps = 0
        last_result = None
        pps = init_pps_table[table_name]
        for i in range(iteration):
            result = vxlan6_test("%dpps"%pps, duration, table_name, direction, 0, 1)
            print_result(table_name, direction, 0, 1, pps, result)
            if test_pass(table_name, direction, pps, duration, result):
                if pps > last_pass_pps:
                    last_pass_pps = pps
                    last_result = result
            else:
                result = vxlan6_test("%dpps"%pps, duration, table_name, direction, 0, 1)
                print_result(table_name, direction, 0, 1, pps, result)
                if test_pass(table_name, direction, pps, duration, result):
                    if pps > last_pass_pps:
                        last_pass_pps = pps
                        last_result = result
                else:
                    if pps < last_fail_pps:
                        last_fail_pps = pps
            pps = (last_fail_pps + last_pass_pps) / 2
            time.sleep(10)
        best_result = {
            'table_name': table_name,
            'direction':  direction,
            'base':       0,
            'count':      1,
            'pps':        last_pass_pps,
            'result':     last_result,
        }
        best_results += [best_result]

print_header()
for best_result in best_results:
    print_result(
        best_result['table_name'],
        best_result['direction'],
        best_result['base'],
        best_result['count'],
        best_result['pps'],
        best_result['result'],
    )
