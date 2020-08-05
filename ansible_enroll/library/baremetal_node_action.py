#!/usr/bin/python

# Copyright: (c) 2020, StackHPC
# Apache 2 License

import openstack

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
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
'''

EXAMPLES = '''
# Pass in a message
- name: Test with a message
  baremetal_node:
    name: test123

'''

RETURN = '''
uuid:
    description: uuid of created node
    type: str
    returned: always
'''

from ansible.module_utils.basic import AnsibleModule


def get_kwargs(module, bmc_type, bmc):
    if bmc_type != "idrac-wsman":
        module.fail_json(msg='Unsupported bmc type')
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
        uuid=dict(type='str', required=True),
        target_state=dict(type='str', required=True),
        wait=dict(type='bool', required=False, default=True),
        cloud=dict(type='str', required=False, default='arcus'),
    )

    result = dict(
        changed=False,
        uuid='',
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Skip if check mode
    if module.check_mode:
        module.exit_json(**result)

    try:
        cloud = openstack.connection.from_config(
            cloud=module.params['cloud'], debug=True)
        # TODO: check initial state?
        node = cloud.baremetal.find_node(module.params['uuid'])
        if not node:
            module.fail_json(msg="can't find the node")

        if module.params['target_state'] != "manageable":
            module.fail_json(msg="unsupported target state")
        if node['provision_state'] == "enroll":
            cloud.baremetal.set_node_provision_state(
                node=module.params['uuid'],
                target="manage",
                wait=module.params['wait'])   
            result['changed'] = True

    except openstack.exceptions.OpenStackCloudException as e:
        module.fail_json(msg=str(e), **result)

    result['uuid'] = node.id
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
