#!/usr/bin/python

# Copyright: (c) 2020, StackHPC
# Apache 2 License

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

    module.fail_json(msg='Not implemented yet!', **result)

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
