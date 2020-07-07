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
    return list(conn.baremetal.nodes(details=True))

conn = openstack.connection.from_config(cloud="arcus", debug=True)
idracs = find_idrac_ports(conn)
print(len(idracs))

baremetal_nodes = find_baremetal_servers(conn)
print(len(baremetal_nodes))

already_created = [node["name"] for node in baremetal_nodes]

new_nodes = []
for idrac in idracs:
    if idrac["name"] not in already_created:
        new_node = conn.baremetal.create_node(
            name=idrac["name"], driver="idrac",
            driver_info={
              "drac_address": idrac["ip"],
              # Starting with default passwords as shipped, updates later
              "drac_password": "calvin",
              "drac_username": "root",
              "redfish_system_id": "/redfish/v1/Systems/System.Embedded.1",
              "redfish_address": idrac["ip"],
              "redfish_password": "calvin",
              "redfish_username": "root",
            },
            boot_interface="ipxe",
            bios_interface="no-bios",
            console_interface="no-console",
            deploy_interface="iscsi",
            inspect_interface="idrac-wsman",
            management_interface="idrac-wsman",
            network_interface="neutron",
            power_interface="idrac-wsman",
            raid_interface="idrac-wsman",
            rescue_interface="agent",
            storage_interface="noop",
            vendor_interface="idrac-wsman",
            extra={
               "rack": idrac["rack"],
               "datacentre": idrac["datacentre"]},
            retry_on_conflict=False,
            provision_state="enroll",
            resource_class="c6420.p8276.m192")
        new_nodes.append(new_node)
        pprint.pprint(new_node)
pprint.pprint(new_nodes)
print(len(new_nodes))

if len(new_nodes) > 0:
    baremetal_nodes = find_baremetal_servers(conn)
print(len(baremetal_nodes))

#
# Now enrolled, lets go to manage
#
move_to_manage = []
for node in baremetal_nodes:
    if node["provision_state"] == "enroll":
        conn.baremetal.set_node_provision_state(node, 'manage')
        move_to_manage.append(node)
if len(move_to_manage) > 0:
    conn.baremetal.wait_for_nodes_provision_state(move_to_manage, 'manageable')

if len(move_to_manage) > 0:
    baremetal_nodes = find_baremetal_servers(conn)

#
# doing out of bound inspection
#
inspecting = []
for node in baremetal_nodes:
    if node["properties"].get("cpus") is None and node["provision_state"] == "manageable":
        conn.baremetal.set_node_provision_state(node, 'inspect')
        inspecting.append(node)
if len(inspecting) > 0:
    conn.baremetal.wait_for_nodes_provision_state(inspecting, 'manageable')


if len(inspecting) > 0:
    baremetal_nodes = find_baremetal_servers(conn)

target_power = "power off"
for node in baremetal_nodes:
    if node["power_state"] != target_power:
        conn.baremetal.set_node_power_state(node, target_power)

