#!/usr/bin/env python3
"""
Generates inventory from neutron iDRAC ports

If you have created ports in Neutron to provide iDRAC
with their IPs via DHCP, we can use that information
to build an inventory file.

Note: we provide a terraform script to create those
ports using

Its also possible you have built an inventory file in
a similar format directly from an inventory spreadsheet
or similar. Either way you can use the rest of the ansible
once we have an appropriate inventory.
"""
import json
import sys

import jinja2
import openstack


def get_ports(conn, rack):
    if conn is None:
        return [
            {
                "name": "sv1",
                "mac_address": "mac1",
                "fixed_ips": [{"ip_address": "ip1"}],
                "tags": ["DR06", "DC42"],
            },
            {
                "name": "sv2",
                "mac_address": "mac2",
                "fixed_ips": [{"ip_address": "ip2"}],
                "tags": ["iDRAC", "DR06", "DC42"],
            },
        ]
    tags = f"iDRAC,{rack}"
    return conn.network.ports(tags=tags)


def extract_nodes_from_ports(raw_ports):
    return [{
            "name": raw_port["name"],
            "mac": raw_port["mac_address"],
            "ip": raw_port["fixed_ips"][0]["ip_address"],
            "rack": [tag for tag in raw_port["tags"] if "DR" in tag][0],
            "datacentre": [tag for tag in raw_port["tags"] if "DC" in tag][0],
        }
        for raw_port in raw_ports]


def generate_inventory(nodes, rack):
    template_str = """[{{ rack }}]
{% for node in nodes -%}
{{ node.name }} bmc_address={{ node.ip }} bmc_mac={{ node.mac }}
{% endfor %}

[{{ rack }}:vars]
bmc_type=idrac

[baremetal-compute:children]
{{ rack }}

"""
    env = jinja2.Environment()
    template = env.from_string(template_str)
    return template.render(nodes=nodes, rack=rack)


if __name__ == "__main__":
    openstack.enable_logging(True, stream=sys.stdout)
    try:
        conn = openstack.connection.from_config(
            cloud="arcus", debug=False)
    except openstack.exceptions.ConfigException:
        print("falling back to test data")
        conn = None

    rack = "DR06"
    raw_ports = get_ports(conn, rack)
    nodes = extract_nodes_from_ports(raw_ports)
    print(json.dumps(nodes, indent=2))

    inventory = generate_inventory(nodes, rack)
    with open("inventory", "w") as f:
        f.write(inventory)
