# arcus-terraform-idrac

# Staring Assumptions

* 1Gb iDRAC untagged traffic on OOB management network
* iDRAC configured for DHCP, with default password
* WSME (and redfish) interface enabled, but IPMI disabled
* Neutron network created to manage IPAM on OOB net
* Neutron dhcp responds to unbound ports

## Step 1: iDRAC IPAM

Ideally your server is configured to have iDRAC dhcp.
And your switch untagged VLAN goes to a neutron network.
This neutron network can hand out IPs to the iDRAC servers.

This script takes a mapping of hostname to mac addresss in csv.
We then create ports in a DHCP enabled neutron network.
Although the ports are not bound, neutron will hand out addresses
to the appropraite mac address.

With this in place, we can now look at adding nodes into ironic,
because we have the impi address that is needed to start the server.

    cd terraform
    terraform plan

Typicaly the above is done per Rack.

### Importing existing ports

If you see a "MAC address in use" 409 error, it might be because
you already created the port for that iDRAC.

You can find the existing port uuid by:

    openstack port list --mac 6C:2B:59:00:00:01 --format yaml

Then you can import and existing port into the state file via:

    terraform import 'openstack_networking_port_v2.ports["hostname"]' /
        a14e016f-14a5-466a-8c19-ad3a910f5511

## Step 2: Add node into Ironic and out-of-band inspect

The iDRAC should now have a working IP address on register with Ironic.

This validates ironic can contact the iDRAC IP.

We use ironic to make the power on state consistent, and powered off.

We can use in iDRAC inspection to get the mac address of pxe 1GbE nic.

    cd python
    . venv/bin/activate
    pip install -r requirements.txt

    ./ironic_enrol.py

## Step 3: Configure iDRAC for PXE on ethernet port

Out the box it boots to hard disk, lets force 1GbE PXE boot.

This forces all hosts in the specified rack to boot using 1GbE nic.
This triggers a host reboot. This also sets the peformance profile
and disabled hyperthreading.

    cd python
    ./ironic_drac_settings.py

TODO: this currently isn't idenpotent. On every invocation it
triggers a bios reconfigure and node reboot for every host without
a pending job. Its a bit slow, one rack takes about 30 mins till
it starts polling all the node for success.

## Step 4: Manually boot up on 1GbE custom ramdisk

We are not using ironic to deploy here,
so first put host in maintainance mode
to stop Ironic modifying the power state of the node.

Boot into ramdisk to update mellanox firmware, as required.
This requires a reboot of the node via a script in the ramdisk.

We use neutron to hand out PXE details, other dhcp can be used instead.

## Step 5: Do in-band inspection via high speed ethernet nic

Move from out of band to in band inspection to get LLDP data.
... ideally also move to inspection using 50GbE at this point.

## Step 6: Finally test booting an instance via Nova

Nova is used to orchestrate putting an image on the node disk.
This involves getting Neutron correctly configuring ports in cumulus.
