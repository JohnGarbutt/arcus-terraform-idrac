#!/usr/bin/env python3

import pprint
import sys
#import sushy
import logging
import os
import openstack
import json
import subprocess
import time

import dracclient

import ironic_drac_settings

# SUSHY_LOG = logging.getLogger('sushy')
# SUSHY_LOG.setLevel(logging.DEBUG)
# SUSHY_LOG.addHandler(logging.StreamHandler())

#openstack.enable_logging(True, stream=sys.stdout)

def get_dracclient(node):
    driver_info = node["driver_info"]
    client = dracclient.client.DRACClient(
        host=f'{driver_info["redfish_address"]}',
        username="root",
        password="calvin")
    return client


def configure_bios(node):
    client = get_dracclient(node)
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


def check_ssh(port):
    ip = port["fixed_ips"][0]["ip_address"]
    response = os.system("nc -zvw3 " + ip + " 22")
    return response == 0


def setup_port(conn, node):
    ports = list(conn.baremetal.ports(node=node.id))

    if len(ports) != 1:
        # FIXME: user logger
        print("Bailing out: port count is not 1")
        sys.exit(1)

    mac = ports[0]["address"]

    existing_ports = list(conn.network.ports(mac_address=mac))
    if existing_ports:
        if len(existing_ports) != 1:
            print("found too many ports")
            sys.exit(1)
        port = existing_ports[0]
        if port["name"] != f'{node["name"]}-pxe':
            print("detected duplicate mac")
            sys.exit(2)
        print("found existing port: " + mac)
        # TODO: conn.network.delete_port(port)
        return port

    dhcp_extras = [
        {
            'opt_name': 'tag:ipxe,67',
            'opt_value': 'http://10.225.1.1:8089/inspector.ipxe',
            #'opt_value': 'http://10.225.1.1:8089/arcus.ipxe',
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
    port = conn.network.create_port(
        name=f'{node["name"]}-pxe', mac_address=mac,
        network_id="fa913866-b115-49db-8198-dee31461628d",
        extra_dhcp_opts=dhcp_extras,
    )
    conn.network.set_tags(port, ["pxe-bootstrap"])
    print("created a new port: " + mac)
    return port


def check_pending(conn, pending):
    still_pending = []

    for node in pending:
        node = conn.baremetal.find_node(node.id)
        if node["power_state"] != "power on":
            print("node not powered on: " + node.name)
            conn.baremetal.set_node_power_state(node, "power on")

        port = setup_port(conn, node)
        if not check_ssh(port):
            print("can't ping port for: " + node.name + " " + node["driver_info"]["drac_address"])
            still_pending.append(node)
        print("ping check passed: " + node["name"])

    if len(still_pending) > 0:
        print("previously pending: " + str(len(pending)))
        print(",".join([node["name"] for node in pending]))
        print("still pending: " + str(len(still_pending)))
        print(",".join([node["name"] for node in still_pending]))
        print(",".join([node["driver_info"]["drac_address"] for node in still_pending]))
        time.sleep(5)
        check_pending(conn, still_pending)


def test_inspector_pxe_boot(conn):
    # Server to operate on
    #id = sys.argv[1]
    #node = conn.baremetal.find_node(id)
    #if not node:
    #    print("Bailing out: node not found")
    #    sys.exit(1)

    nodes = ironic_drac_settings.get_nodes_in_rack(conn, "DR06")
    #nodes = nodes[0:2]
    print(len(nodes))

    pending = []
    for node in nodes:
        # Skip node if already bootstrapped
        if "bootstrap_stage" in node["extra"] \
                and node["extra"]["bootstrap_stage"] in ["inspect"]:
            print("Stage invalid, exiting")
            continue

        if node["provision_state"] != "manageable":
            print("Ignoring node, invalid state")
            continue

        # Setup dhcp to hand out boot
        port = setup_port(conn, node)
        print(port)

        # Ask for power on, if not already
        # TODO: better handle nodes that are already turned on?
        # TODO: reboot: conn.baremetal.set_node_power_state(node, "power off")
        if node["power_state"] != "power on":
            time.sleep(2)  # be conservative about power demand
            conn.baremetal.set_node_power_state(node, "power on")
            print("Powered on: " + node["name"])

        # tell ironic not to mess with power
        # as we expect to reboot a few times
        if not node["is_maintenance"]:
            # Don't power down during firmware upgrade!
            conn.baremetal.set_node_maintenance(node, reason="PXE to flash nic firmware")

        print("Waiting for: " + node["name"])
        pending.append(node)

    time.sleep(5)

    check_pending(conn, pending)


def inspect_nodes(conn, target_stage="inspect_1GbE", initial_stage=None):
    nodes = ironic_drac_settings.get_nodes_in_rack(conn, "DR06")

    inspecting = []
    for node in nodes:
        if node["provision_state"] in ["inspect wait", "inspecting"]:
            print("inspecting: " + node.name + " " + node["driver_info"]["drac_address"])
            inspecting.append(node)
            continue

        # Skip node if already bootstrapped
        if "bootstrap_stage" in node["extra"] \
                and node["extra"]["bootstrap_stage"] in [target_stage]:
            print("Stage invalid, exiting")
            continue

        # Skip node if already bootstrapped
        if "bootstrap_stage" not in node["extra"] \
                or node["extra"]["bootstrap_stage"] not in [initial_stage]:
            print("Not ready for inspect stage")
            continue

        if node["provision_state"] != "manageable":
            print("Ignoring node, invalid state")
            continue

        if node["is_maintenance"]:
            print("skip nodes in maintenance")
            continue

        if node["power_state"] == "power on":
            conn.baremetal.set_node_power_state(node, "power off")

        extra = node["extra"]
        extra["bootstrap_stage"] = target_stage
        patch = [
            {
                "op": "replace",
                "path": "inspect_interface",
                "value": "inspector"
            },
            {
                "op": "replace",
                "path": "extra",
                "value": extra
            }]
        conn.baremetal.patch_node(node, patch)
        conn.baremetal.set_node_provision_state(node, 'inspect')
        inspecting.append(node)
        print("inspecting: " + node.name + " " + node["driver_info"]["drac_address"])
        time.sleep(2)

    conn.baremetal.wait_for_nodes_provision_state(inspecting, 'manageable')


def get_inspection_data(conn):
    nodes = ironic_drac_settings.get_nodes_in_rack(conn, "DR06")

    result = []
    for raw_node in nodes:
        ports = list(conn.baremetal.ports(node=raw_node["id"], details=True))

        name = raw_node['name']
        ip = raw_node["driver_info"]["drac_address"]
        node = {
            "name": name,
            "ip": ip,
            "uuid": raw_node['id'],
            "ports_by_mac": {},
            "ports_by_switch": {},
            "service_tag": "",
            "bmc_mac": "",
            "mac": "",
            "rack": "",
            "datacentre": "",
        }
        node["rack_pos"] = name.split("u")[1]

        idrac_ports = list(conn.network.ports(name=name))
        if len(idrac_ports) == 1:
            idrac_port = idrac_ports[0]
            if idrac_port["fixed_ips"][0]["ip_address"] == ip:
                node["bmc_mac"] = idrac_port['mac_address']
                node["rack"] = [tag for tag in idrac_port["tags"] if "DR" in tag][0]
                node["datacentre"] = [tag for tag in idrac_port["tags"] if "DC" in tag][0]

        conn.add_service("baremetal-introspection")
        inspector = conn.baremetal_introspection
        response = inspector.get(f"/introspection/{name}/data")
        if response:
            node["interfaces"] = list(response.json()["interfaces"].keys())
            node["hse_interfaces"] = [i for i in node["interfaces"] if "p" in i]

        extra = raw_node['extra']
        if extra and "system_vendor" in extra:
            node["service_tag"] = extra['system_vendor'].get('serial_number')

        lldp_count = 0
        for raw_port in ports:
            lldp = raw_port['local_link_connection']
            if lldp:
                lldp_count += 1
            mac = raw_port['address']
            node["ports_by_mac"][mac] = lldp

            if lldp and "GigabitEthernet" in lldp["port_id"]:
                port = lldp["port_id"]
                if port:
                    port = port.split("GigabitEthernet 1/")[1]
                node["ports_by_switch"]["s3048"] = {
                    "mac": mac,
                    "host": lldp["switch_info"],
                    "port": port,
                }
            elif lldp and "swp" in lldp["port_id"]:
                port = lldp["port_id"]
                if port:
                    port = port.split("swp")[1]
                    port = port.split("s")[0]
                node["ports_by_switch"]["sn3700"] = {
                    "mac": mac,
                    "host": lldp["switch_info"],
                    "port": port,
                }
        result.append(node)
        #if lldp_count < 2:
        #    result.append(node)

    #for node in result:
    #    if "hse_interfaces" in node:
    #        print(f'{node["name"]}\n{node["interfaces"]}')
    #exit(0)

    print(json.dumps(result, indent=2))
    print("dc,rack,rack_pos,height,hardware_name,manufacturer,model,serial,"
          "name,ip,mac_noformat,mac,bmc_ip,bmc_mac_noformat,bmc_mac,"
          "nodetype,groups,s3048_port,sn3700c_port")
    csv = {}
    csv_structured = {}
    for node in result:
        name = node["name"]
        oob = node["ports_by_switch"].get("s3048", {})
        mac = oob.get("mac", "").upper()
        mac_noformat = mac.replace(":","")
        bmc_mac = node.get("bmc_mac", "").upper()
        bmc_mac_noformat = bmc_mac.replace(":", "")
        hse = node["ports_by_switch"].get("sn3700", {})
        oob_port = ""
        if oob:
            oob_port = "-p".join([oob.get("host"), oob.get("port")])
        hse_port = ""
        if hse:
            hse_port = "-p".join([hse.get("host"), hse.get("port")])
        groups = (
            'all,nodes,cascadelake,csd3,compute-csd3,compute-cascadelake,'
            f'Dell,C6420,csd3-2020q3p1,csd3-2020q3p1-{node["rack"].lower()}'
        )
        node_csv = (
            f'{node["datacentre"]},{node["rack"]},{node["rack_pos"]},1,'
            f'{name},Dell,C6420,{node["service_tag"]},{name},,'
            f'{mac_noformat},{mac},,{bmc_mac_noformat},{bmc_mac},'
            f'{groups},{oob_port},{hse_port}')
        csv[name] = node_csv
        csv_structured[name] = {
            "dc": node["datacentre"],
            "rack": node["rack"],
            "rack_pos": node["rack_pos"],
            "height": "1",
            "hardware_name": node["name"],
            "manufacturer": "Dell",
            "model": "C6420",
            "serial": node["service_tag"],
            "name": node["name"],
            "ip": "",
            "mac_noformat": mac_noformat,
            "mac": mac,
            "bmc_ip": "",
            "bmc_mac_noformat": bmc_mac_noformat,
            "bmc_mac": bmc_mac,
            "nodetype": "server",
            "groups": groups,
            "s3048_port": oob_port,
            "sn3700c_port": hse_port,
        }
        print(node_csv)


    import csv
    nodes = {}
    with open("DR06.csv") as csvfile:
        rows = csv.DictReader(csvfile)
        for row in rows:
            nodes[row["name"]] = row
    #print(json.dumps(nodes, indent=2))
    for name, expected in nodes.items():
        expected["ip"] = expected["ip"].strip()
        expected_str = json.dumps(expected)
        inspected = csv_structured.get(name, {})
        inspected_str = json.dumps(inspected)
        has_50GbE_up = inspected.get("serial") and inspected.get("sn3700c_port")
        if expected_str != inspected_str:
            print("error: " + name)
            #print("exp: " + expected_str)
            #print("ins: " + inspected_str)
            print("1  expected: " + expected['s3048_port'] + " found: " + inspected['s3048_port'])
            #print("50 expected: " + expected['sn3700c_port'] + " found: " + inspected['sn3700c_port'])

def request_hse_boot(conn):
    nodes = ironic_drac_settings.get_nodes_in_rack(conn, "DR06")

    clients = {}
    for node in nodes:
        if node["provision_state"] != "manageable":
            print("Ignoring node, invalid state")
            continue

        name = node["name"]

        # Skip node if already bootstrapped
        if "bootstrap_stage" in node["extra"]:
            if node["extra"]["bootstrap_stage"] == "boot_on_50GbE":
                dclient = get_dracclient(node)
                clients[name] = dclient
                continue
            if node["extra"]["bootstrap_stage"] != "inspect_1GbE":
                print("Stage invalid, exiting")
                continue
            #if node["extra"]["bootstrap_stage"] != "inspect_50GbE":
            #    print("Stage invalid, exiting")
            #    continue

        if node["is_maintenance"]:
            print("Skip nodes in maintenance")
            continue

        print("moving to hse boot: " + node.name + " " + node["driver_info"]["drac_address"])
        dclient = get_dracclient(node)
        bios_settings = {
          "LogicalProc": "Disabled",
          "SysProfile": "PerfOptimized",
          "EmbNic1": "DisabledOs",
          #"SetBootOrderEn": "NIC.Slot.4-1,InfiniBand.Slot.4-1,NIC.Embedded.1-1-1,HardDisk.List.1-1",
          "SetBootOrderFqdd1": "NIC.Slot.4-1",
          "SetBootOrderFqdd2": "HardDisk.List.1-1",
          "SetBootOrderFqdd3": "",
          "SetBootOrderFqdd4": "",
        }
        idrac_settings={
        }
        ironic_drac_settings.update_settings(
            dclient, bios_settings, idrac_settings)
        clients[name] = dclient

        extra = node["extra"]
        extra["bootstrap_stage"] = "boot_on_50GbE"
        patch = [
            {
                "op": "replace",
                "path": "inspect_interface",
                "value": "inspector"
            },
            {
                "op": "replace",
                "path": "extra",
                "value": extra
            }]
        conn.baremetal.patch_node(node, patch)

    # TODO: ideally add a new state for when jobs are complete
    ironic_drac_settings.wait_for_jobs(clients)


def manual_setup_port_inspection(conn, node):
    ports = list(conn.baremetal.ports(node=node.id))
    pxe_mac = node["extra"]["pxe_interface_mac"]
    ports = [port for port in ports if port['address'] == pxe_mac]
    if len(ports) != 1:
        # FIXME: user logger
        print("Bailing out: port count is not 1")
        sys.exit(1)

    mac = ports[0]["address"]

    existing_ports = list(conn.network.ports(mac_address=mac))
    if existing_ports:
        if len(existing_ports) != 1:
            print("found too many ports")
            sys.exit(1)
        port = existing_ports[0]
        if port["name"] != f'{node["name"]}-pxe':
            print("detected duplicate mac")
            sys.exit(2)
        print("found existing port: " + mac)
        # TODO: conn.network.delete_port(port)
        return port

    dhcp_extras = [
        {
            'opt_name': 'tag:ipxe,67',
            #'opt_value': 'http://10.225.1.1:8089/inspector.ipxe',
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
    network_name = "cleaning-net"
    network = conn.network.find_network(network_name)
    port = conn.network.create_port(
        name=f'{node["name"]}-pxe-{network_name}', mac_address=mac,
        network_id=network["id"],
        extra_dhcp_opts=dhcp_extras,
    )
    conn.network.set_tags(port, ["pxe-bootstrap"])
    print("created a new port: " + mac)
    return port


def boot_on_cleaning_net(conn):
    nodes = ironic_drac_settings.get_nodes_in_rack(conn, "DR06")
    nodes = nodes[1:2]
    print(nodes[0])
    exit(-1)

    clients = {}
    for node in nodes:
        if node["provision_state"] != "manageable":
            print("Ignoring node, invalid state")
            continue
        manual_setup_port_inspection(conn, node)


def set_expected_bios_version(conn, version="2.5.4"):
    nodes = ironic_drac_settings.get_nodes_in_rack(conn, "DR06")

    for node in nodes:
        vendor = node["extra"].get("system_vendor")
        if not vendor:
            print(f"node in bad state: {node['name']}")
        elif "bios_version" not in vendor:
            print("setting bios")
            patch = [
                {
                    "op": "add",
                    "path": "extra/system_vendor/bios_version",
                    "value": version
                }]
            print(f"patching node {node['name']}")
            conn.baremetal.patch_node(node, patch)


def reset_after_failed_clean(conn):
    nodes = ironic_drac_settings.get_nodes_in_rack(conn, "DR06")

    pending = []
    for node in nodes:
        if node["provision_state"] != "clean failed":
            print("Ignoring node, invalid state")
            continue
        print("moving to manageable: " + node.name + " " + node["driver_info"]["drac_address"])
        if node["is_maintenance"]:
            conn.baremetal.unset_node_maintenance(node)
        if node["power_state"] == "power on":
            conn.baremetal.set_node_power_state(node, "power off")
        conn.baremetal.set_node_provision_state(node, 'manage')
        pending.append(node)

    conn.baremetal.wait_for_nodes_provision_state(pending, 'manageable')


def abort_clean(conn):
    nodes = ironic_drac_settings.get_nodes_in_rack(conn, "DR06")

    pending = []
    for node in nodes:
        if node["provision_state"] != "available":
            print("Ignoring node, invalid state")
            continue
        print("aborting clean: " + node.name + " " + node["driver_info"]["drac_address"])
        conn.baremetal.set_node_provision_state(node, 'manage')
        pending.append(node)

    conn.baremetal.wait_for_nodes_provision_state(pending, 'clean failed')


def move_to_available(conn):
    nodes = ironic_drac_settings.get_nodes_in_rack(conn, "DR06")

    pending = []
    for node in nodes:
        if node["provision_state"] in ["clean wait", "cleaning"]:
            print("already cleaning: " + node.name + " " + node["driver_info"]["drac_address"])
            pending.append(node)
            continue
        if node["provision_state"] != "manageable":
            print("Ignoring node, invalid state")
            continue

        name = node["name"]

        # Skip node if already bootstrapped
        if "bootstrap_stage" in node["extra"]:
            if node["extra"]["bootstrap_stage"] == "boot_on_50GbE":
                dclient = get_dracclient(node)
                clients[name] = dclient
                continue
            if node["extra"]["bootstrap_stage"] not in ["inspect_50GbE", "boot_on_50GbE_no_1G"]:
                print("Stage invalid, exiting")
                continue
            #if node["extra"]["bootstrap_stage"] != "inspect_50GbE":
            #    print("Stage invalid, exiting")
            #    continue

        if node["is_maintenance"]:
            print("Skip nodes in maintenance")
            continue

        print("moving to available: " + node.name + " " + node["driver_info"]["drac_address"])
        conn.baremetal.set_node_provision_state(node, 'provide')
        pending.append(node)
        time.sleep(2)

        if len(pending) >= 50:
            break

    conn.baremetal.wait_for_nodes_provision_state(pending, 'available')


if __name__ == "__main__":
    openstack.enable_logging(True, stream=sys.stdout)
    conn = openstack.connection.from_config(cloud="arcus", debug=False)
    #test_inspector_pxe_boot(conn)
    #inspect_nodes(conn)
    #get_inspection_data(conn)
    #request_hse_boot(conn)
    #inspect_nodes(conn, target_stage="inspect_50GbE", initial_stage="boot_on_50GbE")
    #boot_on_cleaning_net(conn)
    #set_expected_bios_version(conn)  #TODO: new inspection rule should do that
    move_to_available(conn)
    #reset_after_failed_clean(conn)
    #abort_clean(conn)
