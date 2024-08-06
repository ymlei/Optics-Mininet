from OpticalToolbox import BaseNetwork

if __name__ == "__main__":
    net = BaseNetwork("hoho")
    net.round_robin(tor_num = 8, port_num = 2)
    net.routing(net.routing_hoho)
    net.start(mode = "Testbed")






    