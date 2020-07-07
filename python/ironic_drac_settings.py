#!/usr/bin/env python3

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

print(json.dumps(get_all_settings(client), indent=2))
