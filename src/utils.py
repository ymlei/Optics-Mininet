import time
import subprocess
import json
import os

def load_table(cmd, cli_path, thrift_port, table_commands, print_flag=False, save_flag=False, save_name="default_name"):

    if save_flag == True:
        with open(f'{save_name}.txt', 'w') as file: 
            file.write(table_commands)
    if print_flag == True:
        print(table_commands)
    
    with open(f'temp-commands.txt', 'w') as file: file.write(table_commands)

    err = cmd(f"{cli_path} --thrift-port {thrift_port} < {os.path.abspath('temp-commands.txt')}")
    #print(err)

    os.remove('temp-commands.txt')

def gen_ocs_commands(slices):
    commands = ""
    commands += "table_set_default ocs_schedule drop\n"
    for slice_id, port_pairs in enumerate(slices):
        for ingress_port, egress_port in port_pairs:
            #ports starts from 1
            ingress_port += 1
            egress_port += 1
            commands += f"table_add ocs_schedule ocs_forward {ingress_port} {slice_id} => {egress_port}\n"
            commands += f"table_add ocs_schedule ocs_forward {egress_port} {slice_id} => {ingress_port}\n"
    return commands

def gen_commands_ip_to_dst(ip_to_tor):
    commands = ""
    for ip, tor_id in ip_to_tor.items():
        commands += f"table_add ip_to_dst_tor write_dst {ip} => {tor_id}\n"
    
    return commands

def gen_tor_commands(tor_id, slices, port_to_ip, num_hosts, offset):
    """
    Old implementation of loading direct routing table entries.
    """
    commands = ""
    #slice_size = int(max_slices / len(slices))
    #commands += f"table_set_default static_config set_static_config {len(slices)} {slice_size} 0 10000 {tor_id}\n"
    # Non-optical network on port 2
    commands += f"table_set_default time_flow_table to_calendar_q {len(slices)} 2\n"
    # For each time slice, register which port is connected to which, and 
    # add an entry to the corresponding tor switch's forwarding table
    for send_time_slice, tor_pairs in enumerate(slices):
        connected_port = None
        for tor_pair in tor_pairs:
            if tor_id in tor_pair:
                if tor_id == tor_pair[0]:
                    connected_port = tor_pair[1]
                else:
                    connected_port = tor_pair[0]
                break
        if connected_port is None:
            break
        ips = port_to_ip[connected_port]
        # Optical network on port 1
        for ip in ips:
            arrival_time_slice = 0 #tbf
            commands += f"table_add time_flow_table to_calendar_q {ip} {arrival_time_slice} => {send_time_slice} 1\n"
    
    for nodes in range(num_hosts):
        for send_time_slice, _ in enumerate(slices):
            commands += f"table_add ocs_schedule ocs_switch 10.0.0.{offset} => {send_time_slice} 0\n"
        offset += 1

    return commands
    