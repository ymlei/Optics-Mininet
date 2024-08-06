import networkx as nx
import matplotlib.pyplot as plt
import json
import os
import sys
import random
import time
import threading

import django
from django.utils import timezone

import utils
from OpticalCLI import OpticalCLI

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.cli import CLI
from mininet.link import TCLink
from p4_mininet import P4Switch, P4Host

from typing import List

class BaseNetwork():
    """
    The base class of optical networks.
    Includes topology and routing.
    """

    def __init__(self, name, ocs_sw_path, ocs_json_path, ocs_cli_path, tor_sw_path, tor_json_path, tor_cli_path, use_webserver=True):
        self.name = name
        self.topo = nx.Graph()
        self.topo_slice = {}
        self.valid_slice = set()
        self.nodes = {}
        self.mininet_topo = None
        self.mininet_net = None
        self.num_hosts = []
        self.ip_to_tor = {}
        self.routing_path = []
        self.ssrr_commands = {}

        self.ocs_sw_path = ocs_sw_path
        self.ocs_json_path = ocs_json_path
        self.ocs_cli_path = ocs_cli_path
        self.tor_sw_path = tor_sw_path
        self.tor_json_path = tor_json_path
        self.tor_cli_path = tor_cli_path

        self.use_webserver = use_webserver
        self.running_db_thread = False
        if self.use_webserver:
            sys.path.append(os.path.join(os.path.dirname(__file__), 'dashboard'))
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
            django.setup()
            self.running_db_thread = True

    def __str__(self) -> str:
        return self.name
    
    def update_db(self):
        from datetime import datetime
        from io import BytesIO
        from django.core.files.base import ContentFile
        from dashboardapp.models import Epochs, Readings, PortReadings
        sys.path.insert(1, '../behavioral-model/targets/tor_switch')
        sys.path.insert(1, '../behavioral-model/tools')
        from tswitch_CLI import TorSwitchAPI
        import runtime_CLI

        import random

        epoch_name = datetime.now().strftime('%d-%m-%Y')
        existing_epochs = Epochs.objects.filter(display_name__startswith=epoch_name)
        if existing_epochs.exists():
            existing_suffixes = [
                int(epoch.display_name[len(epoch_name)+2:-1]) for epoch in existing_epochs 
                if epoch.display_name[len(epoch_name):].startswith(' (') and epoch.display_name.endswith(')')
            ]
            if existing_suffixes:
                next_suffix = max(existing_suffixes) + 1
            else:
                next_suffix = 1
            epoch_name = f"{epoch_name} ({next_suffix})"
        else:
            epoch_name += "(0)"
        
        topology_fig = self.draw_topo()
        buffer = BytesIO()
        topology_fig.savefig(buffer, format='png', dpi=300, bbox_inches='tight')

        content_file = ContentFile(buffer.getvalue())
        current_epoch = Epochs(display_name=epoch_name)
        current_epoch.topo_image.save('graph_slices.png', content_file)
        current_epoch.save()

        from OpticalCLI import get_num_queued_packets, get_num_queued_packets_verbose, get_packet_loss_rate
        
        step_count = 0
        while self.running_db_thread:
            switches = [switch for switch in self.mininet_net.switches if switch.switch_type() != "optical"]
            total_num_queued_packets = 0
            total_packets_recvd = 0
            total_packets_dropped = 0
            for switch in switches:
                device_name = switch.name

                port_queued_packets = get_num_queued_packets_verbose([switch])
                port_readings = []
                num_queued_packets = 0
                for key, reading in port_queued_packets[switch.name].items():
                    if key == "total": continue
                    else:
                        port_readings.append(
                            PortReadings(device_name=device_name,
                                        port_key=key,
                                        num_queued_packets=reading,
                                        timestep=step_count,
                                        epoch=current_epoch)
                        )
                        num_queued_packets += reading
                        total_num_queued_packets += reading
                PortReadings.objects.bulk_create(port_readings)

                packet_loss_rate_values = get_packet_loss_rate([switch])
                packet_loss_rate = packet_loss_rate_values[2]
                total_packets_recvd += packet_loss_rate_values[0]
                total_packets_dropped += packet_loss_rate_values[1]
                switch_reading = Readings(device_name=device_name, 
                                          num_queued_packets=num_queued_packets, 
                                          packet_loss_rate=packet_loss_rate, 
                                          timestep=step_count, 
                                          epoch=current_epoch
                                         )
                switch_reading.save()

            if total_packets_recvd == 0: total_packet_loss_rate = 0.0
            else: total_packet_loss_rate = total_packets_dropped / total_packets_recvd
            total_reading = Readings(device_name='total', 
                                     num_queued_packets=total_num_queued_packets, 
                                     packet_loss_rate=total_packet_loss_rate, 
                                     timestep=step_count, 
                                     epoch=current_epoch
                                    )
            total_reading.save()
            step_count += 1

            for _ in range(10):
                if not self.running_db_thread:
                    break
                time.sleep(0.1)

    def start(self, mode):
        supported_modes = ["Mininet", "Testbed"]
        if mode not in supported_modes:
            assert False, f"Only support modes {supported_modes}"

        if mode == "Testbed":
            assert False, "Not implemented"
        
        self.setup(mode)
        print(f"Started network {self.name} at {mode}.")

        if self.use_webserver:
            db_thread = threading.Thread(target=self.update_db)
            db_thread.start()

        OpticalCLI(self.mininet_net)

        if self.use_webserver:
            self.running_db_thread = False
            db_thread.join()
        self.mininet_net.stop()
    
    def setup(self, mode):
        if mode == "Testbed":
            self.setup_testbed()
        elif mode == "Mininet":
            self.setup_mininet()
        print(f"Initialized {mode}.")
    
    def setup_mininet(self):
        config = self.topo_to_dict()
        self.mininet_topo = Topo()
        thrift_port = 9090 # default thrift port
        # Add switches to mininet topology, store metadata in self.nodes dictionary
        s1 = self.mininet_topo.addSwitch('s1',
                                         sw_path=self.ocs_sw_path,
                                         json_path=self.ocs_json_path,
                                         thrift_port=thrift_port,
                                         pcap_dump=True,
                                         nb_time_slice=self.slice_num(),
                                         cls=P4Switch)
        self.nodes['s1'] = {"port_idx": None, "commands": "", "thrift_port": thrift_port}
        thrift_port += 1
        host_name_counter = 0
        for tor_id in range(self.topo.number_of_nodes()):
            tor_switch = self.mininet_topo.addSwitch('tor' + str(tor_id),
                                                     sw_path=self.tor_sw_path,
                                                     json_path=self.tor_json_path,
                                                     thrift_port=thrift_port,
                                                     pcap_dump=True,
                                                     calendar_queues=self.slice_num(),
                                                     cls=P4Switch)
            self.mininet_topo.addLink(s1, tor_switch)
            self.nodes['tor' + str(tor_id)] = {"tor_id": tor_id, "commands": "", "thrift_port": thrift_port}
            thrift_port += 1

            # Connect hosts to ToR switches
            for _ in range(self.num_hosts[tor_id]):
                ip = f'10.0.{host_name_counter}.1'
                mac = '00:aa:bb:00:00:%02x' % host_name_counter
                host = self.mininet_topo.addHost('h' + str(host_name_counter), ip=ip, mac=mac)
                print(f"h{host_name_counter}: {ip} {mac}")
                self.mininet_topo.addLink(host, tor_switch, cls=TCLink, bw=1000, loss=0)
                self.ip_to_tor[ip] = tor_id
                host_name_counter += 1
        
        for link in self.mininet_topo.links(withKeys=True, withInfo=True):
            print(link)
        
        self.mininet_net = Mininet(self.mininet_topo, host=P4Host, switch=P4Switch, controller=None)
        self.mininet_net.staticArp()
        self.mininet_net.start()
        #print(self.nodes)
        # populate ARP tables
        host_name_counter = 0
        for n in range(sum(self.num_hosts)):
            h = self.mininet_net.get(f"h{host_name_counter}")
            ip = f'10.0.{host_name_counter}.1'
            mac = '00:aa:bb:00:00:%02x' % host_name_counter
            h.setARP(ip, mac)
            host_name_counter += 1
        
        self.setup_ocs(config)
        self.setup_tors()

    def setup_testbed(self):
        pass
    
    def setup_ocs(self, dict_config):
        # Generate commands for optical and tor switches for filling their forwarding tables
        ocs_commands = utils.gen_ocs_commands(dict_config['s1']["slices"])
        self.nodes['s1']["commands"] = ocs_commands
        # print(f"ocs commands: {ocs_commands}")

        # Run commands on switches
        for switch in self.mininet_net.switches:
            print(f"Populating {switch.name}\'s tables...")
            with open(f'temp-commands.txt', 'w') as file: file.write(self.nodes[switch.name]['commands'])
            #with open(f'{switch.name}.txt', 'w') as file: file.write(self.nodes[switch.name]['commands'])
            if switch.name == 's1':
                switch.cmd(f"{self.ocs_cli_path} --thrift-port {self.nodes[switch.name]['thrift_port']} < {os.path.abspath('temp-commands.txt')}")
                #switch.cmd(f"{self.ocs_cli_path} --thrift-port {self.nodes[switch.name]['thrift_port']} < {os.path.abspath(f'{switch.name}.txt')}")
            else:
                switch.cmd(f"{self.tor_cli_path} --thrift-port {self.nodes[switch.name]['thrift_port']} < {os.path.abspath('temp-commands.txt')}")
                #switch.cmd(f"{self.tor_cli_path} --thrift-port {self.nodes[switch.name]['thrift_port']} < {os.path.abspath(f'{switch.name}.txt')}")
        os.remove('temp-commands.txt')

    def setup_tors(self):

        ip_to_dst_commands = utils.gen_commands_ip_to_dst(self.ip_to_tor)


        for switch in self.mininet_net.switches:
            if switch.name == 's1':
                continue
            elif switch.name.startswith("tor"):
                tor_id = int(switch.name[3:])

                utils.load_table(cmd = switch.cmd,
                                cli_path = self.tor_cli_path,
                                thrift_port = self.nodes[switch.name]['thrift_port'],
                                table_commands = ip_to_dst_commands,
                                print_flag=True,
                                save_flag = False
                                )

                utils.load_table(cmd = switch.cmd,
                                cli_path = self.tor_cli_path,
                                thrift_port = self.nodes[switch.name]['thrift_port'],
                                table_commands = self.ssrr_commands[tor_id],
                                print_flag=True,
                                save_flag = False
                                )
            
    #Utils

    def topo_to_dict(self):
        dict_representation = dict({"s1": {"slices": []}})
        for _, graph in self.topo_slice.items():
            dict_representation["s1"]["slices"].append([t[:-1] for t in nx.to_edgelist(graph)])
        #for i in range(0, len(self.topo_slice) + 1):
        #    a = (i // (256 ** 2)) % 256
        #    b = (i // 256) % 256
        #    c = i % 256
        #    dict_representation["s1"]["port_to_ip"][i] = [f"10.{a}.{c}.{b+1}"]
        return dict_representation

    def slice_num(self):
        return len(self.valid_slice)
    
    def tor_num(self):
        return len(self.topo.nodes())
    
    #Topology-related

    def connect(self, tor1, tor2, time_slice):

        #if tor1 == tor2:
        #    return

        self.topo.add_edge(tor1, tor2, ts = time_slice)
        if time_slice not in self.valid_slice:
            self.valid_slice.add(time_slice)
        
        if time_slice not in self.topo_slice.keys():
            self.topo_slice[time_slice] = nx.Graph()
        self.topo_slice[time_slice].add_edge(tor1, tor2)

    def connect(self, tor1, port1, tor2, port2, time_slice):

        if tor1 == tor2:
            return

        self.topo.add_edge(tor1, tor2, ts = time_slice)
        if time_slice not in self.valid_slice:
            self.valid_slice.add(time_slice)
        
        if time_slice not in self.topo_slice.keys():
            self.topo_slice[time_slice] = nx.Graph()
        self.topo_slice[time_slice].add_edge(tor1, tor2)

    def topology_random(self, tor_num, num_hosts = []):
        if len(num_hosts) == 0:
            num_hosts = [1] * tor_num
        #print(num_hosts)
        assert len(num_hosts) == tor_num
        self.num_hosts = num_hosts

        for slice_id in range(tor_num):
            remaining_tors = list(range(tor_num))
            random.shuffle(remaining_tors)
            while remaining_tors:
                tor1 = remaining_tors.pop()
                tor2 = remaining_tors.pop()
                self.connect(tor1, 0, tor2, 0, slice_id)

    def round_robin(self, tor_num, num_hosts = []):
        """Create a round-robin topology with the circle method."""

        assert tor_num % 2 == 0, ""
        tors = list(range(tor_num))

        if len(num_hosts) == 0:
            num_hosts = [1] * tor_num
        assert len(num_hosts) == tor_num
        self.num_hosts = num_hosts

        for slice_id in range(tor_num-1):
            for i in range(tor_num // 2):
                #Set connection rules
                self.connect(tors[i], tors[-i-1], slice_id)
            tors.insert(1, tors.pop(-1))

    def round_robin(self, tor_num, port_num, num_hosts = []):
        assert (tor_num / port_num) % 2 == 0
        group_num = tor_num // port_num

        if len(num_hosts) == 0:
            num_hosts = [1] * tor_num
        assert len(num_hosts) == tor_num
        self.num_hosts = num_hosts
        
        group_tors = list(range(group_num))
        for port_1 in range(port_num):
            for port_2 in range(port_num):
                for slice_id in range(group_num-1):   
                    for i in range(group_num // 2):
                        self.connect(group_tors[i] + port_1 * group_num, port_1,
                                     group_tors[-i - 1] + port_2 * group_num, port_2,
                                     slice_id)
                    group_tors.insert(1, group_tors.pop(-1))
                for i in range(group_num):
                    self.connect(group_tors[i] + port_1 * group_num, port_1,
                                 group_tors[i] + port_2 * group_num, port_2,
                                 time_slice = group_num-1)


    def round_robin_loop(self, tor_num, num_hosts = []):
        """
        Create a round-robin topology with self connection
        for generating multiple upper link schedules.
        """
        assert tor_num % 2 == 0, ""
        tors = list(range(tor_num))

        if len(num_hosts) == 0:
            num_hosts = [1] * tor_num
        assert len(num_hosts) == tor_num
        self.num_hosts = num_hosts

        for slice_id in range(tor_num-1):
            for i in range(tor_num // 2):
                #Set connection rules
                self.connect(tors[i], 0, tors[-i-1], 0, slice_id)
            tors.insert(1, tors.pop(-1))

        for i in range(tor_num):
            self.connect(tors[i], 0, tors[i], 0, time_slice = tor_num-1)

    def opera(self, tor_num, upper_link, num_hosts=[]):
        """Create an Opera topology schedule"""
        if len(num_hosts) == 0:
            num_hosts = [1] * tor_num
        assert len(num_hosts) == tor_num
        self.num_hosts = num_hosts

        self.round_robin(tor_num, upper_link, num_hosts)
        return

        assert (tor_num / upper_link) % 2 == 0, "Incorrect tor num and upper link ratio"
        base_tor_num = tor_num // upper_link
        self.round_robin_loop(base_tor_num, num_hosts)

        ori_edges = list(self.topo.edges(data=True))
        for u,v,d in ori_edges:
            for u_link_id in range(upper_link):
                for v_link_id in range(upper_link):
                    self.connect(u + u_link_id * base_tor_num, u_link_id,
                                 v + v_link_id * base_tor_num, v_link_id,
                                 time_slice = d['ts'])
    
    def set_slice_duration_us(self, duration):
        pass
    
    def get_topo(self):
        return self.topo
    
    def get_topo_slice(self, time_slice : int) -> nx.Graph:
        #print(f"Request slice is {time_slice}")
        return self.topo_slice[time_slice]

        if time_slice not in self.topo_slice.keys():
            self.topo_slice[time_slice] = nx.Graph(
                [ (u,v) for u,v,d in self.topo.edges(data=True) if d
                ['ts'] == time_slice]
            )
        return self.topo_slice[time_slice]
    
    def draw_topo(self):
        pos = nx.circular_layout(sorted(self.topo.nodes))
        fig, axs = plt.subplots(1, self.slice_num())
        for time_slice, ax in enumerate(axs):
            color_map = ["#1E325C" for _ in self.topo.nodes]
            nx.draw(self.get_topo_slice(time_slice),
                    ax = ax,
                    pos = pos,
                    with_labels=True,
                    node_color="#1E325C",
                    font_color="white")
            ax.tick_params(left=True, bottom=True, labelleft=True, labelbottom=True)
            ax.axis('on')
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(f"slice={time_slice}")
        
        fig.set_size_inches(3 * self.slice_num(), 3)
        return fig

    ##########################
        #Routing-related
    ##########################
            
    def make_json(tor_id, tor_tb):
        jsons = []
        table_name = f"tor{tor_id%4}_pipe.Ingress.tb_forwarding_table"
        action = "Ingress.enhqueue.set_send_slice_tor"

        for entry in tor_tb:
            item = {
                "table_name" : table_name,
                "action" : action,
                "key" : {
                    "time_slice" : entry["time_slice"],
                    "dst" : entry["dst"],
                },
                "data" : {
                    "send_slice" : entry["send_slice"],
                    "next_tor" : entry["next_tor"],
                }
            }
            jsons.append(item)
        
        with open(f"tables/tor{tor_id}.json", "w") as outfile:
            json.dump(jsons, outfile, indent=2)

    def save_path(self, src, dst, time_slice, path):
        self.routing_path[src].update({(dst,time_slice) : path})
        #print(f"Save Path ({src}->{dst},{time_slice}): {path}")

    def routing(self, routing_func : callable):
        """Generating routing tables with routing_func"""
        self.routing_path = [{} for src in self.topo_slice[0].nodes()]

        tor_num = self.tor_num()
        slice_num = self.slice_num()
        for src in range(tor_num):
            for dst in range(tor_num):
                if src == dst:
                    continue
                for time_slice in range(slice_num):
                    self.save_path(src, dst, time_slice, routing_func(src, dst, time_slice))
    
    def earliest_direct_conn(self, src, dst, time_slice):
        wait_slice = 0
        while (wait_slice < self.slice_num()):
            current_time_slice = (time_slice + wait_slice) % self.slice_num()
            for edge in self.get_topo_slice(current_time_slice).edges(dst):
                if src in edge:
                    #print(f"edge {edge}")
                    return Path(src, dst, time_slice, [Hop(current_time_slice, 1)])

            wait_slice += 1
        return None

    def earliest_path(self, src, dst, time_slice, hop_limit):
        assert hop_limit == 1
        return self.earliest_direct_conn(src, dst, time_slice)
    
    def routing_direct(self, src, dst, time_slice):
        return self.earliest_path(src, dst, time_slice, hop_limit=1)
        
    def routing_vlb(self, src, dst, time_slice):
        pass
        #Dummy Path
        return f"(*,{time_slice}) -> ({dst},*)"
    
    def routing_hoho(self, src, dst, time_slice):
        pass
    
    def routing_opera(self, src, dst, time_slice):
        pass

    def entries(self, lookup_type = "SOURCE"):
        """
        Generate routing tables based on lookup type.
        lookup_type : "SOURCE" | "PER_HOP"
        """
        if lookup_type == "SOURCE":
            for src in self.topo.nodes():
                self.ssrr_commands[src] = self.generate_source_routing_tables(src)
        elif lookup_type == "PER_HOP":
            print(f"PER_HOP is unsupported for now.")
        else:
            print(f"Unsupported lookup type {lookup_type}")
            exit()

    def generate_source_routing_tables(self, src):
        path = ''
        commands = ''
        print(f"src {src}, path {self.routing_path[src]}")
        for (dst, time_slice), path in self.routing_path[src].items():
            ssrr = path.ssrr_entry()
            commands += f"table_add source_routing_table write_ssrr_header {dst} {time_slice} => {ssrr}\n"
        return commands



class Hop:

    def __init__(self, send_slice = -1, send_port = -1, valid_flag = 1):
        self.valid_flag = valid_flag
        self.send_slice = send_slice
        self.send_port = send_port
    
    def __str__(self):
        return f"send slice: {self.send_slice}, send port: {self.send_port}"
    
    def __repr__(self):
        return f"{self.valid_flag} {self.send_slice} {self.send_port}"
    

class Path:

    ssrr_len = 6

    def __init__(self, src, dst, arrival_ts, ssrr : List[Hop]): ##ssrr is a list of HOP
        self.src = src
        self.dst = dst
        self.arrival_ts = arrival_ts
        self.ssrr = ssrr

    def __str__(self):
        return f"Path ({self.src}->{self.dst},{self.arrival_ts}): {str(self.ssrr)}"
    
    def __repr__(self):
        return f"Path ({self.src}->{self.dst},{self.arrival_ts}): {str(self.ssrr)}"

    def ssrr_entry(self):
        pended_ssrr = self.ssrr + [Hop(valid_flag=0) for _ in range(self.ssrr_len - len(self.ssrr))]
        pended_ssrr[-1].valid_flag = 255 #end flag
        return " ".join(repr(hop) for hop in pended_ssrr)

