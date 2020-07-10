#!/usr/bin/env python3

import pprint
import sys
#import sushy
import logging
import os
import openstack
import json
import subprocess
import dracclient
import ironic_drac_settings

# SUSHY_LOG = logging.getLogger('sushy')
# SUSHY_LOG.setLevel(logging.DEBUG)
# SUSHY_LOG.addHandler(logging.StreamHandler())

#openstack.enable_logging(True, stream=sys.stdout)

def configure_bios(node):
    driver_info = node["driver_info"]
    client = dracclient.client.DRACClient(
        host=f'{driver_info["redfish_address"]}',
        username="root",
        password="calvin")
    return ironic_drac_settings.update_settings(client)


def drac_reboot(node):
    driver_info = node["driver_info"]
    client = dracclient.client.DRACClient(
        host=f'{driver_info["redfish_address"]}',
        username="root",
        password="calvin")
    # DRAC can get stuck in power on, try powering off first :(
    # client.set_power_state("POWER_OFF")
    # dracclient.exceptions.DRACOperationFailed: DRAC
    # operation
    # failed.Messages: ['The command failed to set RequestedState']
    client.set_power_state("REBOOT")


def pxe_on_next_boot(node):
    driver_info = node["driver_info"]
    pxe_cmd = {
        "Boot": {
            "BootSourceOverrideEnabled": "Continuous",
            "BootSourceOverrideTarget": "Pxe",
            "BootSourceOverrideMode": "Legacy"
        }
    }
    try:
        subprocess.check_output(
            ["redfishtool", "-r", f'{driver_info["redfish_address"]}', "-u",
             "root",
             "-S", "Always", "-p", "calvin", "raw", "PATCH",
             f'{driver_info["redfish_system_id"]}/', "-d",
             json.dumps(pxe_cmd)])
    except subprocess.CalledProcessError:
        # Seems to error if PXE boot is already set - should check first,
        # but this will do for now
        pass


def reboot(node):
    # Seems flaky and fails when node powered but so did dracclient
    driver_info = node["driver_info"]
    # "ResetType@Redfish.AllowableValues": [
    #     "On",
    #     "ForceOff",
    #     "ForceRestart",
    #     "GracefulShutdown",
    #     "PushPowerButton",
    #     "Nmi",
    #     "PowerCycle"
    # ]
    subprocess.check_output(
        ["redfishtool", "-r", f'{driver_info["redfish_address"]}', "-u",
         "root",
         "-S", "Always", "-p", "calvin", "Systems", "reset", "PowerCycle"])


def check_ping(port):
    ip = port["fixed_ips"][0]["ip_address"]
    response = os.system("ping -c 1 " + ip)
    return response == 0


if __name__ == "__main__":
    conn = openstack.connection.from_config(cloud="envvars", debug=False)

    # Server to operate on
    id = sys.argv[1]

    node = conn.baremetal.find_node(id)

    # This is to prevent use creating the ports again for PXE booting on the
    # 1G
    if "bootstrap_stage" in node["extra"] \
            and node["extra"]["bootstrap_stage"] in ["inspect"]:
        print("Stage invalid, exiting")
        sys.exit(1)

    if node["provision_state"] != "manageable":
        print("Ignoring")
        sys.exit(1)

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
    else:
        port = existing_ports[0]

    if not node["is_maintenance"]:
        # Don't power down during firmware upgrade!
        conn.baremetal.set_node_maintenance(id, reason="Going for PXE boot")

    if not check_ping(port):
        pxe_on_next_boot(node)
        # Is ironic turning off my nodes?
        conn.baremetal.set_node_power_state(node, "power on")
        # I wanted persistent PXE, but this doesn't seem to work, so i'm polling
        # this script instead
        ##status = configure_bios(node)
        # Seems to leave the node in power off state
        # if not status["rebooted"]:
        reboot(node)

    # if node["power_state"] != "power on":
    #     conn.baremetal.set_node_power_state(node, "power on")
    # else:
    #     conn.baremetal.set_node_power_state(node, "power off")
    #     conn.baremetal.set_node_power_state(node, "power on")







