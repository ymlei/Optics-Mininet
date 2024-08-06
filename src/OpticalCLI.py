from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import error
import sys
import os
import re

from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.protocol import TMultiplexedProtocol

sys.path.insert(1, '../behavioral-model/targets/tor_switch')
sys.path.insert(1, '../behavioral-model/tools')
from tswitch_CLI import TorSwitchAPI
import runtime_CLI

class OpticalCLI(CLI):
    def __init__(self, mininet, stdin=sys.stdin, script=None, **kwargs):
        self.prompt = "Optics-Mininet> "
        CLI.__init__(self, mininet, stdin, script, **kwargs)
    
    def get_switches_from_line(self, line):
        args = line.split()
        if len(args) == 0:
            switches = self.mn.switches
        else:
            switches = [switch for switch in self.mn.switches if switch.name in args]
        switches = [switch for switch in switches if switch.switch_type() != "optical"]
        return switches

    def do_get_num_queued_packets(self, line):
        switches = self.get_switches_from_line(line)
        num_packets = get_num_queued_packets(switches)
        print(num_packets)
    
    def do_get_num_queued_packets_verbose(self, line):
        switches = self.get_switches_from_line(line)
        num_packets = get_num_queued_packets_verbose(switches)
        print(num_packets)
    
    def do_get_packet_loss_rate(self, line):
        switches = self.get_switches_from_line(line)
        result = get_packet_loss_rate(switches)
        print(result[2])
    
    def do_get_packet_loss_rate_verbose(self, line):
        switches = self.get_switches_from_line(line)
        result = get_packet_loss_rate_verbose(switches)
        print(result)

    def do_test_ping_output(self, line):
        h1 = self.mn.hosts[0]
        h1.popen('ping h2')
        sw = self.mn.get(f"tor_s1_p0")
        print(sw.shell.communicate())

def get_num_queued_packets(switches):
    num_packets = ""
    for switch in switches:
        services = TorSwitchAPI.get_thrift_services()
        switch_client = runtime_CLI.thrift_connect("localhost", switch.thrift_port, services)[0]
        num_packets += switch_client.get_num_queued_packets()
        num_packets += "\n"
    matches = re.findall(r'total:\s*(-?\d+)', num_packets)
    total_num_packets = sum(map(int, matches))
    return total_num_packets

def get_num_queued_packets_verbose(switches):
    num_packets = {}
    for switch in switches:
        services = TorSwitchAPI.get_thrift_services()
        switch_client = runtime_CLI.thrift_connect("localhost", switch.thrift_port, services)[0]
        out = switch_client.get_num_queued_packets()
        # num_packets[switch.name] = out
        num_packets[switch.name] = {}
        for line in out.splitlines():
            match = re.match(r'(\(.*?\)|total):\s*(-?\d+)', line)
            if match:
                key = match.group(1)
                value = int(match.group(2))
                num_packets[switch.name][key] = value
    return num_packets

def get_packet_loss_rate(switches):
    num_pkt_recvd = 0
    num_pkt_dropped = 0
    pattern = r"Received: (?P<received>\d+)\nDropped: (?P<dropped>\d+)"
    for switch in switches:
        services = TorSwitchAPI.get_thrift_services()
        switch_client = runtime_CLI.thrift_connect("localhost", switch.thrift_port, services)[0]
        output = switch_client.get_packet_loss_rate()
        match = re.search(pattern, output)
        if match:
            num_pkt_recvd += int(match.group("received"))
            num_pkt_dropped += int(match.group("dropped"))
    if num_pkt_recvd == 0: loss_rate = 0.0
    else: loss_rate = num_pkt_dropped / num_pkt_recvd
    return [num_pkt_recvd, num_pkt_dropped, loss_rate]

def get_packet_loss_rate_verbose(switches):
    result = ""
    for switch in switches:
        services = TorSwitchAPI.get_thrift_services()
        switch_client = runtime_CLI.thrift_connect("localhost", switch.thrift_port, services)[0]
        output = switch_client.get_packet_loss_rate()
        result += "\n" + switch.name + "\n" + output
    return result