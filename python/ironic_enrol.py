#!/usr/bin/env python3

import pprint

import openstack

def find_idrac_ports(conn):
    return [{
            "name": raw_port["name"],
            "mac": raw_port["mac_address"],
            "ip": raw_port["fixed_ips"][0]["ip_address"],
        }
        for raw_port in conn.network.ports(tags="iDRAC")]

conn = openstack.connection.from_config(cloud="arcus")
pprint.pprint(find_idrac_ports(conn))
