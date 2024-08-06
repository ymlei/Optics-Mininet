import random
from OpticalToolbox import BaseNetwork

class MyNetwork(BaseNetwork):
    def routing_direct(self, src, dst, time_slice):
        return self.earliest_path(src, dst, time_slice, hop_limit=1)
    
if __name__ == "__main__":
    root=""
    net = MyNetwork(name="my_network",
                    ocs_sw_path=f"{root}/openoptics-mininet/behavioral-model/targets/optical_switch/optical_switch",
                    ocs_json_path=f"{root}/openoptics-mininet/p4/ocs/ocs.json",
                    ocs_cli_path=f"{root}/openoptics-mininet/behavioral-model/targets/simple_switch/runtime_CLI",
                    tor_sw_path=f"{root}/openoptics-mininet/behavioral-model/targets/tor_switch/tor_switch",
                    tor_json_path=f"{root}/openoptics-mininet/p4/tor/tor.json",
                    tor_cli_path=f"{root}/openoptics-mininet/behavioral-model/targets/simple_switch/runtime_CLI",
                    use_webserver=False)
    #net.topology_random(tor_num = 8)
    net.round_robin(tor_num=8, port_num=1)
    # net.topology_random(tor_num = 8, num_hosts=[8, 1, 9, 1, 3, 6, 2, 4])
    # net.draw_topo()

    net.routing(routing_func = net.routing_direct)
    net.entries(lookup_type="SOURCE")
    
    # net.start(mode="Testbed")
    net.start(mode="Mininet")
