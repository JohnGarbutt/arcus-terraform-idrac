#!/usr/bin/env python3
# Usage:
#

import jinja2

import openstack


def find_ports(conn):
    return [{
            "name": raw_port["name"],
            "mac": raw_port["mac_address"],
            "ip": raw_port["fixed_ips"][0]["ip_address"],
        }
        for raw_port in conn.network.ports(tags="pxe-bootstrap")]


template_str = """
{%- for port in ports -%}
{{ port.name }} ansible_host={{ port.ip }} ansible_user=dev
{% endfor %}
"""

env = jinja2.Environment()
template = env.from_string(template_str)
conn = openstack.connection.from_config(cloud="envvars", debug=True)

ports = find_ports(conn)

print(template.render(ports=ports))

