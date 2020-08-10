#!/usr/bin/python

# Copyright: (c) 2020, StackHPC
# Apache 2 License

import time

from ansible.module_utils.basic import AnsibleModule
import dracclient.client

ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = """
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


def to_dict(settings):
    settings_dict = {}
    for name, settings_attr in settings.items():
        settings_dict[name] = settings_attr.__dict__
    return settings_dict


def run_module():
    module_args = dict(
        address=dict(type="str", required=True),
        username=dict(type="str", required=True),
        password=dict(type="str", required=True),
        bios=dict(type="dict", required=True),
    )
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    result = dict(changed=False)

    # Skip if check mode
    if module.check_mode:
        module.exit_json(**result)

    client = dracclient.client.DRACClient(
        host=module.params["address"],
        username=module.params["username"],
        password=module.params["password"],
    )
    client.is_idrac_ready()

    jobs = client.list_jobs(only_unfinished=True)
    if len(jobs) > 0:
        module.fail_json(msg="pending idrac jobs")

    # check boot order, drop request if its really a no op
    bios_settings = module.params["bios"]
    if "SetBootOrderFqdd1" in bios_settings:
        requested = (
            f"{bios_settings['SetBootOrderFqdd1']},"
            f"{bios_settings.get('SetBootOrderFqdd2')},"
            f"{bios_settings.get('SetBootOrderFqdd3')},"
            f"{bios_settings.get('SetBootOrderFqdd4')}"
        )
        # Remove any trailing commas, if we have three interfaces
        requested = requested.strip(",")
        current_settings = to_dict(client.list_bios_settings())
        current = current_settings["SetBootOrderEn"]["current_value"]
        result["requested_setting"] = requested
        result["current_settings"] = current
        if requested == current:
            del bios_settings["SetBootOrderFqdd1"]
            del bios_settings["SetBootOrderFqdd2"]
            del bios_settings["SetBootOrderFqdd3"]
            del bios_settings["SetBootOrderFqdd4"]

    bios_result = client.set_bios_settings(bios_settings)
    if bios_result and bios_result["is_commit_required"]:
        result["changed"] = True
        reboot_required = bios_result["is_reboot_required"]
        client.commit_pending_bios_changes(reboot=reboot_required)
        wait_for_jobs({module.params["address"]: client})

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
