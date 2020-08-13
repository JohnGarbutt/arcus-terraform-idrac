#!/usr/bin/python

# Copyright: (c) 2020, StackHPC
# Apache 2 License

from ansible.module_utils.basic import AnsibleModule
import openstack
from openstack import exceptions
from deepdiff import DeepDiff

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

def compare_dictionaries(dict_1, dict_2, dict_1_name, dict_2_name, path=""):
    """Compare two dictionaries recursively to find non mathcing elements

    Args:
        dict_1: dictionary 1
        dict_2: dictionary 2

    Returns:

    """
    err = ''
    key_err = ''
    value_err = ''
    old_path = path
    for k in dict_1.keys():
        path = old_path + "[%s]" % k
        if not k in dict_2:
            key_err += "Key %s%s not in %s\n" % (dict_1_name, path, dict_2_name)
        else:
            if isinstance(dict_1[k], dict) and isinstance(dict_2[k], dict):
                err += compare_dictionaries(dict_1[k],dict_2[k], dict_1_name, dict_2_name, path)
            else:
                if dict_1[k] != dict_2[k]:
                    value_err += "Value of %s%s (%s) not same as %s%s (%s)\n"\
                        % (dict_1_name, path, dict_1[k], dict_2_name, path, dict_2[k])

    for k in dict_2.keys():
        path = old_path + "[%s]" % k
        if not k in dict_1:
            key_err += "Key %s%s not in %s\n" % (dict_2_name, path, dict_1_name)

    return key_err + value_err + err

def run_module():
    module_args = dict(
        hosts=dict(type="list", required=True),
        expected=dict(type="dict", required=True),
        actual=dict(type="dict", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    hosts = set(module.params["hosts"])
    expected = module.params["expected"]
    actual = module.params["actual"]

    expected_processed = {}
    # Filter expected to only contain hosts in hosts
    keys = {}
    for switch, ports in expected.items():
        filtered = [port for port in ports if port["server"] in hosts]
        expected_keys = filtered[0].keys()
        keys[switch] = expected_keys
        if filtered:
            expected_processed[switch] = { port["port"]:port for port in filtered }

    actual_processed = {}
    for switch, ports in actual.items():
        whitelist = keys[switch]
        filtered_ports = []
        for port in ports:
            filtered = {}
            for key in whitelist:
                filtered[key] = port[key]
            filtered_ports.append(filtered)
        actual_processed[switch] = { port["port"]:port for port in filtered_ports }

    diff = compare_dictionaries(expected_processed, actual_processed, "expected", "actual")

    if diff:
        module.fail_json(msg=diff)

    module.exit_json(result={"changed": False})


def main():
    run_module()


if __name__ == "__main__":
    main()
