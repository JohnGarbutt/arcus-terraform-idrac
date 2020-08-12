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
module: baremetal_node_info

short_description: Retrieve information about a baremetal node

version_added: "2.9"

description:
    - "Retrieve information about a baremetal node"

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
  baremetal_node_info:
    name: test123

"""

RETURN = """
node:
    description: Metadata pertaining to the node
    type: dict
    returned: always
"""


def run_module():
    module_args = dict(
        name=dict(type="str", required=True),
        cloud=dict(type="str", required=False, default="arcus"),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    result = {"changed": False, "node": {}}


    try:
        cloud = openstack.connection.from_config(
            cloud=module.params["cloud"], debug=True
        )

        # TODO: use utility method from openstack collection, e.g:
        # https://github.com/openstack/ansible-collections-openstack/blob/03fadf3b435b05975b5d3aec028ee92511fd5a13/plugins/modules/compute_flavor_info.py#L203
        # We should update the other modules at the same time.
        node = cloud.baremetal.find_node(module.params["name"])
        if not node:
            module.fail_json(msg="can't find the node")
        result["node"] = node

    except exceptions.OpenStackCloudException as e:
        module.fail_json(msg=str(e), **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
