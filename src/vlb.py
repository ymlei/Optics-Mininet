from OpticalToolbox import BaseNetwork

if __name__ == "__main__":
    net = BaseNetwork("vlb")
    net.round_robin(tor_num = 8, port_num = 1)
    net.routing(net.routing_vlb)
    net.start(mode = "Testbed")