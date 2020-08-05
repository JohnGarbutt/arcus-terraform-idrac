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

from ansible.module_utils.basic import AnsibleModule

def run_module():
    module_args = dict(
        name=dict(type='str', required=True),
        type=dict(type='str', required=True),
        bmc=dict(type='dict', required=True),
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

    cloud = openstack.connection.from_config(
        cloud=module.params['cloud'], debug=True)
    node = cloud.baremetal.find_node(module.params['name'])
    if not node:
        module.fail_json(msg='Not implemented yet!', **result)

    result['uuid'] = node.id
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
