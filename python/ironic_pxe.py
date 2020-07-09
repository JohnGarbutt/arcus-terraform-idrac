#!/usr/bin/env python3

import pprint
import sys
#import sushy
import logging
import openstack
import json
import subprocess

# SUSHY_LOG = logging.getLogger('sushy')
# SUSHY_LOG.setLevel(logging.DEBUG)
# SUSHY_LOG.addHandler(logging.StreamHandler())

openstack.enable_logging(True, stream=sys.stdout)

conn = openstack.connection.from_config(cloud="envvars", debug=True)

# Server to operate on
id = sys.argv[1]

node = conn.baremetal.find_node(id)

if not node:
    print("Bailing out: node not found")
    sys.exit(1)

# 'driver_info': {'drac_address': '10.202.100.105',
#                 'drac_password': '******',
#                 'drac_username': 'root',
#                 'redfish_address': '10.202.100.105',
#                 'redfish_password': '******',
#                 'redfish_system_id': '/redfish/v1/Systems/System.Embedded.1',
#                 'redfish_username': 'root'},


# Sushy fails with: KeyError: 'Actions'
# url = f'http://{driver_info["redfish_address"]}/redfish/v1'
# s = sushy.Sushy(url, username='root', password='calvin', verify=False)
#
# # Get the Redfish version
# print(s.redfish_version)
#
# bmc_system = s.get_system(f'{driver_info["redfish_system_id"]}/')
# bmc_system.set_system_boot_source(sushy.BOOT_SOURCE_TARGET_PXE,
#                                 enabled=sushy.BOOT_SOURCE_ENABLED_ONCE,
#                                 mode=sushy.BOOT_SOURCE_MODE_BIOS)


def pxe_on_next_boot(node):
    driver_info = node["driver_info"]
    pxe_cmd = {
        "Boot": {
            "BootSourceOverrideEnabled": "Once",
            "BootSourceOverrideTarget": "Pxe",
            "BootSourceOverrideMode": "Legacy"
        }
    }
    subprocess.check_output(
        ["redfishtool", "-r", f'{driver_info["redfish_address"]}', "-u",
         "root",
         "-S", "Always", "-p", "calvin", "raw", "PATCH",
         f'{driver_info["redfish_system_id"]}/', "-d",
         json.dumps(pxe_cmd)])


def reboot(node):
    driver_info = node["driver_info"]
    subprocess.check_output(
        ["redfishtool", "-r", f'{driver_info["redfish_address"]}', "-u",
         "root",
         "-S", "Always", "-p", "calvin", "reset", "ForceRestart"])


ports = list(conn.baremetal.ports(node=id))

if len(ports) < 0:
    # FIXME: user logger
    print("Bailing out: no ports")
    sys.exit(1)

mac = ports[0]["address"]

existing_ports = list(conn.network.ports(mac_address=mac))

dhcp_extras = [
    {
        'opt_name': 'tag:ipxe,67',
        'opt_value': 'http://10.225.1.1:8089/arcus.ipxe',
        'ip_version': 4
    },
    {
        'opt_name': '66',
        'opt_value': '10.225.1.1',
        'ip_version': 4
    },
    {
        'opt_name': '150',
        'opt_value': '10.225.1.1',
        'ip_version': 4
    },
    {
        'opt_name': 'tag:!ipxe,67',
        'opt_value': 'undionly.kpxe',
        'ip_version': 4
    },
    {
        'opt_name': 'server-ip-address',
        'opt_value': '10.225.1.1',
        'ip_version': 4
    },
]

if not existing_ports:
    port = conn.network.create_port(
        name=f'{node["name"]}-pxe', mac_address=mac,
        network_id="fa913866-b115-49db-8198-dee31461628d",
        extra_dhcp_opts=dhcp_extras,
    )
    conn.network.set_tags(port, ["pxe-bootstrap"])


if not node["is_maintenance"]:
    conn.baremetal.set_node_maintenance(id, reason="Going for PXE boot")

pxe_on_next_boot(node)
reboot(node)

# if node["power_state"] != "power on":
#     conn.baremetal.set_node_power_state(node, "power on")
# else:
#     conn.baremetal.set_node_power_state(node, "power off")
#     conn.baremetal.set_node_power_state(node, "power on")







