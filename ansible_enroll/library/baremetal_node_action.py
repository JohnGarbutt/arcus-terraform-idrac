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
module: baremetal_provision

Adds an ironic node, ready for inspection to discover nics.

short_description: Adds an ironic node

version_added: "2.9"

description:
    - "This is my longer description explaining my test module"

options:
    name:
        description:
            - Name of the ironic node
        required: true

author:
    - John Garbutt, StackHPC (@johnthetubaguy)
"""

EXAMPLES = """
# Pass in a message
- name: Test with a message
  baremetal_node:
    name: test123

"""

RETURN = """
uuid:
    description: uuid of created node
    type: str
    returned: always
"""


def get_kwargs(module, bmc_type, bmc):
    if bmc_type != "idrac-wsman":
        module.fail_json(msg="Unsupported bmc type")
    return dict(
        driver="idrac",
        driver_info={
            "drac_address": bmc["address"],
            # Starting with default passwords as shipped, updates later
            "drac_password": "calvin",
            "drac_username": "root",
            "redfish_system_id": "/redfish/v1/Systems/System.Embedded.1",
            "redfish_address": bmc["address"],
            "redfish_password": "calvin",
            "redfish_username": "root",
            "ipmi_address": bmc["address"],
        },
        boot_interface="ipxe",
        bios_interface="no-bios",
        console_interface="no-console",
        deploy_interface="iscsi",
        inspect_interface="idrac-wsman",
        management_interface="idrac-wsman",
        network_interface="neutron",
        power_interface="idrac-wsman",
        raid_interface="idrac-wsman",
        rescue_interface="agent",
        storage_interface="noop",
        vendor_interface="idrac-wsman",
    )


def run_module():
    module_args = dict(
        name=dict(type="str", required=True),
        action=dict(type="str", required=False, default=""),
        wait=dict(type="bool", required=False, default=True),
        cloud=dict(type="str", required=False, default="arcus"),
        skip_in_maintenance=dict(type="bool", optional=True, default=True),
        # using extra/bootstrap_stage to track progress
        skip_not_in_stage=dict(type="str", optional=True, default=""),
        move_to_stage=dict(type="str", optional=True, default=""),
    )
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    result = {"changed": False, "node": {}}

    # Skip if check mode
    if module.check_mode:
        module.exit_json(**result)

    try:
        cloud = openstack.connection.from_config(
            cloud=module.params["cloud"], debug=True
        )
        # TODO: check initial state?
        node = cloud.baremetal.find_node(module.params["name"])
        if not node:
            module.fail_json(msg="can't find the node")

        extra = node["extra"]
        start_bootstrap_stage = extra.get("bootstrap_stage", "")
        result["node"] = {
            "uuid": node.id,
            "provision_state": node.provision_state,
            "is_maintenance": node.is_maintenance,
            "start_bootstrap_stage": start_bootstrap_stage,
        }

        # Skip if in maintenance
        if module.params["skip_in_maintenance"]:
            if node.is_maintenance:
                module.exit_json(
                    mgs="Skip as node in maintenance", skipped=True, **result
                )

        # Skip if not in requested bootstrap stage
        requested_start_stage = module.params["skip_not_in_stage"]
        if start_bootstrap_stage != requested_start_stage:
            module.exit_json(
                msg=f"Skip as in stage {start_bootstrap_stage}", skipped=True, **result
            )

        # Update provision state
        if module.params["action"] == "manage":
            if node["provision_state"] == "manageable":
                result["changed"] = False
            elif node["provision_state"] in ("enroll", "inspect failed", "available"):
                cloud.baremetal.set_node_provision_state(
                    node=node, target="manage", wait=module.params["wait"]
                )
                result["changed"] = True
            else:
                module.fail_json(
                    msg=f"invalid node state: {node['provision_state']}", **result
                )

        elif module.params["action"] == "inspect":
            if node["provision_state"] == "manageable":
                cloud.baremetal.set_node_provision_state(
                    node=node, target="inspect", wait=module.params["wait"]
                )
                result["changed"] = True
            else:
                module.fail_json(
                    msg=f"invalid node state: {node['provision_state']}", **result
                )

        elif module.params["action"] == "provide":
            if node["provision_state"] == "available":
                result["changed"] = False
            elif node["provision_state"] == "manageable":
                cloud.baremetal.set_node_provision_state(
                    node=node, target="provide", wait=module.params["wait"]
                )
                result["changed"] = True
            else:
                module.fail_json(
                    msg=f"invalid node state: {node['provision_state']}", **result
                )

        elif module.params["action"] == "maintenance-unset":
            if node.is_maintenance:
                cloud.baremetal.unset_node_maintenance(node)
                result["changed"] = True

        elif module.params["action"] == "noop":
            # NOTE(wszumski): Consider splitting the module into action and update stage
            pass

        elif module.params["action"] != "":
            module.fail_json(msg="unsupported action")

        # Update node to mark stage is complete
        new_stage = module.params["move_to_stage"]
        if new_stage:
            op = "replace"
            if start_bootstrap_stage == "":
                op = "add"
            patch = [{"op": op, "path": "extra/bootstrap_stage", "value": new_stage}]
            cloud.baremetal.patch_node(node, patch)
            result["changed"] = True

    except exceptions.OpenStackCloudException as e:
        module.fail_json(msg=str(e), **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
