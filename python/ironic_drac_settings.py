#!/usr/bin/env python3

import json
import pprint
import sys
import time

import dracclient.client
import openstack


def to_dict(settings):
    settings_dict = {}
    for name, settings_attr in settings.items():
        settings_dict[name] = settings_attr.__dict__
    return settings_dict


def get_all_settings(client):
    bios = to_dict(client.list_bios_settings())
    idrac = to_dict(client.list_idrac_settings())
    nics = client.list_nics()
    nic1 = to_dict(client.list_nic_settings("NIC.Embedded.1-1-1"))
    all_settings = {"bios": bios, "idrac": idrac, "nics": nics, "nic1": nic1}
    return all_settings


def update_settings(client, bios_settings=None, idrac_settings=None):
    if not client.is_idrac_ready():
        print("iDRAC not ready for update settings, skipping")
        return

    jobs = client.list_jobs(only_unfinished=True)
    if len(jobs) > 0:
        pprint.pprint(jobs)
        print("skip update settings, jobs in progress")
        return

    if bios_settings is None:
        bios_settings = {
          "LogicalProc": "Disabled",
          "SysProfile": "PerfOptimized",
          #"SetBootOrderEn": "NIC.Embedded.1-1-1,HardDisk.List.1-1",
          #"SetBootOrderEn": "NIC.Slot.4-1,InfiniBand.Slot.4-1,NIC.Embedded.1-1-1,HardDisk.List.1-1",
          #"SetBootOrderEn": "NIC.Embedded.1-1-1,HardDisk.List.1-1",
          "SetBootOrderFqdd1": "NIC.Embedded.1-1-1",
          "SetBootOrderFqdd2": "HardDisk.List.1-1",
          #"SetBootOrderFqdd3": "InfiniBand.Slot.4-1",
          "SetBootOrderFqdd3": "",
          #"SetBootOrderFqdd4": "InfiniBand.Slot.4-2",
          "SetBootOrderFqdd4": "",
        }
    bios_result = None
    if bios_settings:
        bios_result = client.set_bios_settings(bios_settings)
        print(bios_result)

    if idrac_settings is None:
        idrac_settings = {
          "IPMILan.1#Enable": "Enabled",
        }
    idrac_result = None
    if idrac_settings: 
        idrac_result = client.set_idrac_settings(idrac_settings)
        print(idrac_result)

    reboot_required = bios_result['is_reboot_required']
    if bios_result and bios_result['is_commit_required']:
        reboot_required = bios_result['is_reboot_required']
        print(client.commit_pending_bios_changes(reboot=reboot_required))

    if idrac_result and idrac_result['is_commit_required']:
        reboot_required = idrac_result['is_reboot_required']
        print(client.commit_pending_idrac_changes(reboot=reboot_required))

    return {
        "rebooted": reboot_required
    }


def wait_for_jobs(clients):
    pending = {}

    for name, client in clients.items():
        if not client.is_idrac_ready():
            pending[name] = client
        else:
            jobs = client.list_jobs(only_unfinished=True)
            if len(jobs) > 0:
                pending[name] = client
            else:
                # TODO: check job was a success
                print(name + " has no unfinished jobs")

    if len(pending) > 0:
        hosts = ",".join(list(pending.keys()))
        print("Unfinished jobs found: " + hosts)
        time.sleep(5)
        wait_for_jobs(pending)


def find_idrac_ports(conn):
    return [{
            "name": raw_port["name"],
            "mac": raw_port["mac_address"],
            "ip": raw_port["fixed_ips"][0]["ip_address"],
            "rack": [tag for tag in raw_port["tags"] if "DR" in tag][0],
            "datacentre": [tag for tag in raw_port["tags"] if "DC" in tag][0],
        }
        for raw_port in conn.network.ports(tags="iDRAC")]


def get_nodes_in_rack(conn, rack_name):
    ips = [idrac["ip"] for idrac in find_idrac_ports(conn)
           if idrac["rack"] == rack_name]
    expected_node_count = len(ips)

    all_nodes = conn.baremetal.nodes(details=True)
    nodes = []
    for node in all_nodes:
        if node["driver_info"]["drac_address"] in ips:
            nodes.append(node)
    if len(nodes) != expected_node_count:
        print("unable to find all nodes")
        exit(-1)
    print("found all nodes")
    return nodes


if __name__ == "__main__":
    openstack.enable_logging(True, stream=sys.stdout)
    conn = openstack.connection.from_config(cloud="arcus", debug=True)

    nodes = get_nodes_in_rack(conn, "DR06")

    clients = {}
    for node in nodes:
        ip = node["driver_info"]["drac_address"]
        name = node["name"]
        client = dracclient.client.DRACClient(
            host=ip,
            username="root",
            password="calvin")
        #print(json.dumps(get_all_settings(client), indent=2))
        print("Try BIOS Update for " + ip + " " + name)
        update_settings(client)
        print("Submitted BIOS Update for " + ip + " " + name)
        clients[name] = client

    wait_for_jobs(clients)
