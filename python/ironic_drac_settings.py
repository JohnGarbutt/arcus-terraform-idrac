#!/usr/bin/env python3

import pprint
import json

import dracclient.client


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


client = dracclient.client.DRACClient(
    host="10.202.100.137",
    username="root",
    password="calvin")

#print(json.dumps(get_all_settings(client), indent=2))

jobs = client.list_jobs(only_unfinished=True)
if len(jobs) > 0:
    pprint.pprint(jobs)
    exit(-1)

bios_settings = {
  "LogicalProc": "Disabled",
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
