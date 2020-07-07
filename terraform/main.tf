terraform {
  required_version = ">= 0.12, < 0.13"
}

provider "openstack" {
  cloud = "arcus"
  version = "~> 1.29"
}

locals {
  idrac_mapping = yamldecode(file("idrac.csv"))
}

output idrac {
  value = idrac_mapping
}
