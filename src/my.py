import random
from OpticalToolbox import BaseNetwork

class MyNetwork(BaseNetwork):
    #connect(tor1, port1, tor2, port2, time_slice)
    def topology_random(self, tor_num):
        for slice_id in range(tor_num):
            remaining_tors = list(range(tor_num))
            random.shuffle(remaining_tors)
            while remaining_tors:
                tor1 = remaining_tors.pop()
                tor2 = remaining_tors.pop()
                self.connect(tor1, 0, tor2, 0, slice_id)

    def routing_direct(self, src, dst, time_slice):
        return self.earliest_path(src, dst, time_slice, hop_limit=1)

if __name__ == "__main__":
    net = MyNetwork("my_network")
    net.topology_random(tor_num = 8)
    net.draw_topo()

    paths = net.routing()
    paths = net.routing(net.routing_direct)
    net.entries(paths)

    net.start(mode="Testbed")