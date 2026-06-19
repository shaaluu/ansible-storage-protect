# IBM Storage Protect HSM Client Installation Role

## Overview

This Ansible role provides comprehensive management of IBM Storage Protect Hierarchical Storage Management (HSM) Client for Linux and AIX systems. It supports installation, uninstallation, configuration, and facts gathering operations with automatic rollback capabilities.

## Features

- **Complete Lifecycle Management**: Install, uninstall, and configure HSM Client
- **Multi-Platform Support**: Linux (RHEL, SLES) and AIX
- **Idempotent Operations**: Safe to run multiple times without side effects
- **Automatic Rollback**: Rolls back changes if operations fail
- **Pre-flight Checks**: Validates system requirements before installation
- **GPFS Integration**: Checks GPFS status and HSM state
- **Configuration Management**: Manages dsm.opt and dsm.sys files
- **Facts Gathering**: Collects comprehensive HSM client information
- **Version Validation**: Ensures correct version is installed/uninstalled

## Requirements

### System Requirements

**Linux:**
- **Operating System**: Red Hat Enterprise Linux 7/8/9, SUSE Linux Enterprise Server 12/15
- **Architecture**: x86_64, s390x, ppc64le
- **Disk Space**: Minimum 1500 MB free space
- **Python**: Python 3.6 or higher

**AIX:**
- **Operating System**: AIX 7.1, 7.2, 7.3
- **Architecture**: ppc64
- **Disk Space**: Minimum 1500 MB free space

**Common Requirements:**
- **Privileges**: Root access required
- **GPFS (CRITICAL)**: IBM Spectrum Scale (GPFS) must be installed and configured

### GPFS Prerequisite (MANDATORY)

⚠️ **HSM Client REQUIRES IBM Spectrum Scale (GPFS) to function.**

**Required GPFS Packages:**
- `gpfs.base` (>= 4.2.1-0) - Core GPFS functionality
- `gpfs.gpl` - GPL modules
- `gpfs.gskit` - Security toolkit
- `gpfs.msg.en_US` - Message catalog
- `gpfs.compression` (recommended) - Compression support
- `gpfs.license.std` - Standard license

**Verification Commands:**
```bash
# Linux
rpm -qa | grep -i '^gpfs\.'
mmgetstate -a

# AIX
lslpp -l | grep -i '^gpfs\.'
mmgetstate -a
```

**Why GPFS is Required:**
- File system hooks for automatic migration/recall
- Policy-based file management
- Stub file management
- Transparent data movement between storage tiers

**Bypass Option (Testing Only):**
```yaml
skip_gpfs_check: true  # WARNING: HSM will NOT function without GPFS
```

### Software Requirements
- Ansible 2.9 or higher
- Python 3.6 or higher on target hosts
- IBM Storage Protect HSM Client installation package

## Role Variables

### Required Variables

```yaml
hsm_client_version: "8.2.2.0"           # HSM Client version to install/uninstall
hsm_client_state: "present"             # State: present or absent
tar_file_path: "/tmp/package.tar"       # Path to installation package
```

### Optional Variables

```yaml
# Installation paths
hsm_install_path: "/opt/tivoli/tsm/client/hsm/bin"
hsm_temp_dir: "/opt/hsmClient"
hsm_client_temp_dest: "/tmp/"

# File location
tar_file_location: "remote"             # 'remote' (default) or 'controller'

# Daemon control
hsm_client_start_daemon: true

# Server configuration
server_name: "TSM_SERVER"
server_address: "tsm.example.com"
server_port: "1500"
node_name: "{{ ansible_hostname }}"

# Advanced options
force_install: false
force_uninstall: false
skip_gpfs_check: false
cleanup_tar_file: true
```

## Dependencies

- `system_info` role (for gathering system facts)

## Example Playbooks

### Install HSM Client on Linux

```yaml
---
- name: Install HSM Client on Linux
  hosts: linux_hsm_servers
  become: true
  
  vars:
    hsm_client_version: "8.2.2.0"
    hsm_client_state: "present"
    tar_file_path: "/tmp/8.2.2.0-TIV-TSMHSM-LinuxX86.tar"
    server_name: "TSM_PROD"
    server_address: "tsm-server.example.com"
    
  roles:
    - hsm_client_install
```

### Install HSM Client on AIX

```yaml
---
- name: Install HSM Client on AIX
  hosts: aix_hsm_servers
  become: true
  
  vars:
    hsm_client_version: "8.2.2.0"
    hsm_client_state: "present"
    tar_file_path: "/tmp/8.2.2.0-TIV-TSMHSM-AIXGPFS.tar.Z"
    server_name: "TSM_PROD"
    server_address: "tsm-server.example.com"
    
  roles:
    - hsm_client_install
```

### Uninstall HSM Client

```yaml
---
- name: Uninstall HSM Client
  hosts: hsm_servers
  become: true
  
  vars:
    hsm_client_version: "8.2.2.0"
    hsm_client_state: "absent"
    force_uninstall: true
    
  roles:
    - hsm_client_install
```

### Gather HSM Client Facts

```yaml
---
- name: Gather HSM Client Facts
  hosts: hsm_servers
  become: true
  
  tasks:
    - name: Gather HSM facts
      hsm_client_facts:
        q_version: true
        q_gpfs_status: true
        q_hsm_status: true
        q_filespace: true
        q_systeminfo: true
      register: hsm_facts
      
    - name: Display facts
      debug:
        var: hsm_facts
```

## Command Line Examples

### Installation

**Linux:**
```bash
cd ~/Desktop/Ansible/ansible-storage-protect

ansible-playbook playbooks/hsm_client_install/playbooks/linux/hsm_client_install_role_playbook.yml \
  -i inventory.ini \
  -e "hsm_client_version=8.2.2.0" \
  -e "tar_file_path=/tmp/8.2.2.0-TIV-TSMHSM-LinuxX86.tar"
```

**AIX:**
```bash
ansible-playbook playbooks/hsm_client_install/playbooks/aix/hsm_client_install_role_playbook.yml \
  -i inventory.ini \
  -e "hsm_client_version=8.2.2.0" \
  -e "tar_file_path=/tmp/8.2.2.0-TIV-TSMHSM-AIXGPFS.tar.Z"
```

### Uninstallation

**Linux:**
```bash
ansible-playbook playbooks/hsm_client_install/playbooks/linux/hsm_client_uninstall_playbook.yml \
  -i inventory.ini \
  -e "hsm_client_version=8.2.2.0" \
  -e "force_uninstall=yes"
```

**AIX:**
```bash
ansible-playbook playbooks/hsm_client_install/playbooks/aix/hsm_client_uninstall_playbook.yml \
  -i inventory.ini \
  -e "hsm_client_version=8.2.2.0" \
  -e "force_uninstall=yes"
```

### Facts Gathering

```bash
ansible-playbook playbooks/hsm_client_install/playbooks/linux/hsm_client_facts_playbook.yml \
  -i inventory.ini
```

## Installation Flow

### Linux Installation (`state: present`)

1. **Pre-checks**
   - Validates system architecture (x86_64, s390x, ppc64le)
   - Checks available disk space (minimum 1500 MB)
   - Verifies root privileges
   - Validates GPFS installation and status

2. **Package Transfer**
   - Checks if package exists on remote host
   - Transfers package from controller if needed
   - Extracts tar archive to temporary directory

3. **Package Installation**
   - Installs packages in correct dependency order:
     - gskcrypt64 (Cryptographic library)
     - gskssl64 (SSL library)
     - TIVsm-API64 (64-bit API)
     - TIVsm-APIcit (API Common Interface)
     - TIVsm-BAGPFS (BA Client GPFS integration)
     - TIVsm-BA (BA Client)
     - TIVsm-BAcit (BA Client CIT)
     - TIVsm-HSM (HSM Client)
     - TIVsm-WEBGUI (Web GUI)

4. **Configuration**
   - Creates/updates dsm.sys with server settings
   - Creates/updates dsm.opt with client options
   - Sets appropriate file permissions

5. **Post-Installation**
   - Starts HSM daemon (if enabled)
   - Verifies installation
   - Cleans up temporary files

### AIX Installation (`state: present`)

1. **Pre-checks**
   - Validates system architecture (ppc64)
   - Checks available disk space
   - Verifies root privileges
   - Validates GPFS installation and status

2. **Package Transfer**
   - Checks if package exists on remote host
   - Transfers package from controller if needed
   - Extracts compressed tar archive

3. **Package Installation**
   - Installs BFF packages in dependency order:
     - GSKit8.gskcrypt64.ppc.rte
     - GSKit8.gskssl64.ppc.rte
     - TIVsm.client.api64
     - TIVsm.client.api64cit
     - tivoli.tsm.client.api.64bit
     - tivoli.tsm.client.ba.64bit.base
     - tivoli.tsm.client.ba.64bit.common
     - tivoli.tsm.client.ba.64bit.image
     - tivoli.tsm.client.ba.64bit.nas
     - tivoli.tsm.client.ba.64bit.web
     - tivoli.tsm.client.ba64.gpfs.base
     - tivoli.tsm.client.ba64.gpfs.common
     - tivoli.tsm.client.jbb.64bit
     - tivoli.tsm.client.webgui
     - TIVsm.client.hsm

4. **Configuration**
   - Creates/updates dsm.sys and dsm.opt
   - Configures GPFS integration

5. **Post-Installation**
   - Starts HSM daemon via /etc/rc.gpfshsm
   - Verifies installation

## Uninstallation Flow

### Linux Uninstallation (`state: absent`)

1. **Version Validation**
   - Checks installed version matches requested version
   - Fails if mismatch (unless `force_uninstall=true`)

2. **Backup**
   - Backs up configuration files to `/var/backups/hsm/`
   - Backs up RPM packages to `/opt/hsmClientPackagesBk/`

3. **Service Shutdown**
   - Stops dsmhsm service
   - Kills any running HSM processes

4. **Package Removal**
   - Uninstalls packages in reverse dependency order
   - Uses `rpm -e` for each package
   - Falls back to `rpm -e --nodeps` if needed

5. **Cleanup**
   - Removes extraction directory `/opt/hsmClient`
   - Optionally removes tar file from `/tmp`
   - Keeps configuration backups

### AIX Uninstallation (`state: absent`)

1. **Version Validation**
   - Checks installed version using `lslpp`
   - Validates version match

2. **Backup**
   - Backs up configuration files to `/var/backups/hsm/`
   - Backs up BFF packages to `/opt/hsmClientPackagesBk/`

3. **Service Shutdown**
   - Stops HSM daemon via `/etc/rc.gpfshsm stop`
   - Kills dsmhsm processes

4. **Package Removal**
   - Uninstalls packages using `installp -u`
   - Removes packages in reverse dependency order
   - Includes GPFS-specific packages

5. **Cleanup**
   - Removes extraction directory
   - Optionally removes tar file
   - Preserves configuration backups

## Configuration Files

### dsm.sys
**Location:** 
- Linux: `/opt/tivoli/tsm/client/hsm/bin/dsm.sys`
- AIX: `/opt/tivoli/tsm/client/hsm/bin/dsm.sys`

**Purpose:** Server connection settings

```
SErvername  TSM_SERVER
    TCPServeraddress  tsm.example.com
    TCPPort           1500
    NODENAME          hostname
    PASSWORDACCESS    GENERATE
    MANAGEDSERVICES   WEBCLIENT SCHEDULE HSM
```

### dsm.opt
**Location:**
- Linux: `/opt/tivoli/tsm/client/hsm/bin/dsm.opt`
- AIX: `/opt/tivoli/tsm/client/hsm/bin/dsm.opt`

**Purpose:** Client options

```
SErvername  TSM_SERVER
NODENAME    hostname
ERRORLOGNAME  /opt/tivoli/tsm/client/hsm/bin/dsmerror.log
SCHEDLOGNAME  /opt/tivoli/tsm/client/hsm/bin/dsmsched.log
MANAGEDSERVICES WEBCLIENT SCHEDULE HSM
```

## Rollback Mechanism

The role implements automatic rollback for failed operations:

### Installation Rollback
- Uninstalls all packages installed during failed attempt
- Removes temporary directories
- Restores system to pre-installation state

### Uninstallation Rollback
- Reinstalls packages from backup if uninstall fails
- Restores configuration files
- Restarts services

## Troubleshooting

### Installation Fails

**Check system requirements:**
```bash
# Linux
df -h /opt
rpm -qa | grep gpfs

# AIX
df -g /opt
lslpp -l | grep gpfs
```

**Verify package integrity:**
```bash
# Linux
tar -tzf /tmp/8.2.2.0-TIV-TSMHSM-LinuxX86.tar

# AIX
zcat /tmp/8.2.2.0-TIV-TSMHSM-AIXGPFS.tar.Z | tar -tvf -
```

**Check logs:**
```bash
tail -f /opt/tivoli/tsm/client/hsm/bin/dsmerror.log
```

### Uninstallation Fails

**Check installed packages:**
```bash
# Linux
rpm -qa | grep TIVsm

# AIX
lslpp -L | grep -Ei "TIVsm|tivoli.tsm"
```

**Force uninstall:**
```bash
ansible-playbook playbooks/hsm_client_install/playbooks/linux/hsm_client_uninstall_playbook.yml \
  -i inventory.ini \
  -e "hsm_client_version=8.2.2.0" \
  -e "force_uninstall=yes"
```

### GPFS Issues

**Check GPFS status:**
```bash
mmgetstate -a
mmlscluster
```

**Check HSM state:**
```bash
mmhsm state show
```

**Verify GPFS packages:**
```bash
# Linux
rpm -qa | grep gpfs

# AIX
lslpp -l | grep gpfs
```

## Best Practices

1. **Always verify GPFS status** before HSM operations
2. **Test in non-production** environment first
3. **Backup configuration files** before any changes
4. **Monitor disk space** during installation
5. **Keep package sources** for potential reinstallation
6. **Document custom configurations** in version control
7. **Use inventory variables** for host-specific settings
8. **Verify version compatibility** with your GPFS version

## Known Limitations

- Windows support not implemented in this role
- Requires GPFS to be pre-installed and configured
- Version mismatch during uninstall requires `force_uninstall=true`
- Cannot install multiple HSM versions simultaneously
- Package must be accessible on target host or controller

## Package Information

### Linux Packages (RPM)
- TIVsm-HSM - HSM Client
- TIVsm-BA - Backup-Archive Client
- TIVsm-BAcit - BA Client CIT
- TIVsm-BAGPFS - BA Client GPFS integration
- TIVsm-API64 - 64-bit API
- TIVsm-APIcit - API CIT
- TIVsm-WEBGUI - Web GUI
- gskssl64 - GSKit SSL
- gskcrypt64 - GSKit Crypto

### AIX Packages (BFF)
- TIVsm.client.hsm - HSM Client
- tivoli.tsm.client.ba.64bit.* - BA Client components
- tivoli.tsm.client.ba64.gpfs.* - GPFS-specific BA components
- tivoli.tsm.client.api.64bit - API
- tivoli.tsm.client.webgui - Web GUI
- GSKit8.* - GSKit libraries

## Support

For issues and questions:
- Check the troubleshooting section above
- Review logs in `/opt/tivoli/tsm/client/hsm/bin/`
- Consult IBM Storage Protect documentation
- Check GPFS status and logs

## License

IBM Storage Protect Ansible Collection
Copyright IBM Corporation 2024

## Author

IBM Storage Protect Team

## Version History

- **1.0.0** (2024): Initial release
  - Installation and uninstallation support
  - Linux (RHEL, SLES) and AIX support
  - Configuration management
  - Facts gathering
  - GPFS integration
  - Automatic rollback
  - Version validation

---
