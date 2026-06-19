#!/usr/bin/python3
# -*- coding: utf-8 -*-
# IBM Storage Protect HSM Client Installation Module

import sys
import json
import platform
import os
import re
from typing import Any, Dict, Optional, List

# Try to import the real Ansible module
HAS_ANSIBLE = False
try:
    from ansible.module_utils.basic import AnsibleModule  # type: ignore
    HAS_ANSIBLE = True
except Exception:
    AnsibleModule = None  # type: ignore

try:
    # When running as real Ansible module
    from ..module_utils.hsm_client_utils import HSMClientHelper  # type: ignore
    from ..module_utils.hsm_constants import HSMConstants  # type: ignore
except ImportError:
    # When running as standalone script
    import sys
    import os
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    UTILS_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "module_utils"))
    sys.path.insert(0, UTILS_PATH)
    from hsm_client_utils import HSMClientHelper  # type: ignore
    from hsm_constants import HSMConstants  # type: ignore


DOCUMENTATION = '''
---
module: hsm_client_install
short_description: Install or remove IBM Storage Protect HSM Client on Linux and AIX hosts
version_added: "1.0.0"
author: IBM Storage Protect Team

description:
  - This module provides idempotent management of the HSM Client software on target hosts.
  - Supports Linux and AIX platforms with platform-specific installation methods.
  - It supports installation and uninstallation operations only (no in-place upgrades).
  - For upgrades, uninstall the current version first, then install the new version.
  - The module handles package dependencies, configuration, and rollback on failures.
  - Uses RPM packages for Linux and installp for AIX.

options:
  state:
    description:
      - Desired state of the HSM Client
    type: str
    choices: ['present', 'absent']
    default: 'present'
    
  hsm_client_version:
    description:
      - Version of the HSM Client to install or upgrade to
    type: str
    required: true
    
  package_source:
    description:
      - Path to the HSM Client installation package (tar file)
    type: str
    required: true
    
  install_path:
    description:
      - Target installation directory of HSM Client binaries
    type: str
    default: '/opt/tivoli/tsm/client/hsm/bin'
    
  force:
    description:
      - If true, forces reinstallation even if the desired version is already present
    type: bool
    default: false
    
  temp_dir:
    description:
      - Temporary directory for package extraction
    type: str
    default: '/opt/hsmClient'
    
  start_daemon:
    description:
      - Whether to start the HSM Client daemon after installation
    type: bool
    default: true

requirements:
  - Root privileges on Linux
  - Minimum 1500 MB free disk space
  - Compatible architecture (x86_64, s390x, ppc64le)

notes:
  - The module performs comprehensive pre-checks before installation
  - Automatic rollback is performed if installation fails
  - Configuration files are backed up during upgrades
'''

EXAMPLES = '''
- name: Install HSM Client on Linux
  hsm_client_install:
    hsm_client_version: "8.1.25.0"
    state: present
    package_source: "/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar"
    install_path: "/opt/tivoli/tsm/client/hsm/bin"

- name: Install HSM Client on AIX
  hsm_client_install:
    hsm_client_version: "8.1.25.0"
    state: present
    package_source: "/tmp/8.1.25.0-TIV-TSMHSM-AIX.tar.Z"

- name: Uninstall HSM Client
  hsm_client_install:
    hsm_client_version: "8.1.25.0"
    state: absent
    package_source: "/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar"

- name: Upgrade HSM Client (two-step process)
  # Step 1: Uninstall old version
  hsm_client_install:
    hsm_client_version: "8.1.25.0"
    state: absent
    package_source: "/tmp/8.1.25.0-TIV-TSMHSM-LinuxX86.tar"
  
  # Step 2: Install new version
  hsm_client_install:
    hsm_client_version: "8.1.26.0"
    state: present
    package_source: "/tmp/8.1.26.0-TIV-TSMHSM-LinuxX86.tar"
'''

RETURN = '''
changed:
  description: Whether any change was made
  type: bool
  returned: always
  
msg:
  description: Human-readable message summarizing the operation
  type: str
  returned: always
  
version:
  description: The installed HSM Client version
  type: str
  returned: when applicable
  
is_installation_successful:
  description: Whether the installation was successful
  type: bool
  returned: when state is present
'''


def normalize_version(ver):
    """Normalize version string to list of integers for comparison"""
    try:
        return [int(x) for x in ver.split('.')]
    except Exception:
        return []


def validate_parameters(params: Dict[str, Any]) -> List[str]:
    """
    Validate all input parameters before processing.
    
    Args:
        params: Dictionary of module parameters
        
    Returns:
        List of error messages (empty if validation passes)
    """
    errors = []
    
    # Validate version format
    version = params.get('hsm_client_version', '')
    if not re.match(HSMConstants.VERSION_REGEX, version):
        errors.append(
            HSMConstants.ERROR_MESSAGES['invalid_version'].format(version=version)
        )
    
    # Validate install_path is absolute
    install_path = params.get('install_path', '')
    if install_path and not os.path.isabs(install_path):
        errors.append(f"install_path must be an absolute path: {install_path}")
    
    # Validate temp_dir is absolute
    temp_dir = params.get('temp_dir', '')
    if temp_dir and not os.path.isabs(temp_dir):
        errors.append(f"temp_dir must be an absolute path: {temp_dir}")
    
    # Validate package source format
    package_source = params.get('package_source', '')
    if package_source:
        system_platform = platform.system().lower()
        platform_key = 'windows' if system_platform.startswith('win') else system_platform
        
        valid_extensions = HSMConstants.PACKAGE_EXTENSIONS.get(platform_key, [])
        if not any(package_source.endswith(ext) for ext in valid_extensions):
            errors.append(
                f"Invalid package format for {platform_key}: {package_source}. "
                f"Expected one of: {', '.join(valid_extensions)}"
            )
    
    # Validate state
    state = params.get('state', '')
    if state not in ['present', 'absent']:
        errors.append(f"Invalid state: {state}. Must be 'present' or 'absent'")
    
    return errors


def main():
    """Main module execution"""
    
    # Define module arguments
    argument_spec = dict(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        hsm_client_version=dict(type='str', required=True),
        package_source=dict(type='str', required=True),
        install_path=dict(type='str', default='/opt/tivoli/tsm/client/hsm/bin'),
        force=dict(type='bool', default=False),
        temp_dir=dict(type='str', default='/opt/hsmClient'),
        start_daemon=dict(type='bool', default=True),
    )
    
    # Create module instance
    module = AnsibleModule(  # type: ignore
        argument_spec=argument_spec,
        supports_check_mode=True
    )
    
    # Get parameters - Cast params to Dict to satisfy type checker
    params: Dict[str, Any] = module.params  # type: ignore
    
    # Validate parameters
    validation_errors = validate_parameters(params)
    if validation_errors:
        module.fail_json(
            msg="Parameter validation failed",
            errors=validation_errors
        )
    
    # Initialize helper
    utils = HSMClientHelper(module)  # type: ignore
    state = params['state']
    hsm_client_version = params['hsm_client_version']
    package_source = params['package_source']
    install_path = params['install_path']
    force = params['force']
    temp_dir = params['temp_dir']
    hsm_client_start_daemon = params['start_daemon']
    
    # Check what is installed
    installed, installed_version = utils.check_installed()
    
    utils.log(f"Installed: {installed}")
    utils.log(f"Installed version: {installed_version}")
    
    # Handle uninstall first (doesn't need package source)
    if state == 'absent':
        if not installed:
            module.exit_json(
                changed=False,
                msg="HSM Client not installed, nothing to remove"
            )
        
        # Version mismatch check - fail if trying to uninstall a different version
        if hsm_client_version and installed_version and hsm_client_version != installed_version and not force:
            module.fail_json(
                changed=False,
                msg=f"Version mismatch: Installed version is {installed_version}, but requested uninstall version is {hsm_client_version}. "
                    f"To uninstall the currently installed version, use -e 'hsm_client_version={installed_version}'. "
                    f"To force uninstall regardless of version, add -e 'force=true'."
            )
        
        try:
            uninstalled = utils.uninstall_hsm_client()
            if uninstalled:
                module.exit_json(
                    changed=True,
                    msg="HSM Client successfully uninstalled"
                )
            else:
                module.exit_json(
                    changed=False,
                    msg="HSM Client was not installed, nothing to uninstall"
                )
        except Exception as e:
            module.fail_json(
                changed=False,
                msg=f"Uninstallation failed: {str(e)}"
            )
    
    # For install/upgrade, check package availability
    version_available = utils.file_exists(package_source)
    installed_version_list = normalize_version(installed_version) if installed_version else []
    user_version_list = normalize_version(hsm_client_version) if hsm_client_version else []
    
    utils.log(f"Version available (file_exists): {version_available}")
    utils.log(f"Package source: {package_source}")
    
    # Determine action - Simplified: only install or none (no upgrade support)
    if not installed and version_available:
        action = "install"
    elif installed:
        # If already installed, fail with message to uninstall first
        module.fail_json(
            msg=f"HSM Client version {installed_version} is already installed. "
                f"This module does not support in-place upgrades. "
                f"To install version {hsm_client_version}, please: "
                f"1. Run uninstall playbook first (state=absent) "
                f"2. Then run install playbook with new version (state=present)"
        )
    else:
        action = "none"
    
    utils.log(f"Determined HSM Client action: {action}")
    
    # Execute based on action
    if action == 'install':
        # Idempotency recheck
        installed, _ = utils.check_installed()
        if installed and not force:
            module.exit_json(
                changed=False,
                msg="HSM Client already installed after extraction check"
            )
        
        # Pre-checks
        precheck = utils.verify_system_prereqs()
        module.warn(f"Precheck completed: {precheck}")
        
        # Check package
        if not utils.file_exists(package_source):
            module.fail_json(msg=f"Package source not found on host: {package_source}")
        
        try:
            # Perform install
            utils.install_hsm_client(package_source, install_path, temp_dir)
            utils.configure_hsm_client()
            
            # Verify
            verify_result = utils.post_installation_verification(hsm_client_version, action)
            
            # Start daemon
            daemon_result = utils.start_hsm_daemon(hsm_client_start_daemon)
            
            module.exit_json(
                changed=True,
                msg=f"HSM Client {verify_result.get('hsm_client_version', hsm_client_version)} verification completed",
                **verify_result,
                **daemon_result
            )
            
        except Exception as install_error:
            module.warn(f"Installation failed: {install_error}")
            rollback_info = utils.rollback(action="install", previous_version=installed_version)
            rollback_status = rollback_info.get('status', 'unknown') if rollback_info else 'rollback failed'
            module.exit_json(
                changed=False,
                msg=f"Installation failed and rollback executed: {install_error}. {rollback_status}"
            )
    
    elif state == 'absent':
        if not installed:
            module.exit_json(
                changed=False,
                msg="HSM Client not installed, nothing to remove"
            )
        
        try:
            uninstalled = utils.uninstall_hsm_client()
            if uninstalled:
                module.exit_json(
                    changed=True,
                    msg="HSM Client successfully uninstalled"
                )
            else:
                module.exit_json(
                    changed=False,
                    msg="HSM Client was not installed, nothing to uninstall"
                )
        except Exception as uninstall_error:
            module.warn(f"Uninstallation failed: {uninstall_error}")
            utils.rollback(action="uninstall", previous_version=installed_version)
            module.exit_json(
                changed=False,
                msg=f"Uninstallation failed and rollback executed: {uninstall_error}"
            )
    
    # Fallback
    module.exit_json(
        changed=False,
        msg="No action taken: HSM Client is already at the desired state or no package available"
    )


if __name__ == '__main__':
    main()

