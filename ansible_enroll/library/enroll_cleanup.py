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
module: enroll_cleanup

short_description: Cleans up any resources created during the onboarding so that you can start again
version_added: "2.9"

description:
    - "This is my longer description explaining my test module"

author:
    - Will Szumski, StackHPC
"""

EXAMPLES = """
# Pass in a message
- name: Test with a message
  enroll_cleanup:
    name: "{{ inventory_hostname }}"
    idrac_ip:   "{{ idrac_ip }}"
    idrac_user: "{{ idrac_user }}"
    idrac_password:  "{{ idrac_password }}"
  delegate_to: localhost
"""

from ansible.module_utils.remote_management.dellemc.dellemc_idrac import iDRACConnection
from ansible.module_utils.basic import AnsibleModule


# Get System Inventory
def run_get_system_inventory(idrac, module):
    msg = {}
    msg['changed'] = False
    msg['failed'] = False
    err = False

    try:
        # idrac.use_redfish = True
        idrac.get_entityjson()
        msg['msg'] = idrac.get_json_device()
    except Exception as e:
        err = True
        msg['msg'] = "Error: %s" % str(e)
        msg['failed'] = True
    return msg, err


# Main
def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            cloud=dict(type="str", required=False, default="arcus"),
            # iDRAC credentials
            idrac_ip=dict(required=True, type='str'),
            idrac_user=dict(required=True, type='str'),
            idrac_password=dict(required=True, type='str', aliases=['idrac_pwd'], no_log=True),
            idrac_port=dict(required=False, default=443)
        ),
        supports_check_mode=False)

    try:
        with iDRACConnection(module.params) as idrac:
            msg, err = run_get_system_inventory(idrac, module)
    except (ImportError, ValueError, RuntimeError) as e:
        module.fail_json(msg=str(e))

    if err:
        module.fail_json(**msg)

    result = {"changed": False}


    try:
        cloud = openstack.connection.from_config(
            cloud=module.params["cloud"], debug=True
        )

        # TODO: use utility method from openstack collection, e.g:
        # https://github.com/openstack/ansible-collections-openstack/blob/03fadf3b435b05975b5d3aec028ee92511fd5a13/plugins/modules/compute_flavor_info.py#L203
        # We should update the other modules at the same time.
        node = cloud.baremetal.find_node(module.params["name"])
        if node:
            if node["provision_state"] != "manageable":
                module.fail_json(msg="You must put the node in the manage state in order to perform this cleanup. Warning, it will delete the node.")
            cloud.baremetal.delete_node(node)
            result["changed"] = True

        # Delete all ports
        nics = msg['msg']['NIC']
        for nic in nics:
            mac = nic['CurrentMACAddress']
            existing_ports = list(cloud.network.ports(mac_address=mac))
            for port in existing_ports:
                result["changed"] = True
                cloud.network.delete_port(port)


    except exceptions.OpenStackCloudException as e:
        module.fail_json(msg=str(e), **result)

    module.exit_json(**result)



    module.exit_json(ansible_facts={idrac.ipaddr: {'SystemInventory': msg['msg']}})


if __name__ == '__main__':
    main()
