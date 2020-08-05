#!/usr/bin/python

# Copyright: (c) 2020, StackHPC
# Apache 2 License

from ansible.module_utils.basic import AnsibleModule
import openstack
from openstack import exceptions

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: baremetal_enroll

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


def get_node_properties(module):
    bmc_type = module.params['type']
    if bmc_type != "idrac-wsman":
        module.fail_json(msg=f'Unsupported bmc type: {bmc_type}')
    bmc = module.params['bmc']
    props = dict(
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

    def add_optional_prop(name):
        prop = module.params[name]
        if prop:
            props[name] = prop

    add_optional_prop("resource_class")
    add_optional_prop("extra")

    return props


def run_module():
    module_args = dict(
        name=dict(type='str', required=True),
        type=dict(type='str', required=True),
        bmc=dict(type='dict', required=True),
        resource_class=dict(type='str', required=False),
        extra=dict(type='dict', required=False),
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

    node = None
    try:
        cloud = openstack.connection.from_config(
            cloud=module.params['cloud'])
        node = cloud.baremetal.find_node(module.params['name'])

        if not node:
            kwargs = get_node_properties(module)
            node = cloud.baremetal.create_node(
                provision_state="enroll",
                name=module.params['name'],
                **kwargs)
            result['changed'] = True

        # TODO(johngarbutt) patch existing node?
        # TODO(johngarbutt) delete existing node?

    except exceptions.OpenStackCloudException as e:
        module.fail_json(msg=str(e), **result)

    if node:
        result['uuid'] = node.id
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
