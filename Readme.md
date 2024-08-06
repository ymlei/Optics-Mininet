# Optics-Mininet

Optics-Mininet is an open-source, general framework for realizing different optical data center network architectures in a plug-and-play manner. With Optics-Mininet, users can realize optical DCNs in a full software emulation using BMv2 software switches and Mininet network emulator. A Tofiino-based testbed version will be open sourced in the future.

## Installation

### Building with VS Code Dev Container

This repository comes pre-configured with a Visual Studio Code Development Container that includes all necessary dependencies for building and testing. With Docker and the VS Code Dev Containers extension installed, simply press Ctrl+Shift+P in your VS Code and run the “Dev Containers: Reopen in Container” command to open the repository inside the container. The build process takes around ten minutes. After that, Optics-Mininet is ready to go.

### Building with Docker

We also provide a Dockerfile as a quick and easy way to get Optics-Mininet up and running if you prefer command line. Simply run the following:
```
docker build -t Optics-Mininet .
docker run --privileged -i -t Optics-Mininet /bin/bash
```

### Building Optics-Mininet from scratch

[BMv2](https://github.com/p4lang/behavioral-model) is the P4-programmable reference software switch. Optics-Mininet contains two custom BMv2 targets in the `targets/` directory, and their accompanying compiled p4 files in the `p4/` directory. To build BMv2 for Optics-Mininet: 
1. Clone the BMv2 repo and move it into the Optics-Mininet directory
2. Checkout commit 8e183a39b372cb9dc563e9d0cf593323249cd88b of BMv2
3. Copy the `optical_switch` and `tor_switch` target directories into the `behavioral-model/targets/` directory
4. Install BMv2's dependencies, either by manually following the instructions in BMv2's README, or by running the script `behavioral-model/install_deps.sh`
5. Replace `behavioral-model/configure.ac` with `targets/configure.ac`
6. Replace `behavioral-model/targets/Makefile.am` with `targets/Makefile.am`
7. `cd` into `behavioral-model/` and compile BMv2 by running:
```
./autogen.sh && ./configure && make -j8
```
8. Install Optics-Mininet' Python dependencies by navigating to `src/` and running:
```
pip3 install -r requirements.txt
```

## Usage

### Quick Start

Use the following commands to start a customized optical DCN:
```
cd src
python3 mynetwork.py
```
Then you can try ping in your optical DCN,
```
h0 ping h1
h2 ping h3
```

### Defining an Optical DCN with Optics-Mininet' Python Frontend

Optics-Mininet' network API is contained in `src/OpticalToolbox.py`. This file defines a number of useful functions for creating network topologies, populating switch forwarding tables, and visualising topologies, among other things. Every Optics-Mininet network begins with a `BaseNetwork` object:
```python
net = BaseNetwork(name="my_network",
                  ocs_sw_path="/path/to/behavioral-model/targets/optical_switch/optical_switch",
                  ocs_json_path="/path/to/p4/ocs/forwarding_opt.json",
                  ocs_cli_path="/path/to/behavioral-model/targets/optical_switch/oswitch_CLI",
                  tor_sw_path="/path/to/behavioral-model/targets/tor_switch/tor_switch",
                  tor_json_path="/path/to/p4/tor/forwarding_opt.json",
                  tor_cli_path="/path/to/behavioral-model/targets/tor_switch/tswitch_CLI",
                  use_webserver=True)
```
Generate different topologies:
```python
net.topology_random(tor_num=8, num_hosts=[1]*8)
net.round_robin(tor_num=7, num_hosts=[1]*7)
net.opera(tor_num=6, upper_link=2, num_hosts=[1]*6)
# tor_num is the number of ToR switches connnected to the OCS
# num_hosts is a list where element i is the number of hosts connected to ToR switch i
```
Or, manually define your own topology and time slices:
```python
net.connect(tor1=0, port1=0, tor2=3, port2=0, time_slice=5)
```
Define routing:
```python
net.routing(routing_func=net.routing_vlb)
# possible routing_func's are routing_vlb, routing_hoho, routing_opera
net.entries(lookup_type="SOURCE")
# possible lookup_type's are SOURCE and PER_HOP
```
Visualise topology:
```python
net.draw_topo()
```

### Running an Optics-Mininet network

Once you have created a `BaseNetwork` object, and defined its topology and routing, start the network by simply calling `net.start(mode="Mininet")`. Possible modes are `Mininet` and `Testbed`. Now simply run your Python file! Optics-Mininet takes care of all the Mininet configuration steps for you! The full example is in `src/mynetwork.py`.

Starting the network launches a command line interface defined in `src/OpticalCLI.py`. This CLI is an extension of Mininet's CLI, with added support for custom commands to query the number of queued packets in ToR switches and the network's packet loss rate. 

### Using the Optics-Mininet Dashboard

To configure the Optics-Mininet web dashboard, navigate to `src/dashboard` and run:
```
service redis-server start
python3 manage.py makemigrations dashboardapp
python3 manage.py migrate
```
Make sure to set `use_webserver` to true when creating your `BaseNetwork` object. In one terminal start your network. In another terminal run `python3 manage.py runserver 0.0.0.0:8001`. In your web browser, visit http://0.0.0.0:8001 to view the dashboard. The dashboard displays the network topology, along with realtime graphs of network performance served via WebSockets. 

Note: If running Optics-Mininet over ssh, make sure to enable port forwarding by passing `-L8001:0.0.0.0:8001` to ssh.

### MISC

Please run the following command to turn of checksum check before test your network with iperf or other applications which needs checksum correctness.
```
ethtool --offload  eth0  rx off  tx off
ethtool -K eth0 gso off
```