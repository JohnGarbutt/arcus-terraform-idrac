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
module: baremetal_node_update

short_description: Update metadata for a baremetal node

version_added: "2.9"

description:
    - "Update metadata for a baremetal node"

options:
    name:
        description:
            - Name of the ironic node
        required: true
        type: str
    field:
        description:
            - field to update e.g inspect_interface
        required: true
        type: str
    value:
        description:
            - new value for field
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
        changes=dict(type="dict", required=True),
        cloud=dict(type="str", required=False, default="arcus"),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    result = {"changed": False}

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

        patches = []

        for field, value in module.params["changes"].items():

            # Fields can be separated, e.g extra/system_vendor/bios_version
            field_components = field.split('/')
            current = node
            for i, component in enumerate(field_components):
                if component not in current:
                    if i == 0:
                        # base field must exist
                        module.fail_json(msg=f"Field, {field} does not exist", **result)
                    # key is not guarenteed to exist e.g driver_info/drac_password
                    current = None
                    break
                current = current[component]

            if current and value == current:
                # no update required
                continue

            op = "replace"

            if current == None:
                op = "add"

            patch = {
                    "op": op,
                    "path": field,
                    "value": value
                }

            patches.append(patch)

        if patches:
            cloud.baremetal.patch_node(node, patches)
            # HACK: password appears as *****, so we have no idea if needs updating - report no change
            # on password updates
            password_updates = [patch for patch in patches if "password" in patch["path"]]
            if len(password_updates) == len(patches):
                result = {"changed": False}
            else:
                result = {"changed": True}

    except exceptions.OpenStackCloudException as e:
        module.fail_json(msg=str(e), **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
