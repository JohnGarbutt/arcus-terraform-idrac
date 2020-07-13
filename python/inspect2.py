#!/usr/bin/env python3

import sys
import openstack

# Server to operate on

if __name__  == "__main__":
    conn = openstack.connection.from_config(cloud="envvars", debug=False)
    id = sys.argv[1]

    node = conn.baremetal.find_node(id)

    extra = node["extra"]

    if node["provision_state"] == "inspect failed":
        conn.baremetal.set_node_provision_state(node, 'manage')
        conn.baremetal.wait_for_nodes_provision_state([node], 'manageable')

    if node["provision_state"] != "manageable":
        print("Ignoring")
        sys.exit(1)

    ports = list(conn.baremetal.ports(node=id))

    if len(ports) < 0:
        # FIXME: user logger
        print("Bailing out: no ports")
        sys.exit(1)

    mac = ports[0]["address"]

    pxe_ports = list(conn.network.ports(mac_address=mac))

    if len(pxe_ports) > 0:
        conn.network.delete_port(pxe_ports[0])

    if node["is_maintenance"]:
        conn.baremetal.unset_node_maintenance(id)

    extra["bootstrap_stage"] = "inspect"

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
        }
    ]

    conn.baremetal.patch_node(node, patch)

    conn.baremetal.set_node_provision_state(node, 'inspect')

    conn.baremetal.wait_for_nodes_provision_state([node], 'manageable')


