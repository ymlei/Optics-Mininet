/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;

const bit<16> TYPE_SOURCE_ROUTING = 0x100;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

typedef bit<8>  tor_t;
typedef bit<8>  ts_t;
typedef bit<8>  port_t;
typedef bit<8>  flag_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

header source_routing_t {
    flag_t valid_flag_1;
    ts_t send_time_slice_1;
    port_t send_port_1;

    flag_t valid_flag_2;
    ts_t send_time_slice_2;
    port_t send_port_2;

    flag_t valid_flag_3;
    ts_t send_time_slice_3;
    port_t send_port_3;

    flag_t valid_flag_4;
    ts_t send_time_slice_4;
    port_t send_port_4;

    flag_t valid_flag_5;
    ts_t send_time_slice_5;
    port_t send_port_5;
}

header time_flow_entry_t {
    flag_t valid_flag;
    ts_t send_time_slice;
    port_t send_port;
}

struct metadata {
    ts_t send_time_slice;
    time_flow_entry_t time_flow_entry;
	bit<1> intermediateForward;
}

struct headers {
    ethernet_t   ethernet;
    source_routing_t ssrr;
    ipv4_t       ipv4;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {

        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType){
            TYPE_IPV4: ipv4;
            TYPE_SOURCE_ROUTING: time_flow;
            default: accept;

        }

    }

    state ipv4 {

        packet.extract(hdr.ipv4);
        transition accept;
    }

    state time_flow {

        packet.extract(meta.time_flow_entry);
        transition select(meta.time_flow_entry.valid_flag) {
            0   :   extract_remaining_ssrr; // pending ssrr entry
            1   :   accept; // valid ssrr entry
            255 :   accept; // end of ssrr entry
        }
    }

    state extract_remaining_ssrr {

        packet.extract(meta.time_flow_entry);
        transition select(meta.time_flow_entry.valid_flag) {
            0   :   extract_remaining_ssrr_1;
            255 :   accept;
        }
    }

    state extract_remaining_ssrr_1 {

        packet.extract(meta.time_flow_entry);
        transition select(meta.time_flow_entry.valid_flag) {
            0   :   extract_remaining_ssrr_2;
            255 :   accept;
        }
    }

    state extract_remaining_ssrr_2 {

        packet.extract(meta.time_flow_entry);
        transition select(meta.time_flow_entry.valid_flag) {
            0   :   extract_remaining_ssrr_3;
            255 :   accept;
        }
    }

    state extract_remaining_ssrr_3 {

        packet.extract(meta.time_flow_entry);
        transition select(meta.time_flow_entry.valid_flag) {
            0   :   extract_remaining_ssrr_4;
            255 :   accept;
        }
    }

    state extract_remaining_ssrr_4 {

        packet.extract(meta.time_flow_entry);
        transition select(meta.time_flow_entry.valid_flag) {
            255 :   accept;
        }
    }

}


/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    bit<8> arrival_time_slice;
    tor_t dst_tor = 127;

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action ts_to_slice() {
        // target tor_switch reuses ingress_global_timestamp as time slice.
        arrival_time_slice = (bit<8>)standard_metadata.ingress_global_timestamp;
    }

    action write_dst(tor_t dst_tor_in) {
        dst_tor = dst_tor_in;
    }

    table ip_to_dst_tor {
        key = {
            hdr.ipv4.dstAddr   : exact;
        }
        actions = {
            write_dst;
        }
        size = 512;
    }

    action to_calendar_q(ts_t send_time_slice, bit<9> egress_port) {
        meta.send_time_slice = send_time_slice;
        standard_metadata.egress_spec = egress_port;

        hdr.ipv4.ttl = hdr.ipv4.ttl -1;
    }

    action write_ssrr_header(
        flag_t valid_flag_0,
        ts_t send_time_slice_0,
        port_t send_port_0,

        flag_t valid_flag_1,
        ts_t send_time_slice_1,
        port_t send_port_1,

        flag_t valid_flag_2,
        ts_t send_time_slice_2,
        port_t send_port_2,

        flag_t valid_flag_3,
        ts_t send_time_slice_3,
        port_t send_port_3,

        flag_t valid_flag_4,
        ts_t send_time_slice_4,
        port_t send_port_4,

        flag_t valid_flag_5,
        ts_t send_time_slice_5,
        port_t send_port_5) {

        meta.time_flow_entry.setValid();
        meta.time_flow_entry.valid_flag = valid_flag_0;
        meta.time_flow_entry.send_time_slice = send_time_slice_0;
        meta.time_flow_entry.send_port = send_port_0;

        hdr.ssrr.setValid();
        hdr.ssrr.valid_flag_1 = valid_flag_1;
        hdr.ssrr.send_time_slice_1 = send_time_slice_1;
        hdr.ssrr.send_port_1 = send_port_1;

        hdr.ssrr.valid_flag_2 = valid_flag_2;
        hdr.ssrr.send_time_slice_2 = send_time_slice_2;
        hdr.ssrr.send_port_2 = send_port_2;

        hdr.ssrr.valid_flag_3 = valid_flag_3;
        hdr.ssrr.send_time_slice_3 = send_time_slice_3;
        hdr.ssrr.send_port_3 = send_port_3;

        hdr.ssrr.valid_flag_4 = valid_flag_4;
        hdr.ssrr.send_time_slice_4 = send_time_slice_4;
        hdr.ssrr.send_port_4 = send_port_4;

        hdr.ssrr.valid_flag_5 = valid_flag_5;
        hdr.ssrr.send_time_slice_5 = send_time_slice_5;
        hdr.ssrr.send_port_5 = send_port_5;
    }
    
    table source_routing_table {
        key = {
            dst_tor            : exact;
            arrival_time_slice : exact;
        }
        actions = {
            write_ssrr_header;
            drop;
            NoAction;
        }
        size = 1024;
        //default_action = ocs_switch(0, 0);
    }

    apply {
		
        if (hdr.ipv4.isValid() && standard_metadata.ingress_port == 2) { //Now port 2 is connected to the host
            //Add source routing table

		    meta.intermediateForward = 0;
            ts_to_slice();
            ip_to_dst_tor.apply();
            if(source_routing_table.apply().hit) {
                hdr.ethernet.etherType = TYPE_SOURCE_ROUTING;
            }
		  
		}

        if (meta.time_flow_entry.valid_flag == 1) { // Source routing not ended. To calendar q.

            to_calendar_q(send_time_slice = meta.time_flow_entry.send_time_slice,
                egress_port = (bit<9>)meta.time_flow_entry.send_port);

        } else if (meta.time_flow_entry.valid_flag == 255){ // end of source routing. To host, probably

            hdr.ethernet.etherType = TYPE_IPV4;
            meta.intermediateForward = 1;
            standard_metadata.egress_spec = 2;

        }


    }//End of ingress
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    counter(512, CounterType.packets_and_bytes) port_counter;

    apply {
        port_counter.count((bit<32>)standard_metadata.egress_port);
    }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
     apply {
    update_checksum(
        hdr.ipv4.isValid(),
            { hdr.ipv4.version,
          hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}


/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {

        //parsed headers have to be added again into the packet.
        packet.emit(hdr);

    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

//switch architecture
V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
