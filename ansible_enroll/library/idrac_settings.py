#!/usr/bin/python

# Copyright: (c) 2020, StackHPC
# Apache 2 License

import time

from ansible.module_utils.basic import AnsibleModule
import dracclient.client

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: idrac_bios

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


def wait_for_jobs(clients):
    # TODO(johngarbutt) timeout via tenacity?
    pending = {}

    for name, client in clients.items():
        if not client.is_idrac_ready():
            pending[name] = client
        else:
            jobs = client.list_jobs(only_unfinished=True)
            if len(jobs) > 0:
                pending[name] = client
            else:
                # TODO: check job was a success
                print(name + " has no unfinished jobs")

    if len(pending) > 0:
        hosts = ",".join(list(pending.keys()))
        print("Unfinished jobs found: " + hosts)
        time.sleep(5)
        wait_for_jobs(pending)


def run_module():
    module_args = dict(
        address=dict(type='str', required=True),
        username=dict(type='str', required=True),
        password=dict(type='str', required=True),
        bios=dict(type='dict', required=True),
    )
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )
    result = dict(changed=False)

    # Skip if check mode
    if module.check_mode:
        module.exit_json(**result)

    client = dracclient.client.DRACClient(
        host=module.params['address'],
        username=module.params['username'],
        password=module.params['password'])
    client.is_idrac_ready()

    jobs = client.list_jobs(only_unfinished=True)
    if len(jobs) > 0:
        module.fail_json(msg="pending idrac jobs")

    bios_result = client.set_bios_settings(
        module.params["bios"])
    if bios_result and bios_result['is_commit_required']:
        reboot_required = bios_result['is_reboot_required']
        client.commit_pending_bios_changes(reboot=reboot_required)
    wait_for_jobs({module.params['address']: client})

    module.fail_json(msg="not implemented yet")


def main():
    run_module()


if __name__ == '__main__':
    main()
