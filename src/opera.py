from .OpticalToolbox import BaseNetwork

if __name__ == "__main__":
    net = BaseNetwork("opera")
    net.opera(tor_num = 8, upper_link = 2)
    net.routing(net.routing_opera)
    net.start(mode = "Testbed")