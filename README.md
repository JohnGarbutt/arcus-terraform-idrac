# arcus-terraform-idrac

Ideally your server is configured to have iDRAC dhcp.
And your switch untagged VLAN goes to a neutron network.
This neutron network can hand out IPs to the iDRAC servers.

This script takes a mapping of hostname to mac addresss.
We then create ports in a DHCP enabled neutron network.
Although the ports are not bound, neutron will hand out addresses
to the appropraite mac address.

With this in place, we can now look at adding nodes into ironic,
because we have the impi address that is needed to start the server.

## Importing existing ports

If you see a "MAC address in use" 409 error, it might be because
you already created the port for that iDRAC.

You can find the existing port uuid by:

    openstack port list --mac 6C:2B:59:00:00:01 --format yaml

Then you can import and existing port into the state file via:

    terraform import 'openstack_networking_port_v2.ports["hostname"]' /
        a14e016f-14a5-466a-8c19-ad3a910f5511
