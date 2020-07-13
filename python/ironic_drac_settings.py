#!/usr/bin/env python3

import json
import pprint
import sys

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


def update_settings(client):
    jobs = client.list_jobs(only_unfinished=True)
    if len(jobs) > 0:
        pprint.pprint(jobs)
        exit(-1)

    bios_settings = {
      "LogicalProc": "Disabled",
      "SysProfile": "PerfOptimized",
      #"SetBootOrderEn": "NIC.Embedded.1-1-1,HardDisk.List.1-1",
      #"SetBootOrderEn": "NIC.Slot.4-1,InfiniBand.Slot.4-1,NIC.Embedded.1-1-1,HardDisk.List.1-1",
      "SetBootOrderFqdd1": "NIC.Embedded.1-1-1",
      "SetBootOrderFqdd2": "HardDisk.List.1-1",
    }
    bios_result = client.set_bios_settings(bios_settings)
    print(bios_result)

    idrac_settings = {
      "IPMILan.1#Enable": "Enabled",
    }
    idrac_result = client.set_idrac_settings(idrac_settings)
    print(idrac_result)

    reboot_required = bios_result['is_reboot_required']
    if bios_result['is_commit_required']:
        reboot_required = bios_result['is_reboot_required']
        print(client.commit_pending_bios_changes(reboot=reboot_required))

    if idrac_result['is_commit_required']:
        reboot_required = idrac_result['is_reboot_required']
        print(client.commit_pending_idrac_changes(reboot=reboot_required))

    pprint.pprint(client.list_jobs(only_unfinished=True))
    return {
        "rebooted": reboot_required
    }


def find_idrac_ports(conn):
    return [{
            "name": raw_port["name"],
            "mac": raw_port["mac_address"],
            "ip": raw_port["fixed_ips"][0]["ip_address"],
            "rack": [tag for tag in raw_port["tags"] if "DR" in tag][0],
            "datacentre": [tag for tag in raw_port["tags"] if "DC" in tag][0],
        }
        for raw_port in conn.network.ports(tags="iDRAC")]


if __name__ == "__main__":
    openstack.enable_logging(True, stream=sys.stdout)
    conn = openstack.connection.from_config(cloud="envvars", debug=True)

    ips = [idrac["ip"] for idrac in find_idrac_ports(conn)]
    print(ips)

    for ip in ips:
        client = dracclient.client.DRACClient(
            host=ip,
            username="root",
            password="calvin")
        print(json.dumps(get_all_settings(client), indent=2))
        break
        #update_settings(client)

