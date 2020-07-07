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

output idrac {
  value = local.idrac_mapping
}
