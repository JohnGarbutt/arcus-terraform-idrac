#!/usr/bin/env python3

import pprint
import sys

import openstack
openstack.enable_logging(True, stream=sys.stdout)

def find_idrac_ports(conn):
    return [{
            "name": raw_port["name"],
            "mac": raw_port["mac_address"],
            "ip": raw_port["fixed_ips"][0]["ip_address"],
            "rack": [tag for tag in raw_port["tags"] if "DR" in tag][0],
            "datacentre": [tag for tag in raw_port["tags"] if "DC" in tag][0],
        }
        for raw_port in conn.network.ports(tags="iDRAC")]


def find_baremetal_servers(conn):
    return list(conn.baremetal.nodes())

conn = openstack.connection.from_config(cloud="arcus", debug=True)
idracs = find_idrac_ports(conn)
pprint.pprint(find_baremetal_servers(conn))

print(len(idracs))
idrac = idracs[0]
pprint.pprint(idrac)

new_node = conn.baremetal.create_node(name=idrac["name"], driver="ipmi",
                                      driver_info={"ipmi_address": idrac["ip"]},
                                      extra={"rack": idrac["rack"], "datacentre": idrac["datacentre"]},
                                      retry_on_conflict=False,
                                      expected_provision_state="enroll")

pprint.pprint(new_node)
