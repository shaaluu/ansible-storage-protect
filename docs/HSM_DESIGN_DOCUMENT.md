# IBM Storage Protect HSM Client Ansible Automation - Design Document

## Document Information

| **Field** | **Value** |
|-----------|-----------|
| **Document Title** | HSM Client Ansible Automation - Design Document |
| **Version** | 1.0.0 |
| **Date** | 2024 |
| **Author** | IBM Storage Protect Team |
| **Status** | Active |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Architecture Design](#3-architecture-design)
4. [Component Design](#4-component-design)
5. [Data Flow](#5-data-flow)
6. [Security Design](#6-security-design)
7. [Error Handling & Rollback](#7-error-handling--rollback)
8. [Performance Considerations](#8-performance-considerations)
9. [Testing Strategy](#9-testing-strategy)
10. [Deployment Architecture](#10-deployment-architecture)
11. [Appendices](#11-appendices)

---

## 1. Executive Summary

### 1.1 Purpose
This document describes the design and architecture of the IBM Storage Protect Hierarchical Storage Management (HSM) Client Ansible automation solution. The solution provides automated installation, configuration, and lifecycle management of HSM Client software across Linux and AIX platforms.

### 1.2 Scope
The automation covers:
- HSM Client installation on Linux (RHEL 7/8/9, SLES) and AIX (7.1+)
- HSM Client uninstallation with automatic rollback
- Configuration management (dsm.sys, dsm.opt)
- GPFS prerequisite validation
- Facts gathering and system verification
- Daemon lifecycle management

### 1.3 Key Features
- **Idempotent Operations**: Safe to run multiple times
- **Automatic Rollback**: Reverts changes on failure
- **Multi-Platform Support**: Linux and AIX
- **GPFS Integration**: Validates IBM Spectrum Scale prerequisites
- **Comprehensive Validation**: Pre-flight and post-installation checks

---

## 2. System Overview

### 2.1 System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                     Ansible Control Node                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  HSM Ansible Collection                                   │  │
│  │  - Roles                                                   │  │
│  │  - Modules                                                 │  │
│  │  - Playbooks                                               │  │
│  │  - Module Utils                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SSH/WinRM
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Target Hosts                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Linux RHEL   │  │ Linux SLES   │  │ AIX 7.1+     │          │
│  │ - GPFS       │  │ - GPFS       │  │ - GPFS       │          │
│  │ - HSM Client │  │ - HSM Client │  │ - HSM Client │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ TCP/IP
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              IBM Storage Protect Server                          │
│  - Policy Management                                             │
│  - Storage Pools                                                 │
│  - Node Registration                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| **Layer** | **Technology** |
|-----------|----------------|
| Automation Framework | Ansible 2.9+ |
| Programming Language | Python 3.6+ |
| Target OS | RHEL 7/8/9, SLES, AIX 7.1+ |
| Package Management | RPM (Linux), installp (AIX) |
| File System | IBM Spectrum Scale (GPFS) |
| Configuration | YAML, Jinja2 Templates |

---

## 3. Architecture Design

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Ansible Collection Layer                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │   Playbooks    │  │     Roles      │  │    Modules     │   │
│  │                │  │                │  │                │   │
│  │ - Install      │  │ - hsm_client_  │  │ - hsm_client_  │   │
│  │ - Uninstall    │  │   install      │  │   install      │   │
│  │ - Configure    │  │ - system_info  │  │ - hsm_client_  │   │
│  │ - Facts        │  │                │  │   facts        │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                    Module Utils Layer                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  HSMClientHelper                                        │    │
│  │  - install_hsm_client()                                 │    │
│  │  - uninstall_hsm_client()                               │    │
│  │  - configure_hsm_client()                               │    │
│  │  - verify_system_prereqs()                              │    │
│  │  - rollback()                                           │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  HSMConstants                                           │    │
│  │  - Package names, paths, error messages                │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Interaction

```
┌──────────────┐
│  Playbook    │
└──────┬───────┘
       │
       │ calls
       ▼
┌──────────────┐
│     Role     │
└──────┬───────┘
       │
       │ includes tasks
       ▼
┌──────────────┐
│    Tasks     │
└──────┬───────┘
       │
       │ invokes
       ▼
┌──────────────┐
│   Module     │
└──────┬───────┘
       │
       │ uses
       ▼
┌──────────────┐
│ Module Utils │
└──────┬───────┘
       │
       │ executes on
       ▼
┌──────────────┐
│ Target Host  │
└──────────────┘
```

---

## 4. Component Design

### 4.1 Role: hsm_client_install

#### 4.1.1 Purpose
Main orchestration role for HSM Client lifecycle management.

#### 4.1.2 Structure
```
hsm_client_install/
├── defaults/
│   └── main.yml                    # Default variables
├── meta/
│   └── main.yml                    # Role metadata
├── tasks/
│   ├── main.yml                    # Entry point
│   ├── determine_action.yml        # Action determination logic
│   ├── local_repo_check.yml        # Package validation
│   ├── gpfs_prerequisite_check.yml # GPFS validation
│   ├── hsm_client_install_linux.yml
│   ├── hsm_client_install_aix.yml
│   ├── hsm_client_uninstall_linux.yml
│   └── hsm_client_uninstall_aix.yml
└── README.md
```

#### 4.1.3 Task Flow

**Installation Flow (state: present)**
```
┌─────────────────────────┐
│ local_repo_check.yml    │
│ - Validate package      │
│ - Check version format  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ determine_action.yml    │
│ - Compare versions      │
│ - Set action: install   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ gpfs_prerequisite_check │
│ - Verify GPFS installed │
│ - Check GPFS status     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ system_info role        │
│ - Gather system facts   │
│ - Validate requirements │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ hsm_client_install_*.yml│
│ - Pre-checks            │
│ - Extract packages      │
│ - Install packages      │
│ - Configure client      │
│ - Start daemon          │
│ - Post-verification     │
└─────────────────────────┘
```

**Uninstallation Flow (state: absent)**
```
┌─────────────────────────┐
│ Pre-checks              │
│ - Verify installed      │
│ - Check GPFS/HSM status │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Backup                  │
│ - Config files          │
│ - Package files         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ hsm_client_uninstall_*  │
│ - Stop daemon           │
│ - Deactivate HSM        │
│ - Uninstall packages    │
│ - Cleanup directories   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Rollback (on failure)   │
│ - Restore configs       │
│ - Reinstall packages    │
└─────────────────────────┘
```

### 4.2 Module: hsm_client_install

#### 4.2.1 Purpose
Core module for HSM Client installation and uninstallation operations.

#### 4.2.2 Parameters

| **Parameter** | **Type** | **Required** | **Default** | **Description** |
|---------------|----------|--------------|-------------|-----------------|
| state | str | No | present | Desired state (present/absent) |
| hsm_client_version | str | Yes | - | Version to install |
| package_source | str | Yes | - | Path to installation package |
| install_path | str | No | /opt/tivoli/tsm/client/hsm/bin | Installation directory |
| force | bool | No | false | Force reinstallation |
| temp_dir | str | No | /opt/hsmClient | Temporary directory |
| start_daemon | bool | No | true | Start daemon after install |

#### 4.2.3 Return Values

| **Key** | **Type** | **Description** |
|---------|----------|-----------------|
| changed | bool | Whether changes were made |
| msg | str | Operation summary message |
| version | str | Installed version |
| is_installation_successful | bool | Installation success status |

### 4.3 Module Utils: HSMClientHelper

#### 4.3.1 Class Design

```python
class HSMClientHelper:
    """Helper class for HSM Client operations"""
    
    def __init__(self, module):
        """Initialize with Ansible module instance"""
        
    # Installation Methods
    def install_hsm_client(self, package_source, install_path, temp_dir)
    def uninstall_hsm_client(self)
    def configure_hsm_client(self)
    
    # Validation Methods
    def verify_system_prereqs(self)
    def check_installed(self)
    def post_installation_verification(self, version, action)
    
    # GPFS Methods
    def check_gpfs_installed(self)
    def check_gpfs_status(self)
    def check_hsm_status(self)
    
    # Daemon Methods
    def start_hsm_daemon(self, should_start)
    def stop_hsm_daemon(self)
    
    # Rollback Methods
    def rollback(self, action, previous_version)
    def backup_configuration(self)
    def restore_configuration(self)
    
    # Utility Methods
    def file_exists(self, path)
    def run_command(self, cmd)
    def log(self, message)
```

#### 4.3.2 Key Methods

**install_hsm_client()**
```python
def install_hsm_client(self, package_source, install_path, temp_dir):
    """
    Install HSM Client from package source
    
    Steps:
    1. Create temporary directory
    2. Extract package
    3. Install packages in dependency order:
       - gskcrypt64
       - gskssl64
       - TIVsm-API64
       - TIVsm-APIcit
       - TIVsm-HSM
       - TIVsm-HSMcit
    4. Verify installation
    5. Cleanup temporary files
    """
```

**uninstall_hsm_client()**
```python
def uninstall_hsm_client(self):
    """
    Uninstall HSM Client
    
    Steps:
    1. Stop HSM daemon
    2. Deactivate HSM (if active)
    3. Backup configuration
    4. Uninstall packages in reverse order
    5. Remove directories
    6. Verify uninstallation
    """
```

**rollback()**
```python
def rollback(self, action, previous_version):
    """
    Rollback failed operation
    
    For install: Remove installed packages
    For uninstall: Restore packages and configs
    For upgrade: Restore previous version
    """
```

### 4.4 Module Utils: HSMConstants

#### 4.4.1 Purpose
Centralized constants for HSM Client operations.

#### 4.4.2 Constants

```python
class HSMConstants:
    # Package Names
    LINUX_PACKAGES = [
        'gskcrypt64',
        'gskssl64',
        'TIVsm-API64',
        'TIVsm-APIcit',
        'TIVsm-HSM',
        'TIVsm-HSMcit'
    ]
    
    AIX_PACKAGES = [
        'gsk8cry64',
        'gsk8ssl64',
        'TIVsm-API64',
        'TIVsm-APIcit',
        'TIVsm-HSM',
        'TIVsm-HSMcit'
    ]
    
    # Paths
    DEFAULT_INSTALL_PATH = '/opt/tivoli/tsm/client/hsm/bin'
    DEFAULT_TEMP_DIR = '/opt/hsmClient'
    CONFIG_DIR = '/opt/tivoli/tsm/client/hsm/bin'
    
    # Configuration Files
    DSM_SYS = 'dsm.sys'
    DSM_OPT = 'dsm.opt'
    
    # GPFS Requirements
    REQUIRED_GPFS_PACKAGES = [
        'gpfs.base',
        'gpfs.gpl',
        'gpfs.gskit',
        'gpfs.msg.en_US'
    ]
    
    # Version Regex
    VERSION_REGEX = r'^\d+\.\d+\.\d+\.\d+$'
    
    # Error Messages
    ERROR_MESSAGES = {
        'invalid_version': 'Invalid version format: {version}',
        'gpfs_not_installed': 'GPFS is not installed (REQUIRED)',
        'insufficient_space': 'Insufficient disk space',
        'unsupported_arch': 'Unsupported architecture: {arch}'
    }
```

---

## 5. Data Flow

### 5.1 Installation Data Flow

```
┌─────────────────┐
│ Control Node    │
│ - Playbook vars │
│ - Package file  │
└────────┬────────┘
         │
         │ 1. Transfer package
         ▼
┌─────────────────┐
│ Target Host     │
│ /tmp/package    │
└────────┬────────┘
         │
         │ 2. Extract
         ▼
┌─────────────────┐
│ Temp Directory  │
│ /opt/hsmClient  │
└────────┬────────┘
         │
         │ 3. Install RPMs
         ▼
┌─────────────────┐
│ Install Path    │
│ /opt/tivoli/... │
└────────┬────────┘
         │
         │ 4. Configure
         ▼
┌─────────────────┐
│ Config Files    │
│ - dsm.sys       │
│ - dsm.opt       │
└─────────────────┘
```

### 5.2 Configuration Data Flow

```
┌─────────────────┐
│ Playbook Vars   │
│ - server_name   │
│ - server_addr   │
│ - node_name     │
└────────┬────────┘
         │
         │ Template rendering
         ▼
┌─────────────────┐
│ dsm.sys         │
│ SErvername      │
│ TCPServeraddr   │
│ NODENAME        │
└────────┬────────┘
         │
         │ Write to target
         ▼
┌─────────────────┐
│ Target Host     │
│ /opt/tivoli/... │
└─────────────────┘
```

---

## 6. Security Design

### 6.1 Authentication & Authorization

| **Aspect** | **Implementation** |
|------------|-------------------|
| Ansible Connection | SSH key-based authentication |
| Privilege Escalation | sudo/become with password or NOPASSWD |
| Target Host Access | Root or equivalent privileges required |
| Package Verification | Checksum validation (optional) |

### 6.2 Sensitive Data Handling

```yaml
# Use Ansible Vault for sensitive data
server_password: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          ...encrypted...

# Use environment variables
node_password: "{{ lookup('env', 'HSM_NODE_PASSWORD') }}"

# Use external secret management
node_password: "{{ lookup('hashivault', 'secret/hsm/node_password') }}"
```

### 6.3 File Permissions

| **File** | **Permissions** | **Owner** | **Purpose** |
|----------|----------------|-----------|-------------|
| dsm.sys | 600 | root | Server configuration |
| dsm.opt | 600 | root | Client options |
| dsmerror.log | 640 | root | Error logs |
| dsmsched.log | 640 | root | Schedule logs |

---

## 7. Error Handling & Rollback

### 7.1 Error Handling Strategy

```
┌─────────────────────────┐
│ Operation Start         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Pre-checks              │
│ - Validate inputs       │
│ - Check prerequisites   │
└───────────┬─────────────┘
            │
            ├─── FAIL ──> Exit with error
            │
            ▼ PASS
┌─────────────────────────┐
│ Backup Current State    │
│ - Config files          │
│ - Package list          │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Execute Operation       │
└───────────┬─────────────┘
            │
            ├─── FAIL ──┐
            │           │
            ▼ PASS      ▼
┌─────────────────────────┐
│ Post-verification       │ Rollback
└───────────┬─────────────┘ - Restore configs
            │               - Reinstall packages
            ▼               - Cleanup
┌─────────────────────────┐
│ Success                 │
└─────────────────────────┘
```

### 7.2 Rollback Scenarios

#### 7.2.1 Installation Rollback
```yaml
- name: Rollback failed installation
  block:
    - name: Remove installed packages
      package:
        name: "{{ item }}"
        state: absent
      loop: "{{ installed_packages }}"
      
    - name: Remove directories
      file:
        path: "{{ item }}"
        state: absent
      loop:
        - "{{ hsm_install_path }}"
        - "{{ hsm_temp_dir }}"
```

#### 7.2.2 Uninstallation Rollback
```yaml
- name: Rollback failed uninstallation
  block:
    - name: Restore configuration files
      copy:
        src: "{{ backup_dir }}/{{ item }}"
        dest: "{{ config_dir }}/{{ item }}"
      loop:
        - dsm.sys
        - dsm.opt
        
    - name: Reinstall packages
      package:
        name: "{{ item }}"
        state: present
      loop: "{{ backed_up_packages }}"
```

### 7.3 Error Categories

| **Category** | **Examples** | **Handling** |
|--------------|--------------|--------------|
| Pre-check Failures | Missing GPFS, insufficient space | Fail fast, no rollback needed |
| Installation Failures | Package conflicts, dependency issues | Rollback: remove installed packages |
| Configuration Failures | Invalid config syntax | Rollback: restore previous config |
| Post-check Failures | Service won't start | Rollback: full uninstall |

---

## 8. Performance Considerations

### 8.1 Optimization Strategies

| **Area** | **Strategy** | **Impact** |
|----------|-------------|------------|
| Package Transfer | Use local repository when possible | Reduces network transfer time |
| Parallel Execution | Use Ansible forks for multiple hosts | Reduces total execution time |
| Idempotency Checks | Check before action | Avoids unnecessary operations |
| Fact Caching | Cache gathered facts | Reduces repeated fact gathering |

### 8.2 Resource Requirements

| **Resource** | **Minimum** | **Recommended** |
|--------------|-------------|-----------------|
| Disk Space | 1500 MB | 3000 MB |
| Memory | 512 MB | 1 GB |
| CPU | 1 core | 2 cores |
| Network | 10 Mbps | 100 Mbps |

### 8.3 Execution Time Estimates

| **Operation** | **Single Host** | **10 Hosts (parallel)** |
|---------------|-----------------|-------------------------|
| Installation | 5-10 minutes | 8-15 minutes |
| Uninstallation | 2-5 minutes | 3-7 minutes |
| Configuration | 1-2 minutes | 1-3 minutes |
| Facts Gathering | 30-60 seconds | 1-2 minutes |

---

## 9. Testing Strategy

### 9.1 Test Levels

```
┌─────────────────────────────────────────┐
│ Unit Tests                              │
│ - Module functions                      │
│ - Utility methods                       │
│ - Input validation                      │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Integration Tests                       │
│ - Role execution                        │
│ - Multi-task workflows                  │
│ - Rollback scenarios                    │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ System Tests                            │
│ - End-to-end playbook execution         │
│ - Multi-host scenarios                  │
│ - Performance testing                   │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Acceptance Tests                        │
│ - Production-like environment           │
│ - User acceptance criteria              │
│ - Documentation validation              │
└─────────────────────────────────────────┘
```

### 9.2 Test Cases

#### 9.2.1 Installation Tests
- Fresh installation on clean system
- Installation with existing GPFS
- Installation with insufficient disk space (should fail)
- Installation without GPFS (should fail)
- Force reinstallation

#### 9.2.2 Uninstallation Tests
- Clean uninstallation
- Uninstallation with active HSM (should deactivate first)
- Uninstallation rollback on failure

#### 9.2.3 Configuration Tests
- Valid configuration
- Invalid server address (should fail gracefully)
- Missing required parameters

---

## 10. Deployment Architecture

### 10.1 Deployment Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Control Node                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ Ansible Collection                                  │     │
│  │ /usr/share/ansible/collections/                     │     │
│  │   ansible_collections/                              │     │
│  │     ibm/                                            │     │
│  │       storage_protect/                              │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ SSH (Port 22)
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Linux Host 1 │    │ Linux Host 2 │    │ AIX Host 1   │
│ - RHEL 8     │    │ - SLES 15    │    │ - AIX 7.2    │
│ - GPFS 5.1   │    │ - GPFS 5.1   │    │ - GPFS 5.1   │
│ - HSM Client │    │ - HSM Client │    │ - HSM Client │
└──────────────┘    └──────────────┘    └──────────────┘
```

### 10.2 Network Requirements

| **Connection** | **Protocol** | **Port** | **Purpose** |
|----------------|--------------|----------|-------------|
| Control → Target | SSH | 22 | Ansible communication |
| Target → SP Server | TCP | 1500 | HSM Client communication |
| Target → GPFS | TCP | 1191 | GPFS cluster communication |

### 10.3 Directory Structure

```
/usr/share/ansible/collections/ansible_collections/ibm/storage_protect/
├── docs/
│   ├── HSM_DESIGN_DOCUMENT.md
│   └── HSM_USER_GUIDE.md
├── playbooks/
│   └── hsm_client_install/
│       ├── playbooks/
│       │   ├── linux/
│       │   │   ├── hsm_client_install_role_playbook.yml
│       │   │   ├── hsm_client_uninstall_playbook.yml
│       │   │   ├── hsm_client_config_playbook.yml
│       │   │   └── hsm_client_facts_playbook.yml
│       │   └── aix/
│       │       ├── hsm_client_install_role_playbook.yml
│       │       └── hsm_client_uninstall_playbook.yml
│       └── vars/
│           └── main.yml
├── plugins/
│   ├── modules/
│   │   └── hsm_client_install.py
│   └── module_utils/
│       ├── hsm_client_utils.py
│       ├── hsm_client_facts_utils.py
│       └── hsm_constants.py
└── roles/
    └── hsm_client_install/
        ├── defaults/
        │   └── main.yml
        ├── meta/
        │   └── main.yml
        ├── tasks/
        │   ├── main.yml
        │   ├── determine_action.yml
        │   ├── local_repo_check.yml
        │   ├── gpfs_prerequisite_check.yml
        │   ├── hsm_client_install_linux.yml
        │   ├── hsm_client_install_aix.yml
        │   ├── hsm_client_uninstall_linux.yml
        │   └── hsm_client_uninstall_aix.yml
        └── README.md
```

---

## 11. Appendices

### 11.1 Package Dependencies

#### Linux Package Order
1. gskcrypt64 (Cryptographic library)
2. gskssl64 (SSL library)
3. TIVsm-API64 (64-bit API)
4. TIVsm-APIcit (API Common Interface)
5. TIVsm-HSM (HSM Client)
6. TIVsm-HSMcit (HSM Common Interface)

#### AIX Package Order
1. gsk8cry64 (Cryptographic library)
2. gsk8ssl64 (SSL library)
3. TIVsm-API64 (64-bit API)
4. TIVsm-APIcit (API Common Interface)
5. TIVsm-HSM (HSM Client)
6. TIVsm-HSMcit (HSM Common Interface)

### 11.2 GPFS Prerequisites

**Required GPFS Packages:**
- gpfs.base (>= 4.2.1-0)
- gpfs.gpl
- gpfs.gskit
- gpfs.msg.en_US
- gpfs.compression (recommended)
- gpfs.license.std

**GPFS Verification Commands:**
```bash
# Check GPFS packages
rpm -qa | grep -i '^gpfs\.'  # Linux
lslpp -l | grep -i '^gpfs\.' # AIX

# Check GPFS status
mmgetstate -a

# Check HSM status
mmhsm state show
```

### 11.3 Configuration File Templates

#### dsm.sys Template
```
SErvername  {{ server_name }}
    TCPServeraddress  {{ server_address }}
    TCPPort           {{ server_port }}
    NODENAME          {{ node_name }}
    PASSWORDACCESS    GENERATE
    MANAGEDSERVICES   WEBCLIENT SCHEDULE HSM
```

#### dsm.opt Template
```
SErvername  {{ server_name }}
NODENAME    {{ node_name }}
ERRORLOGNAME  {{ hsm_install_path }}/dsmerror.log
SCHEDLOGNAME  {{ hsm_install_path }}/dsmsched.log
MANAGEDSERVICES WEBCLIENT SCHEDULE HSM
```

### 11.4 Glossary

| **Term** | **Definition** |
|----------|----------------|
| HSM | Hierarchical Storage Management |
| GPFS | General Parallel File System (IBM Spectrum Scale) |
| BA Client | Backup-Archive Client |
| SP Server | Storage Protect Server |
| Stub File | Placeholder file for migrated data |
| Policy | Rules for file migration and retention |

### 11.5 References

- IBM Storage Protect Documentation: https://www.ibm.com/docs/en/storage-protect
- IBM Spectrum Scale Documentation: https://www.ibm.com/docs/en/spectrum-scale
- Ansible Documentation: https://docs.ansible.com/
- Python Documentation: https://docs.python.org/3/

---

## Document Control

| **Version** | **Date** | **Author** | **Changes** |
|-------------|----------|------------|-------------|
| 1.0.0 | 2024 | IBM Storage Protect Team | Initial release |

---

**End of Design Document**