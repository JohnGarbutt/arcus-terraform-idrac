# arcus-terraform-idrac

If you see a "MAC address in use" 409 error, it might be because
you already created the port for that iDRAC.

You can find the existing port uuid by:

    openstack port list --mac 6C:2B:59:00:00:01 --format yaml

Then you can import and existing port into the state file via:

    terraform import 'openstack_networking_port_v2.ports["hostname"]' /
        a14e016f-14a5-466a-8c19-ad3a910f5511
