#!/usr/bin/python

# Copyright: (c) 2020, StackHPC
# Apache 2 License

from ansible.module_utils.basic import AnsibleModule
import openstack
from openstack import exceptions

ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = """
---
module: baremetal_switch_ports

short_description: Retreives switch port mappings from introspection data

version_added: "2.9"

description:
    - "Retrieves switch port mappings"

options:
    name:
        description:
            - Name of the ironic node
        required: true
        type: str

requirements:
    - "python >= 3.6"
    - "openstacksdk"

extends_documentation_fragment:
- openstack.cloud.openstack

author:
    - Will Szumski, StackHPC
"""

EXAMPLES = """
# Pass in a message
- name: Test with a message
  baremetal_switch_ports:
   hosts:
    - host1
    - host 2

"""

RETURN = """
mappings:
    description: Switch port mappings
    type: dict
    returned: always
"""

def get_inspection_data(module, conn, nodes):
    result = {}
    conn.add_service("baremetal-introspection")
    inspector = conn.baremetal_introspection

    for name in nodes:
        response = inspector.get(f"/introspection/{name}/data")
        if response:
            result[name] = response.json()
        else:
            module.warn(f"introspection data not found for: {name}")
    return result

def pad(seq, length):
    result = [0] * length
    for i, element in enumerate(seq):
        result[i] = element
    return tuple(result)

def parse(port):
    port_split_ws = port.split(" ")
    if port.startswith("swp"):
        # e.g swp1s2
        unprefix = port[3:]
        as_int = [int(x) for x in unprefix.split("s")]
        return pad(as_int, 4)
    elif port_split_ws[0] in ("GigabitEthernet"):
        # e.g: GigabitEthernet 1/27
        as_int = [int(x) for x in port_split_ws[1].split("/")]
        return pad(as_int, 4)
    else:
        raise ValueError(f"Can't parse switchport: {port}")

def compare(item):
    # This defines the sort order. We using the the port name.
    return parse(item["port"])

def get_lldp(module, introspection_data):
    ports = {}
    for name, data in introspection_data.items():
        for interface in data["all_interfaces"]:
            if "lldp_processed" not in data["all_interfaces"][interface]:
                module.warn("lldp not available for %s-%s" % (name, interface))
                continue
            mac = data["all_interfaces"][interface]["mac"]
            lldp = data["all_interfaces"][interface]["lldp_processed"]
            switch = lldp["switch_system_name"]
            port = lldp['switch_port_id']
            entry = {
                "port": port,
                "server": name,
                "interface": interface,
                "mac": mac
            }
            if switch in ports:
               ports[switch] = ports[switch] + [entry]
            else:
               ports[switch] = [entry]

    sorted_ = {}
    for key, xs in ports.items():
        xs = sorted(xs, key=compare)
        sorted_[key] = xs
    return sorted_


def run_module():
    module_args = dict(
        hosts=dict(type="list", required=True),
        cloud=dict(type="str", required=False, default="arcus"),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    result = {"changed": False}
    hosts = module.params["hosts"]

    try:
        cloud = openstack.connection.from_config(
            cloud=module.params["cloud"], debug=True
        )

        result["mappings"] = get_lldp(module, get_inspection_data(module, cloud, hosts))

    except exceptions.OpenStackCloudException as e:
        module.fail_json(msg=str(e), **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
