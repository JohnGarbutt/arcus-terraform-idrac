#!/usr/bin/python

# Copyright: (c) 2020, StackHPC
# Apache 2 License

from ansible.errors import AnsibleError, AnsibleFilterError, AnsibleFilterTypeError
from ansible.module_utils.six import string_types


def _get_hostvar(context, var_name, inventory_hostname=None):
    if inventory_hostname is None:
        namespace = context
    else:
        if inventory_hostname not in context['hostvars']:
            raise AnsibleFilterError(
                "Inventory hostname '%s' not in hostvars" % inventory_hostname)
        namespace = context["hostvars"][inventory_hostname]
    return namespace.get(var_name)

def baremetal_driver(bmc_type, bmc_address, bmc_username, bmc_password):
    '''Return Openstack Ironic driver info'''
    if not isinstance(bmc_type, string_types):
        raise AnsibleFilterTypeError("|baremetal_driver_info expects string got %s instead." % type(bmc_type))
    bmc_props = {
        "idrac": {
            "driver":"idrac",
            "driver_info/drac_address":bmc_address,
            "driver_info/drac_password":bmc_password,
            "driver_info/drac_username":bmc_username,
            "boot_interface":"ipxe",
            "bios_interface":"no-bios",
            "console_interface":"no-console",
            "deploy_interface":"iscsi",
            "inspect_interface":"idrac-wsman",
            "management_interface":"idrac-wsman",
            "network_interface":"neutron",
            "power_interface":"idrac-wsman",
            "raid_interface":"idrac-wsman",
            "rescue_interface":"agent",
            "storage_interface":"noop",
            "vendor_interface":"idrac-wsman",
        },
        "ipmi": {
            "driver":"ipmi",
            "driver_info/ipmi_address":bmc_address,
            "driver_info/ipmi_password":bmc_password,
            "driver_info/ipmi_username":bmc_username,
            "boot_interface":"ipxe",
            "bios_interface":"no-bios",
            "console_interface":"no-console",
            "deploy_interface":"iscsi",
            "inspect_interface":"inspector",
            "management_interface":"ipmitool",
            "network_interface":"neutron",
            "power_interface":"ipmitool",
            "raid_interface":"no-raid",
            "rescue_interface":"agent",
            "storage_interface":"noop",
            "vendor_interface":"no-vendor",
        }
    }
    props = bmc_props[bmc_type]
    return props

class FilterModule(object):
    ''' Ansible core jinja2 filters '''

    def filters(self):
        return {
            # jinja2 overrides
            'baremetal_driver': baremetal_driver
        }