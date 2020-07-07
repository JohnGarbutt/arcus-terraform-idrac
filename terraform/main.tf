terraform {
  required_version = ">= 0.12, < 0.13"
}

provider "openstack" {
  cloud = "arcus"
  version = "~> 1.29"
}

provider "local" {
  version = "~> 1.4"
}

# Example entry in parsed csv:
# [{
#    "bmc_mac_format" = "6C:2B:59:00:00:00"
#    "device_name" = "sv1-ab07-u2"
#    "device_serial" = "AABBCC12"
#    "management_mac_format" = "6C:2B:59:00:00:01"
#    "datacentre_id" = "AC-H3"
#    "rack" = "AB07"
#    "rack_pos" = "2"
#  }]
locals {
  idrac_mapping = csvdecode(file("idrac.csv"))
}

data "openstack_networking_network_v2" "network" {
  name = "out-of-band-management"
}

resource "openstack_networking_port_v2" "ports" {
  for_each = { for mapping in local.idrac_mapping:
               mapping.device_name => mapping}

  name           = each.value.device_name
  network_id     = data.openstack_networking_network_v2.network.id
  mac_address    = each.value.bmc_mac_format
  admin_state_up = "true"
  tags           = [each.value.datacentre_id, each.value.rack]
}

#output idrac {
#  value = local.idrac_mapping
#}
output ports {
  value = {for port in openstack_networking_port_v2.ports:
           port.name => port.all_fixed_ips[0]}
          
}
