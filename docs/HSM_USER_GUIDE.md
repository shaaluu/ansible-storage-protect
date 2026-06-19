# IBM Storage Protect HSM Client Ansible Automation - User Guide

## Document Information

| **Field** | **Value** |
|-----------|-----------|
| **Document Title** | HSM Client Ansible Automation - User Guide |
| **Version** | 1.0.0 |
| **Date** | 2024 |
| **Author** | IBM Storage Protect Team |
| **Audience** | System Administrators, DevOps Engineers |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Prerequisites](#2-prerequisites)
3. [Installation & Setup](#3-installation--setup)
4. [Quick Start Guide](#4-quick-start-guide)
5. [Configuration Guide](#5-configuration-guide)
6. [Operations Guide](#6-operations-guide)
7. [Troubleshooting](#7-troubleshooting)
8. [Best Practices](#8-best-practices)
9. [FAQ](#9-faq)
10. [Appendices](#10-appendices)

---

## 1. Introduction

### 1.1 What is HSM Client Ansible Automation?

The IBM Storage Protect HSM (Hierarchical Storage Management) Client Ansible Automation provides a comprehensive solution for automating the installation, configuration, and lifecycle management of HSM Client software across Linux and AIX platforms.

### 1.2 Key Benefits

- ✅ **Automated Deployment**: Install HSM Client on multiple hosts simultaneously
- ✅ **Idempotent Operations**: Safe to run multiple times without side effects
- ✅ **Automatic Rollback**: Automatically reverts changes if operations fail
- ✅ **Multi-Platform Support**: Works on Linux (RHEL, SLES) and AIX
- ✅ **GPFS Integration**: Validates IBM Spectrum Scale prerequisites
- ✅ **Configuration Management**: Centralized configuration with templates

### 1.3 What You Can Do

| **Operation** | **Description** |
|---------------|-----------------|
| Install | Fresh installation of HSM Client |
| Uninstall | Complete removal with cleanup |
| Configure | Update configuration files |
| Facts Gathering | Collect HSM Client information |
| Validation | Verify GPFS and system prerequisites |

### 1.4 Supported Platforms

| **Platform** | **Versions** | **Architectures** |
|--------------|--------------|-------------------|
| Red Hat Enterprise Linux | 7, 8, 9 | x86_64, s390x, ppc64le |
| SUSE Linux Enterprise Server | 12, 15 | x86_64, s390x, ppc64le |
| AIX | 7.1, 7.2, 7.3 | ppc64 |

---

## 2. Prerequisites

### 2.1 Control Node Requirements

The Ansible control node (where you run playbooks) requires:

| **Component** | **Requirement** |
|---------------|-----------------|
| Operating System | Linux, macOS, or WSL2 |
| Ansible | Version 2.9 or higher |
| Python | Version 3.6 or higher |
| SSH Access | Key-based authentication to target hosts |
| Network | Connectivity to target hosts |

**Installation:**
```bash
# Install Ansible
pip3 install ansible

# Verify installation
ansible --version
```

### 2.2 Target Host Requirements

#### 2.2.1 Critical Requirement: GPFS (IBM Spectrum Scale)

⚠️ **MANDATORY**: HSM Client requires IBM Spectrum Scale (GPFS) to be installed and running.

**Required GPFS Packages:**
```bash
# Linux
gpfs.base (>= 4.2.1-0)
gpfs.gpl
gpfs.gskit
gpfs.msg.en_US
gpfs.compression (recommended)
gpfs.license.std

# AIX
gpfs.base (>= 4.2.1-0)
gpfs.rte
gpfs.gskit
gpfs.msg.en_US
```

**Verify GPFS Installation:**
```bash
# Check GPFS packages
rpm -qa | grep -i '^gpfs\.'  # Linux
lslpp -l | grep -i '^gpfs\.' # AIX

# Check GPFS status
mmgetstate -a

# Expected output:
# Node number  Node name        GPFS state
# ------------------------------------------
#       1      hostname         active
```

#### 2.2.2 System Requirements

| **Resource** | **Minimum** | **Recommended** |
|--------------|-------------|-----------------|
| Disk Space | 1500 MB free | 3000 MB free |
| Memory | 512 MB | 1 GB |
| CPU | 1 core | 2 cores |
| Privileges | Root access | Root access |

#### 2.2.3 Software Requirements

- Python 3.6 or higher
- SSH server running
- sudo/root access configured

### 2.3 Network Requirements

| **Connection** | **Protocol** | **Port** | **Purpose** |
|----------------|--------------|----------|-------------|
| Control → Target | SSH | 22 | Ansible communication |
| Target → SP Server | TCP | 1500 | HSM Client communication |
| Target → GPFS | TCP | 1191 | GPFS cluster communication |

### 2.4 HSM Client Package

You need the HSM Client installation package:

**Linux:**
```
8.1.25.0-TIV-TSMHSM-LinuxX86.tar
```

**AIX:**
```
8.1.25.0-TIV-TSMHSM-AIX.tar.Z
```

Download from IBM Fix Central or your IBM representative.

---

## 3. Installation & Setup

### 3.1 Install Ansible Collection

#### Option 1: From Ansible Galaxy (Recommended)
```bash
ansible-galaxy collection install ibm.storage_protect
```

#### Option 2: From Source
```bash
# Clone repository
git clone https://github.com/IBM/ansible-storage-protect.git
cd ansible-storage-protect

# Install collection
ansible-galaxy collection install .
```

#### Option 3: Manual Installation
```bash
# Create directory structure
mkdir -p ~/.ansible/collections/ansible_collections/ibm/

# Copy collection
cp -r ansible-storage-protect ~/.ansible/collections/ansible_collections/ibm/storage_protect
```

### 3.2 Verify Installation

```bash
# List installed collections
ansible-galaxy collection list

# Expected output:
# ibm.storage_protect    1.0.0
```

### 3.3 Setup Inventory

Create an inventory file `inventory.ini`:

```ini
[hsm_servers]
hsm-node1 ansible_host=192.168.1.101
hsm-node2 ansible_host=192.168.1.102
hsm-node3 ansible_host=192.168.1.103

[hsm_servers:vars]
ansible_user=root
ansible_ssh_private_key_file=~/.ssh/id_rsa
ansible_python_interpreter=/usr/bin/python3
```

### 3.4 Test Connectivity

```bash
# Test SSH connectivity
ansible hsm_servers -i inventory.ini -m ping

# Expected output:
# hsm-node1 | SUCCESS => {
#     "changed": false,
#     "ping": "pong"
# }
```

### 3.5 Prepare HSM Client Package

```bash
# Copy package to control node
scp 8.1.25.0-TIV-TSMHSM-LinuxX86.tar /tmp/

# Or place on shared storage accessible to all target hosts
```

---

## 4. Quick Start Guide

### 4.1 Basic Installation (5 Minutes)

**Step 1: Create Variables File**

Create `vars/hsm_vars.yml`:
```yaml
---
hsm_client_version: "8.1.25.0"
hsm_client_state: "present"
linux_package_source: "/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar"
server_name: "TSM_PROD"
server_address: "tsm-server.example.com"
server_port: "1500"
hsm_client_start_daemon: true
```

**Step 2: Run Installation Playbook**

```bash
ansible-playbook \
  -i inventory.ini \
  ~/.ansible/collections/ansible_collections/ibm/storage_protect/playbooks/hsm_client_install/playbooks/linux/hsm_client_install_role_playbook.yml \
  -e "@vars/hsm_vars.yml" \
  -e "target_hosts=hsm_servers"
```

**Step 3: Verify Installation**

```bash
# Check HSM Client version
ansible hsm_servers -i inventory.ini -m shell -a "rpm -q TIVsm-HSM"

# Check daemon status
ansible hsm_servers -i inventory.ini -m shell -a "systemctl status dsmcad"
```

### 4.2 Quick Uninstallation

```bash
ansible-playbook \
  -i inventory.ini \
  ~/.ansible/collections/ansible_collections/ibm/storage_protect/playbooks/hsm_client_install/playbooks/linux/hsm_client_uninstall_playbook.yml \
  -e "hsm_client_version=8.1.25.0" \
  -e "linux_package_source=/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar" \
  -e "target_hosts=hsm_servers"
```

---

## 5. Configuration Guide

### 5.1 Variable Reference

#### 5.1.1 Required Variables

| **Variable** | **Type** | **Description** | **Example** |
|--------------|----------|-----------------|-------------|
| `hsm_client_version` | string | HSM Client version | `"8.1.25.0"` |
| `hsm_client_state` | string | Desired state | `"present"` or `"absent"` |
| `linux_package_source` | string | Path to package | `"/tmp/package.tar"` |

#### 5.1.2 Optional Variables

| **Variable** | **Type** | **Default** | **Description** |
|--------------|----------|-------------|-----------------|
| `hsm_install_path` | string | `/opt/tivoli/tsm/client/hsm/bin` | Installation directory |
| `hsm_temp_dir` | string | `/opt/hsmClient` | Temporary directory |
| `hsm_client_start_daemon` | boolean | `true` | Start daemon after install |
| `server_name` | string | `TSM_SERVER` | Storage Protect server name |
| `server_address` | string | - | Server hostname/IP |
| `server_port` | string | `1500` | Server port |
| `node_name` | string | `{{ ansible_hostname }}` | Client node name |
| `force_install` | boolean | `false` | Force reinstallation |
| `skip_gpfs_check` | boolean | `false` | Skip GPFS validation (testing only) |

### 5.2 Configuration Files

#### 5.2.1 dsm.sys Configuration

Location: `/opt/tivoli/tsm/client/hsm/bin/dsm.sys`

**Template:**
```
SErvername  {{ server_name }}
    TCPServeraddress  {{ server_address }}
    TCPPort           {{ server_port }}
    NODENAME          {{ node_name }}
    PASSWORDACCESS    GENERATE
    MANAGEDSERVICES   WEBCLIENT SCHEDULE HSM
    ERRORLOGNAME      {{ hsm_install_path }}/dsmerror.log
    SCHEDLOGNAME      {{ hsm_install_path }}/dsmsched.log
```

**Customize:**
```yaml
# In your vars file
dsm_sys_options:
  COMPRESSION: "yes"
  COMPRESSALWAYS: "no"
  RESOURCEUTILIZATION: "5"
  TCPWINDOWSIZE: "63"
```

#### 5.2.2 dsm.opt Configuration

Location: `/opt/tivoli/tsm/client/hsm/bin/dsm.opt`

**Template:**
```
SErvername  {{ server_name }}
NODENAME    {{ node_name }}
ERRORLOGNAME  {{ hsm_install_path }}/dsmerror.log
SCHEDLOGNAME  {{ hsm_install_path }}/dsmsched.log
MANAGEDSERVICES WEBCLIENT SCHEDULE HSM
```

### 5.3 Advanced Configuration Examples

#### 5.3.1 Multi-Server Configuration

```yaml
# vars/multi_server.yml
---
hsm_servers:
  - name: "TSM_PROD"
    address: "tsm-prod.example.com"
    port: "1500"
  - name: "TSM_DR"
    address: "tsm-dr.example.com"
    port: "1500"

# Use in playbook
server_name: "{{ hsm_servers[0].name }}"
server_address: "{{ hsm_servers[0].address }}"
server_port: "{{ hsm_servers[0].port }}"
```

#### 5.3.2 Environment-Specific Configuration

```yaml
# vars/dev.yml
---
hsm_client_version: "8.1.25.0"
server_name: "TSM_DEV"
server_address: "tsm-dev.example.com"

# vars/prod.yml
---
hsm_client_version: "8.1.25.0"
server_name: "TSM_PROD"
server_address: "tsm-prod.example.com"

# Run with specific environment
ansible-playbook playbook.yml -e "@vars/prod.yml"
```

---

## 6. Operations Guide

### 6.1 Installation Operations

#### 6.1.1 Fresh Installation

**Linux:**
```bash
ansible-playbook \
  -i inventory.ini \
  ~/.ansible/collections/ansible_collections/ibm/storage_protect/playbooks/hsm_client_install/playbooks/linux/hsm_client_install_role_playbook.yml \
  -e "hsm_client_version=8.1.25.0" \
  -e "linux_package_source=/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar" \
  -e "target_hosts=hsm_servers"
```

**AIX:**
```bash
ansible-playbook \
  -i inventory.ini \
  ~/.ansible/collections/ansible_collections/ibm/storage_protect/playbooks/hsm_client_install/playbooks/aix/hsm_client_install_role_playbook.yml \
  -e "hsm_client_version=8.1.25.0" \
  -e "aix_package_source=/tmp/8.1.25.0-TIV-TSMHSM-AIX.tar.Z" \
  -e "target_hosts=aix_servers"
```

#### 6.1.2 Installation with Custom Options

```bash
ansible-playbook \
  -i inventory.ini \
  playbook.yml \
  -e "hsm_client_version=8.1.25.0" \
  -e "linux_package_source=/tmp/package.tar" \
  -e "hsm_install_path=/opt/custom/hsm" \
  -e "hsm_client_start_daemon=false" \
  -e "server_name=CUSTOM_SERVER" \
  -e "server_address=custom.example.com" \
  -e "target_hosts=hsm_servers"
```

#### 6.1.3 Parallel Installation (Multiple Hosts)

```bash
# Install on all hosts in parallel (default: 5 forks)
ansible-playbook -i inventory.ini playbook.yml -e "target_hosts=hsm_servers"

# Increase parallelism
ansible-playbook -i inventory.ini playbook.yml -e "target_hosts=hsm_servers" -f 10

# Serial installation (one at a time)
ansible-playbook -i inventory.ini playbook.yml -e "target_hosts=hsm_servers" -f 1
```

### 6.2 Uninstallation Operations

#### 6.2.1 Standard Uninstallation

```bash
ansible-playbook \
  -i inventory.ini \
  ~/.ansible/collections/ansible_collections/ibm/storage_protect/playbooks/hsm_client_install/playbooks/linux/hsm_client_uninstall_playbook.yml \
  -e "hsm_client_version=8.1.25.0" \
  -e "linux_package_source=/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar" \
  -e "target_hosts=hsm_servers"
```

#### 6.2.2 Force Uninstallation

```bash
# Uninstall regardless of version mismatch
ansible-playbook \
  -i inventory.ini \
  playbook.yml \
  -e "hsm_client_state=absent" \
  -e "force=true" \
  -e "target_hosts=hsm_servers"
```

### 6.3 Configuration Operations

#### 6.3.1 Update Configuration

```bash
ansible-playbook \
  -i inventory.ini \
  ~/.ansible/collections/ansible_collections/ibm/storage_protect/playbooks/hsm_client_install/playbooks/linux/hsm_client_config_playbook.yml \
  -e "server_name=NEW_SERVER" \
  -e "server_address=new-server.example.com" \
  -e "target_hosts=hsm_servers"
```

#### 6.3.2 Reconfigure Existing Installation

```bash
# Update only configuration files
ansible hsm_servers -i inventory.ini -m template \
  -a "src=templates/dsm.sys.j2 dest=/opt/tivoli/tsm/client/hsm/bin/dsm.sys mode=0600" \
  -e "server_name=NEW_SERVER" \
  -e "server_address=new-server.example.com"
```

### 6.4 Facts Gathering

#### 6.4.1 Gather HSM Client Information

```bash
ansible-playbook \
  -i inventory.ini \
  ~/.ansible/collections/ansible_collections/ibm/storage_protect/playbooks/hsm_client_install/playbooks/linux/hsm_client_facts_playbook.yml \
  -e "target_hosts=hsm_servers"
```

#### 6.4.2 Check Specific Information

```bash
# Check version
ansible hsm_servers -i inventory.ini -m shell -a "rpm -q TIVsm-HSM"

# Check GPFS status
ansible hsm_servers -i inventory.ini -m shell -a "mmgetstate -a"

# Check HSM status
ansible hsm_servers -i inventory.ini -m shell -a "mmhsm state show"

# Check daemon status
ansible hsm_servers -i inventory.ini -m shell -a "systemctl status dsmcad"
```

### 6.5 Daemon Management

#### 6.5.1 Start Daemon

```bash
ansible hsm_servers -i inventory.ini -m systemd \
  -a "name=dsmcad state=started enabled=yes"
```

#### 6.5.2 Stop Daemon

```bash
ansible hsm_servers -i inventory.ini -m systemd \
  -a "name=dsmcad state=stopped"
```

#### 6.5.3 Restart Daemon

```bash
ansible hsm_servers -i inventory.ini -m systemd \
  -a "name=dsmcad state=restarted"
```

#### 6.5.4 Check Daemon Status

```bash
ansible hsm_servers -i inventory.ini -m shell \
  -a "systemctl status dsmcad"
```

---

## 7. Troubleshooting

### 7.1 Common Issues

#### 7.1.1 GPFS Not Installed

**Error:**
```
FAILED! => {"msg": "GPFS is not installed (REQUIRED for HSM)"}
```

**Solution:**
```bash
# Verify GPFS installation
rpm -qa | grep -i '^gpfs\.'

# Install GPFS if missing
# Contact your GPFS administrator or IBM support
```

**Temporary Bypass (Testing Only):**
```bash
ansible-playbook playbook.yml -e "skip_gpfs_check=true"
```

#### 7.1.2 Insufficient Disk Space

**Error:**
```
FAILED! => {"msg": "Insufficient disk space. Required: 1500 MB, Available: 800 MB"}
```

**Solution:**
```bash
# Check disk space
df -h /opt

# Clean up space
rm -rf /tmp/old_files
yum clean all

# Or use different directory
ansible-playbook playbook.yml -e "hsm_temp_dir=/data/hsmClient"
```

#### 7.1.3 Package Not Found

**Error:**
```
FAILED! => {"msg": "Package source not found: /tmp/package.tar"}
```

**Solution:**
```bash
# Verify package exists on control node
ls -lh /tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar

# Copy to target hosts first
ansible hsm_servers -i inventory.ini -m copy \
  -a "src=/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar dest=/tmp/"

# Or use correct path
ansible-playbook playbook.yml -e "linux_package_source=/correct/path/package.tar"
```

#### 7.1.4 Version Mismatch

**Error:**
```
FAILED! => {"msg": "Version mismatch: Installed version is 8.1.25.0, but requested uninstall version is 8.1.24.0"}
```

**Solution:**
```bash
# Check installed version
ansible hsm_servers -i inventory.ini -m shell -a "rpm -q TIVsm-HSM"

# Use correct version
ansible-playbook playbook.yml -e "hsm_client_version=8.1.25.0"

# Or force uninstall
ansible-playbook playbook.yml -e "force=true"
```

#### 7.1.5 Installation Already Exists

**Error:**
```
FAILED! => {"msg": "HSM Client version 8.1.25.0 is already installed"}
```

**Solution:**
```bash
# This is expected behavior (idempotency)
# To reinstall, first uninstall:
ansible-playbook uninstall_playbook.yml

# Then install:
ansible-playbook install_playbook.yml

# Or use force:
ansible-playbook install_playbook.yml -e "force=true"
```

### 7.2 Debugging

#### 7.2.1 Enable Verbose Output

```bash
# Level 1: Basic info
ansible-playbook playbook.yml -v

# Level 2: More details
ansible-playbook playbook.yml -vv

# Level 3: Debug level
ansible-playbook playbook.yml -vvv

# Level 4: Connection debug
ansible-playbook playbook.yml -vvvv
```

#### 7.2.2 Check Logs

**Ansible Logs:**
```bash
# Enable logging in ansible.cfg
[defaults]
log_path = /var/log/ansible.log

# View logs
tail -f /var/log/ansible.log
```

**HSM Client Logs:**
```bash
# Error log
tail -f /opt/tivoli/tsm/client/hsm/bin/dsmerror.log

# Schedule log
tail -f /opt/tivoli/tsm/client/hsm/bin/dsmsched.log

# System log
journalctl -u dsmcad -f
```

#### 7.2.3 Test Individual Tasks

```bash
# Test SSH connectivity
ansible hsm_servers -i inventory.ini -m ping

# Test privilege escalation
ansible hsm_servers -i inventory.ini -m shell -a "whoami" --become

# Test package query
ansible hsm_servers -i inventory.ini -m shell -a "rpm -q TIVsm-HSM"

# Test GPFS
ansible hsm_servers -i inventory.ini -m shell -a "mmgetstate -a"
```

### 7.3 Rollback Scenarios

#### 7.3.1 Automatic Rollback

The automation automatically rolls back on failure:

```
Installation failed → Removes installed packages
Uninstallation failed → Restores packages and configs
Configuration failed → Restores previous configuration
```

#### 7.3.2 Manual Rollback

If automatic rollback fails:

```bash
# Restore from backup
ansible hsm_servers -i inventory.ini -m copy \
  -a "src=/opt/hsmClientPackagesBk/dsm.sys dest=/opt/tivoli/tsm/client/hsm/bin/dsm.sys remote_src=yes"

# Reinstall from backup
ansible hsm_servers -i inventory.ini -m shell \
  -a "rpm -ivh /opt/hsmClientPackagesBk/*.rpm"
```

### 7.4 Performance Issues

#### 7.4.1 Slow Installation

**Causes:**
- Large package size
- Slow network
- Limited resources

**Solutions:**
```bash
# Use local repository
# Copy package to all hosts first
ansible hsm_servers -i inventory.ini -m copy \
  -a "src=/tmp/package.tar dest=/tmp/"

# Increase parallelism
ansible-playbook playbook.yml -f 10

# Use faster network
# Configure in inventory.ini
ansible_connection=ssh
ansible_ssh_common_args='-o Compression=yes -o ControlMaster=auto -o ControlPersist=60s'
```

#### 7.4.2 Timeout Issues

```bash
# Increase timeout in ansible.cfg
[defaults]
timeout = 60

# Or in playbook
- name: Install HSM Client
  async: 3600
  poll: 10
```

---

## 8. Best Practices

### 8.1 Pre-Installation

✅ **DO:**
- Verify GPFS is installed and running
- Check disk space (minimum 1500 MB)
- Test SSH connectivity
- Backup existing configuration
- Review system requirements
- Test in non-production first

❌ **DON'T:**
- Skip GPFS validation in production
- Install without sufficient disk space
- Run without testing connectivity
- Ignore prerequisite checks

### 8.2 During Installation

✅ **DO:**
- Monitor installation progress
- Check logs for errors
- Verify each step completes
- Use verbose mode for troubleshooting
- Keep package sources available

❌ **DON'T:**
- Interrupt running playbooks
- Modify files during installation
- Run multiple installations simultaneously on same host
- Ignore warning messages

### 8.3 Post-Installation

✅ **DO:**
- Verify installation success
- Test HSM Client connectivity
- Check daemon status
- Document configuration
- Backup configuration files
- Test rollback procedures

❌ **DON'T:**
- Delete package sources immediately
- Skip post-installation verification
- Forget to enable daemon
- Leave default passwords

### 8.4 Configuration Management

✅ **DO:**
- Use version control for playbooks
- Store sensitive data in Ansible Vault
- Use variables for environment-specific settings
- Document custom configurations
- Test configuration changes

❌ **DON'T:**
- Hardcode passwords in playbooks
- Store credentials in plain text
- Skip configuration validation
- Make manual changes without documentation

### 8.5 Maintenance

✅ **DO:**
- Regularly update Ansible collection
- Monitor HSM Client logs
- Keep package sources for rollback
- Document all changes
- Test upgrades in non-production

❌ **DON'T:**
- Skip regular maintenance
- Ignore log warnings
- Delete backup files prematurely
- Upgrade without testing

---

## 9. FAQ

### 9.1 General Questions

**Q: Can I install HSM Client without GPFS?**
A: No. GPFS (IBM Spectrum Scale) is a mandatory prerequisite for HSM Client. HSM requires GPFS for file system hooks and policy-based management.

**Q: Can I upgrade HSM Client in-place?**
A: No. The automation does not support in-place upgrades. You must uninstall the current version first, then install the new version.

**Q: Is the automation idempotent?**
A: Yes. You can run the playbooks multiple times safely. If HSM Client is already installed at the desired version, no changes will be made.

**Q: What happens if installation fails?**
A: The automation automatically rolls back changes, removing any installed packages and restoring the system to its previous state.

**Q: Can I install on multiple hosts simultaneously?**
A: Yes. Use Ansible's fork parameter to control parallelism: `ansible-playbook playbook.yml -f 10`

### 9.2 Configuration Questions

**Q: How do I change the server address after installation?**
A: Run the configuration playbook with new values:
```bash
ansible-playbook config_playbook.yml -e "server_address=new-server.example.com"
```

**Q: Where are configuration files located?**
A: Default location: `/opt/tivoli/tsm/client/hsm/bin/`
- dsm.sys
- dsm.opt
- dsmerror.log
- dsmsched.log

**Q: Can I customize installation paths?**
A: Yes, use the `hsm_install_path` variable:
```bash
ansible-playbook playbook.yml -e "hsm_install_path=/custom/path"
```

**Q: How do I configure multiple Storage Protect servers?**
A: Add multiple server stanzas in dsm.sys. See Section 5.3.1 for examples.

### 9.3 Troubleshooting Questions

**Q: Installation fails with "GPFS not installed" error. What should I do?**
A: Install and configure GPFS first. HSM Client cannot function without it. Contact your GPFS administrator or IBM support.

**Q: How do I check if HSM Client is working?**
A: Run these commands:
```bash
# Check version
rpm -q TIVsm-HSM

# Check daemon
systemctl status dsmcad

# Check HSM status
mmhsm state show

# Test connection
dsmc query session
```

**Q: Where can I find error logs?**
A: Check these locations:
- `/opt/tivoli/tsm/client/hsm/bin/dsmerror.log`
- `/opt/tivoli/tsm/client/hsm/bin/dsmsched.log`
- `journalctl -u dsmcad`

**Q: How do I perform a manual rollback?**
A: See Section 7.3.2 for manual rollback procedures.

### 9.4 Platform-Specific Questions

**Q: Are there differences between Linux and AIX installation?**
A: Yes:
- Package format: `.tar` (Linux) vs `.tar.Z` (AIX)
- Package manager: RPM (Linux) vs installp (AIX)
- Package names: Different GSKit packages
- Paths may vary

**Q: Which Linux distributions are supported?**
A: RHEL 7/8/9 and SLES 12/15 on x86_64, s390x, and ppc64le architectures.

**Q: Can I use this on Ubuntu or Debian?**
A: Not officially supported. The automation is designed for RHEL and SLES.

---

## 10. Appendices

### 10.1 Complete Playbook Examples

#### 10.1.1 Production Installation Playbook

```yaml
---
- name: Install HSM Client in Production
  hosts: "{{ target_hosts | default('hsm_servers') }}"
  become: true
  gather_facts: true
  
  vars:
    hsm_client_version: "8.1.25.0"
    hsm_client_state: "present"
    linux_package_source: "/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar"
    server_name: "TSM_PROD"
    server_address: "tsm-prod.example.com"
    server_port: "1500"
    hsm_client_start_daemon: true
    hsm_install_path: "/opt/tivoli/tsm/client/hsm/bin"
    
  pre_tasks:
    - name: Verify GPFS is running
      command: mmgetstate -a
      register: gpfs_state
      changed_when: false
      
    - name: Fail if GPFS is not active
      fail:
        msg: "GPFS is not active. HSM requires GPFS."
      when: "'active' not in gpfs_state.stdout"
      
  roles:
    - ibm.storage_protect.hsm_client_install
    
  post_tasks:
    - name: Verify HSM Client installation
      command: rpm -q TIVsm-HSM
      register: hsm_version
      changed_when: false
      
    - name: Display installation result
      debug:
        msg: "HSM Client installed: {{ hsm_version.stdout }}"
```

#### 10.1.2 Multi-Environment Playbook

```yaml
---
- name: Install HSM Client - Multi-Environment
  hosts: "{{ target_hosts }}"
  become: true
  
  vars_files:
    - "vars/{{ environment }}.yml"
    
  roles:
    - ibm.storage_protect.hsm_client_install

# Run with:
# ansible-playbook playbook.yml -e "environment=dev target_hosts=dev_servers"
# ansible-playbook playbook.yml -e "environment=prod target_hosts=prod_servers"
```

### 10.2 Inventory Examples

#### 10.2.1 Simple Inventory

```ini
[hsm_servers]
hsm-node1 ansible_host=192.168.1.101
hsm-node2 ansible_host=192.168.1.102

[hsm_servers:vars]
ansible_user=root
ansible_python_interpreter=/usr/bin/python3
```

#### 10.2.2 Advanced Inventory

```ini
[hsm_linux]
hsm-rhel8-1 ansible_host=192.168.1.101
hsm-rhel8-2 ansible_host=192.168.1.102
hsm-sles15-1 ansible_host=192.168.1.103

[hsm_aix]
hsm-aix72-1 ansible_host=192.168.1.201
hsm-aix72-2 ansible_host=192.168.1.202

[hsm_linux:vars]
ansible_user=root
ansible_python_interpreter=/usr/bin/python3
linux_package_source=/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar

[hsm_aix:vars]
ansible_user=root
ansible_python_interpreter=/usr/bin/python3
aix_package_source=/tmp/8.1.25.0-TIV-TSMHSM-AIX.tar.Z

[hsm_servers:children]
hsm_linux
hsm_aix

[hsm_servers:vars]
hsm_client_version=8.1.25.0
server_name=TSM_PROD
server_address=tsm-prod.example.com
```

### 10.3 Ansible Configuration

#### 10.3.1 ansible.cfg Example

```ini
[defaults]
inventory = inventory.ini
remote_user = root
host_key_checking = False
timeout = 60
forks = 5
log_path = /var/log/ansible.log
retry_files_enabled = False
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 3600

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o Compression=yes
pipelining = True
control_path = /tmp/ansible-ssh-%%h-%%p-%%r
```

### 10.4 Command Reference

#### 10.4.1 Installation Commands

```bash
# Basic installation
ansible-playbook install_playbook.yml

# With custom variables
ansible-playbook install_playbook.yml -e "hsm_client_version=8.1.25.0"

# Specific hosts
ansible-playbook install_playbook.yml -l hsm-node1,hsm-node2

# Check mode (dry run)
ansible-playbook install_playbook.yml --check

# Step-by-step execution
ansible-playbook install_playbook.yml --step

# Start from specific task
ansible-playbook install_playbook.yml --start-at-task="Install HSM packages"
```

#### 10.4.2 Ad-hoc Commands

```bash
# Check HSM version
ansible hsm_servers -m shell -a "rpm -q TIVsm-HSM"

# Check GPFS status
ansible hsm_servers -m shell -a "mmgetstate -a"

# Check daemon status
ansible hsm_servers -m systemd -a "name=dsmcad state=started"

# Copy file to all hosts
ansible hsm_servers -m copy -a "src=/tmp/file dest=/tmp/"

# Run command on all hosts
ansible hsm_servers -m shell -a "df -h /opt"
```

### 10.5 Useful Scripts

#### 10.5.1 Pre-Installation Check Script

```bash
#!/bin/bash
# pre_install_check.sh

echo "=== HSM Client Pre-Installation Check ==="

# Check GPFS
echo "Checking GPFS..."
if rpm -qa | grep -q '^gpfs\.'; then
    echo "✓ GPFS packages found"
    mmgetstate -a
else
    echo "✗ GPFS not installed"
    exit 1
fi

# Check disk space
echo "Checking disk space..."
AVAILABLE=$(df -m /opt | tail -1 | awk '{print $4}')
if [ $AVAILABLE -gt 1500 ]; then
    echo "✓ Sufficient disk space: ${AVAILABLE}MB"
else
    echo "✗ Insufficient disk space: ${AVAILABLE}MB (need 1500MB)"
    exit 1
fi

# Check Python
echo "Checking Python..."
if command -v python3 &> /dev/null; then
    echo "✓ Python3 found: $(python3 --version)"
else
    echo "✗ Python3 not found"
    exit 1
fi

echo "=== All checks passed ==="
```

#### 10.5.2 Post-Installation Verification Script

```bash
#!/bin/bash
# post_install_verify.sh

echo "=== HSM Client Post-Installation Verification ==="

# Check packages
echo "Checking installed packages..."
for pkg in gskcrypt64 gskssl64 TIVsm-API64 TIVsm-APIcit TIVsm-HSM TIVsm-HSMcit; do
    if rpm -q $pkg &> /dev/null; then
        echo "✓ $pkg installed"
    else
        echo "✗ $pkg not installed"
    fi
done

# Check daemon
echo "Checking daemon..."
if systemctl is-active dsmcad &> /dev/null; then
    echo "✓ dsmcad is running"
else
    echo "✗ dsmcad is not running"
fi

# Check configuration
echo "Checking configuration files..."
for file in dsm.sys dsm.opt; do
    if [ -f "/opt/tivoli/tsm/client/hsm/bin/$file" ]; then
        echo "✓ $file exists"
    else
        echo "✗ $file missing"
    fi
done

# Check HSM status
echo "Checking HSM status..."
mmhsm state show

echo "=== Verification complete ==="
```

### 10.6 Glossary

| **Term** | **Definition** |
|----------|----------------|
| **HSM** | Hierarchical Storage Management - automated data migration between storage tiers |
| **GPFS** | General Parallel File System (IBM Spectrum Scale) - clustered file system |
| **BA Client** | Backup-Archive Client - IBM Storage Protect client for backup operations |
| **SP Server** | Storage Protect Server - central server managing backups and archives |
| **Stub File** | Placeholder file for migrated data, contains metadata for recall |
| **Policy** | Rules defining when and how files are migrated between storage tiers |
| **Migration** | Moving data from primary to secondary storage |
| **Recall** | Retrieving migrated data back to primary storage |
| **Idempotent** | Operation that produces same result regardless of how many times executed |
| **Rollback** | Reverting changes to previous state after failure |

### 10.7 Support & Resources

#### 10.7.1 Documentation

- IBM Storage Protect Documentation: https://www.ibm.com/docs/en/storage-protect
- IBM Spectrum Scale Documentation: https://www.ibm.com/docs/en/spectrum-scale
- Ansible Documentation: https://docs.ansible.com/
- Collection Repository: https://github.com/IBM/ansible-storage-protect

#### 10.7.2 Support Channels

- IBM Support: https://www.ibm.com/support
- GitHub Issues: https://github.com/IBM/ansible-storage-protect/issues
- IBM Community: https://community.ibm.com/

#### 10.7.3 Training Resources

- Ansible Getting Started: https://docs.ansible.com/ansible/latest/user_guide/intro_getting_started.html
- IBM Storage Protect Training: Contact IBM Training
- GPFS Administration: IBM Spectrum Scale training courses

---

## Document Control

| **Version** | **Date** | **Author** | **Changes** |
|-------------|----------|------------|-------------|
| 1.0.0 | 2024 | IBM Storage Protect Team | Initial release |

---

**End of User Guide**

For additional assistance, please contact IBM Support or refer to the Design Document for technical details.