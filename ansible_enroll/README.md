## Setup

```
python3 -m venv ~/venv-enroll && ~/venv-enroll/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml -p collections
ansible-galaxy install -r requirements.yml -p roles
```

NOTE: The inventory contains an example host and needs to modified

## Setting up the update respository

NOTE: This only shows a proof of concept grade setup. We need to do these
steps in a dockerfile.

```
[will@cumulus-seed ~]$ docker run --detach --net host --name updates-repo --restart always centos:8 sleep infinity
[root@0a0c6a827562 ~]# curl -O https://dl.dell.com/FOLDER06331494M/1/DRMInstaller_3.3.1.694.bin
[root@0a0c6a827562 ~]# chmod +x DRMInstaller_3.3.1.694.bin 
[root@0a0c6a827562 ~]# ./DRMInstaller_3.3.1.694.bin 
[root@0a0c6a827562 ~]# /opt/dell/dellemcrepositorymanager/DRM_Service.sh

[root@0a0c6a827562 ~]# /opt/dell/dellemcrepositorymanager/drm.sh  -cr -r=idrac_repo -ih=10.202.100.105 -it=idrac --authentication=root:calvin                 

Creating repository idrac_repo
Creating repository for: 10.202.100.105
Repository with name idrac_repo created successfully.

[root@0a0c6a827562 ~]# mkdir /root/idrac_repo
[root@0a0c6a827562 ~]# /opt/dell/dellemcrepositorymanager/drm.sh --deployment-type=share --location=/root/idrac_repo -r=idrac_repo

Job Export_07/31/2020_09:45 is scheduled to run at: Fri Jul 31 09:45:08 UTC 2020
Export Repository job started.
Export Repository job completed successfully.

# NOTE: you can't specifiy a port, so has to use port 80. We could use NFS instead
python3 -m http.server 80 --bind 10.202.150.1
```

Also make sure you open the port on the firewall:

```
[will@cumulus-seed ~]$ sudo iptables -I INPUT 1 -i em1.202 -j ACCEPT -m comment --comment "Will: used for updating via idrac"
```

## Run the update firmware playbook

```
ansible-playbook update-firmware.yml -i inventory/
```

## Exporting and importing server configuration

### Exporting current configuration

Select a server to act as reference machine 

```
(venv-arcus) [will@cumulus-seed ansible_enroll]$ ansible-playbook -i inventory/ export-configuration.yml --limit svn2-dr06-u21
```

### Import

Create a reference configuration. This can be the file you exported earlier unchanged or you can select
a set of attributes to apply:

```
(venv-arcus) [will@cumulus-seed ansible_enroll]$ ./configuration-filter.py --input data/10.202.100.200_20200903_125655_scp.json --component-filter "iDRAC.Embedded.1" --attr-filter "SysLog.1.*" "IPMILan.1#AlertEnable" --component-filter "EventFilters.*" --attr-filter ".*"  | jq . > data/reference-configuration.json
```

In the example above, we are copying the configuration need to enable remote syslog output.

Run the playbook to import the reference confiuration:

```
(venv-arcus) [will@cumulus-seed ansible_enroll]$ ansible-playbook -i inventory/ export-configuration.yml --limit svn2-dr06-u21
```

### Testing the configuration

Prerequisites: install racadm in docker container

```
(venv-arcus) [will@cumulus-seed ~]$ sudo docker exec -it will-testin /opt/dell/srvadmin/bin/idracadm7 -r 10.202.100.162 -u root -p calvin eventfilters test -i PSU0001
```
