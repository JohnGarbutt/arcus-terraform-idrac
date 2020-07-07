#!/usr/bin/env python3

import json

import dracclient.client

client = dracclient.client.DRACClient(
    host="10.202.100.137",
    username="root",
    password="calvin")

settings = client.list_bios_settings()
settings_dict = {}
for name, settings_attr in settings.items():
    settings_dict[name] = settings_attr.__dict__
print(json.dumps(settings_dict, indent=2))

#print(client.list_idrac_settings())
#print(client.list_nic_settings())
