# -*- coding: utf-8 -*-
# IBM Storage Protect HSM Client Facts Utility Module

import subprocess
import platform
import re

# Try to import Ansible (for Linux/normal use)
HAS_ANSIBLE = False
try:
    from ansible.module_utils.basic import AnsibleModule, env_fallback
    HAS_ANSIBLE = True
except ImportError:
    # On Windows or standalone execution, Ansible not available
    AnsibleModule = None
    env_fallback = None

# Try relative import first (Ansible module structure)
try:
    from ..module_utils.dsmc_adapter import DsmcAdapter  # type: ignore[assignment]
except ImportError:
    # Fallback to direct import (Windows standalone)
    try:
        from dsmc_adapter import DsmcAdapter  # type: ignore[assignment]
    except ImportError:
        # Create a minimal DsmcAdapter if not available
        class DsmcAdapter:  # type: ignore[no-redef]
            def __init__(self, server_name=None, node_name=None, password=None, **kwargs):
                self.server_name = server_name
                self.node_name = node_name
                self.password = password
                self.json_output = {}  # type: dict
                self.json_output['changed'] = False
                self.params = kwargs.get('direct_params', {})
            
            def exit_json(self, **kwargs):
                """Stub method for standalone execution."""
                import json
                print(json.dumps(kwargs))
                
            def fail_json(self, msg='', **kwargs):
                """Stub method for standalone execution."""
                import json
                import sys
                error_output = {'failed': True, 'msg': msg}
                error_output.update(kwargs)
                print(json.dumps(error_output))
                sys.exit(1)


class DsmcAdapterExtendedHSM(DsmcAdapter):  # type: ignore[misc]
    """
    Extended DsmcAdapter for HSM Client to add support for HSM-specific query commands.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize the extended adapter and ensure json_output exists."""
        super().__init__(*args, **kwargs)
        # Ensure json_output exists even in fallback scenarios
        if not hasattr(self, 'json_output'):
            self.json_output = {'changed': False}

    def run_command(self, command, auto_exit=True, dataonly=True, exit_on_fail=True, timeout=30):
        """
        Run a DSMC command with appropriate parameters for HSM.
        
        Args:
            command: The DSMC command to execute
            auto_exit: Whether to automatically exit after command execution
            dataonly: Whether to use -dataonly=yes parameter
            exit_on_fail: Whether to fail on command error
            timeout: Command timeout in seconds (default: 30)
            
        Returns:
            tuple: (return_code, stdout, stderr)
        """
        # Build the command based on platform
        system_platform = platform.system().lower()
        is_windows = system_platform.startswith("win")
        is_aix = system_platform == "aix"
        
        if is_windows:
            dsmc_cmd = 'dsmc.exe'
        elif is_aix:
            # AIX: Try to find DSMC in common locations
            dsmc_cmd = self._find_dsmc_aix()
            if not dsmc_cmd:
                if exit_on_fail:
                    self.fail_json(msg="DSMC not found on AIX system. Checked: /usr/bin/dsmc, /opt/tivoli/tsm/client/ba/bin/dsmc, /usr/tivoli/tsm/client/ba/bin/dsmc")
                return 1, "", "DSMC not found"
        else:
            dsmc_cmd = 'dsmc'
        
        # Get user credentials
        user_id = getattr(self, 'user_id', self.node_name)
        password = self.password
        
        # Build full command
        full_command = f'{dsmc_cmd} {command}'
        
        self.json_output['command'] = full_command
        
        # Prepare input for interactive prompts (user ID and password)
        input_data = f"{user_id}\n{password}\n" if password else None
        
        # AIX-specific environment setup
        env = None
        if is_aix:
            import os
            env = os.environ.copy()
            env['LANG'] = 'C'  # Ensure English output for consistent parsing
            env['LC_ALL'] = 'C'
        
        try:
            result = subprocess.run(
                full_command,
                shell=True,
                input=input_data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                env=env
            )
            raw_output = result.stdout
            self.json_output['output'] = raw_output
            self.json_output['stderr'] = result.stderr

            if auto_exit:
                self.json_output['changed'] = result.returncode == 0
                self.exit_json(**self.json_output)
            
            return result.returncode, raw_output, result.stderr
            
        except FileNotFoundError:
            error_msg = f"DSMC command not found: {dsmc_cmd}"
            if exit_on_fail:
                self.fail_json(msg=error_msg, **self.json_output)
            return 1, "", error_msg
        except PermissionError:
            error_msg = f"Permission denied executing: {dsmc_cmd}"
            if exit_on_fail:
                self.fail_json(msg=error_msg, **self.json_output)
            return 1, "", error_msg
        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after {timeout} seconds"
            if exit_on_fail:
                self.fail_json(msg=error_msg, **self.json_output)
            return 1, "", "Timeout"
        except subprocess.CalledProcessError as e:
            if exit_on_fail:
                self.fail_json(
                    msg=e.stderr if e.stderr else str(e),
                    rc=e.returncode,
                    **self.json_output
                )
            return e.returncode, e.stdout if hasattr(e, 'stdout') else "", e.stderr if e.stderr else str(e)
        except Exception as e:
            error_msg = f"Unexpected error executing command: {str(e)}"
            if exit_on_fail:
                self.fail_json(msg=error_msg, **self.json_output)
            return 1, "", error_msg
    
    def _find_dsmc_aix(self):
        """
        Find DSMC binary on AIX system.
        
        Returns:
            str: Path to DSMC binary or None if not found
        """
        import os
        possible_paths = [
            '/usr/bin/dsmc',
            '/opt/tivoli/tsm/client/ba/bin/dsmc',
            '/usr/tivoli/tsm/client/ba/bin/dsmc'
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        
        return None

class HSMParser:
    """
    A class to parse various output data from the HSM Client system into structured formats.
    """

    @staticmethod
    def parse_hsm_version(output):
        """
        Parses HSM version information from package query or dsmc output.
        
        Args:
            output (str): The raw output string from rpm query or dsmc command.
            
        Returns:
            dict: A dictionary with parsed HSM version information.
        """
        version_info = {}
        
        # Extract HSM version from rpm output
        hsm_match = re.search(r'TIVsm-HSM[^\s]*\s+(\d+\.\d+\.\d+\.\d+)', output)
        if hsm_match:
            version_info['hsm_version'] = hsm_match.group(1)
        
        # Extract BA version (HSM depends on BA)
        ba_match = re.search(r'TIVsm-BA[^\s]*\s+(\d+\.\d+\.\d+\.\d+)', output)
        if ba_match:
            version_info['ba_version'] = ba_match.group(1)
        
        # Extract API version
        api_match = re.search(r'TIVsm-API64[^\s]*\s+(\d+\.\d+\.\d+\.\d+)', output)
        if api_match:
            version_info['api_version'] = api_match.group(1)
        
        return version_info

    @staticmethod
    def parse_gpfs_status(output):
        """
        Parses GPFS status information with comprehensive error handling.
        
        Args:
            output (str): The raw output string from mmlsfs or mmgetstate command.
            
        Returns:
            dict: A dictionary with parsed GPFS status and any errors encountered.
        """
        gpfs_info = {
            'gpfs_installed': False,
            'gpfs_active': False,
            'gpfs_version': None,
            'filesystems': [],
            'errors': []
        }
        
        # Validate input
        if not output or not output.strip():
            gpfs_info['errors'].append("Empty GPFS output")
            return gpfs_info
        
        # Check for error messages
        error_indicators = ['command not found', 'not installed', 'permission denied', 'error']
        for indicator in error_indicators:
            if indicator in output.lower():
                gpfs_info['errors'].append(f"GPFS error detected: {indicator}")
                if 'command not found' in output.lower() or 'not installed' in output.lower():
                    return gpfs_info
        
        try:
            # Check if GPFS is active
            if 'active' in output.lower():
                gpfs_info['gpfs_active'] = True
                gpfs_info['gpfs_installed'] = True
            
            # Extract GPFS version
            version_match = re.search(r'GPFS\s+version\s+(\d+\.\d+\.\d+\.\d+)', output, re.IGNORECASE)
            if version_match:
                gpfs_info['gpfs_version'] = version_match.group(1)
                gpfs_info['gpfs_installed'] = True
            
            # Extract filesystem information
            fs_lines = output.strip().split('\n')
            for line in fs_lines:
                line = line.strip()
                if not line or line.startswith('File') or line.startswith('---') or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        gpfs_info['filesystems'].append({
                            'name': parts[0],
                            'mount_point': parts[1] if len(parts) > 1 else '',
                            'status': parts[2] if len(parts) > 2 else 'unknown'
                        })
                    except (IndexError, ValueError) as e:
                        gpfs_info['errors'].append(f"Error parsing filesystem line: {line[:50]}")
        
        except Exception as e:
            gpfs_info['errors'].append(f"Parsing error: {str(e)}")
        
        return gpfs_info

    @staticmethod
    def parse_hsm_status(output):
        """
        Parses HSM status information from dsmhsm command.
        
        Args:
            output (str): The raw output string from dsmhsm status command.
            
        Returns:
            dict: A dictionary with parsed HSM status.
        """
        hsm_status = {
            'hsm_active': False,
            'hsm_enabled': False,
            'managed_filesystems': [],
            'migration_status': None,
            'recall_status': None
        }
        
        # Check if HSM is active
        if 'active' in output.lower() or 'running' in output.lower():
            hsm_status['hsm_active'] = True
        
        # Check if HSM is enabled
        if 'enabled' in output.lower():
            hsm_status['hsm_enabled'] = True
        
        # Extract managed filesystems
        fs_match = re.findall(r'Filesystem:\s+(\S+)', output)
        if fs_match:
            hsm_status['managed_filesystems'] = fs_match
        
        # Extract migration status
        migration_match = re.search(r'Migration:\s+(\w+)', output)
        if migration_match:
            hsm_status['migration_status'] = migration_match.group(1)
        
        # Extract recall status
        recall_match = re.search(r'Recall:\s+(\w+)', output)
        if recall_match:
            hsm_status['recall_status'] = recall_match.group(1)
        
        return hsm_status

    @staticmethod
    def parse_hsm_filespace(output):
        """
        Parses HSM filespace information.
        
        Args:
            output (str): The raw output string from query filespace command.
            
        Returns:
            list: A list of dictionaries with parsed filespace information.
        """
        filespaces = []
        lines = output.strip().split('\n')
        
        keys = [
            "Filespace Name", "FSID", "Platform", "Filespace Type", "Capacity (MB)",
            "Pct Util", "HSM State", "Last Migration", "Last Recall"
        ]
        
        for line in lines:
            if line.strip() and not line.startswith('ANR') and not line.startswith('File'):
                values = [v.strip().replace('"', '') for v in line.split(',')]
                if len(values) >= 3:  # At least filespace name, FSID, and platform
                    # Pad values if needed
                    while len(values) < len(keys):
                        values.append('')
                    filespaces.append(dict(zip(keys, values[:len(keys)])))
        
        return filespaces

    @staticmethod
    def parse_hsm_migration_stats(output):
        """
        Parses HSM migration statistics.
        
        Args:
            output (str): The raw output string from HSM migration query.
            
        Returns:
            dict: A dictionary with parsed migration statistics.
        """
        migration_stats = {
            'total_files_migrated': 0,
            'total_bytes_migrated': 0,
            'files_pending_migration': 0,
            'migration_rate': None,
            'last_migration_time': None
        }
        
        # Extract total files migrated
        files_match = re.search(r'Total files migrated:\s+(\d+)', output)
        if files_match:
            migration_stats['total_files_migrated'] = int(files_match.group(1))
        
        # Extract total bytes migrated
        bytes_match = re.search(r'Total bytes migrated:\s+(\d+)', output)
        if bytes_match:
            migration_stats['total_bytes_migrated'] = int(bytes_match.group(1))
        
        # Extract pending files
        pending_match = re.search(r'Files pending migration:\s+(\d+)', output)
        if pending_match:
            migration_stats['files_pending_migration'] = int(pending_match.group(1))
        
        # Extract migration rate
        rate_match = re.search(r'Migration rate:\s+([\d.]+)\s+(\w+)', output)
        if rate_match:
            migration_stats['migration_rate'] = f"{rate_match.group(1)} {rate_match.group(2)}"
        
        # Extract last migration time
        time_match = re.search(r'Last migration:\s+(.+)', output)
        if time_match:
            migration_stats['last_migration_time'] = time_match.group(1).strip()
        
        return migration_stats

    @staticmethod
    def parse_hsm_recall_stats(output):
        """
        Parses HSM recall statistics.
        
        Args:
            output (str): The raw output string from HSM recall query.
            
        Returns:
            dict: A dictionary with parsed recall statistics.
        """
        recall_stats = {
            'total_files_recalled': 0,
            'total_bytes_recalled': 0,
            'files_pending_recall': 0,
            'recall_rate': None,
            'last_recall_time': None
        }
        
        # Extract total files recalled
        files_match = re.search(r'Total files recalled:\s+(\d+)', output)
        if files_match:
            recall_stats['total_files_recalled'] = int(files_match.group(1))
        
        # Extract total bytes recalled
        bytes_match = re.search(r'Total bytes recalled:\s+(\d+)', output)
        if bytes_match:
            recall_stats['total_bytes_recalled'] = int(bytes_match.group(1))
        
        # Extract pending files
        pending_match = re.search(r'Files pending recall:\s+(\d+)', output)
        if pending_match:
            recall_stats['files_pending_recall'] = int(pending_match.group(1))
        
        # Extract recall rate
        rate_match = re.search(r'Recall rate:\s+([\d.]+)\s+(\w+)', output)
        if rate_match:
            recall_stats['recall_rate'] = f"{rate_match.group(1)} {rate_match.group(2)}"
        
        # Extract last recall time
        time_match = re.search(r'Last recall:\s+(.+)', output)
        if time_match:
            recall_stats['last_recall_time'] = time_match.group(1).strip()
        
        return recall_stats

    @staticmethod
    def parse_hsm_policy(output):
        """
        Parses HSM policy information.
        
        Args:
            output (str): The raw output string from HSM policy query.
            
        Returns:
            dict: A dictionary with parsed HSM policy information.
        """
        policy_info = {
            'migration_threshold': None,
            'migration_age': None,
            'recall_priority': None,
            'stub_size': None,
            'policies': []
        }
        
        # Extract migration threshold
        threshold_match = re.search(r'Migration threshold:\s+(\d+)%', output)
        if threshold_match:
            policy_info['migration_threshold'] = f"{threshold_match.group(1)}%"
        
        # Extract migration age
        age_match = re.search(r'Migration age:\s+(\d+)\s+days', output)
        if age_match:
            policy_info['migration_age'] = f"{age_match.group(1)} days"
        
        # Extract recall priority
        priority_match = re.search(r'Recall priority:\s+(\w+)', output)
        if priority_match:
            policy_info['recall_priority'] = priority_match.group(1)
        
        # Extract stub size
        stub_match = re.search(r'Stub size:\s+(\d+)\s+(\w+)', output)
        if stub_match:
            policy_info['stub_size'] = f"{stub_match.group(1)} {stub_match.group(2)}"
        
        # Parse policy lines
        lines = output.strip().split('\n')
        for line in lines:
            if 'Policy:' in line:
                policy_info['policies'].append(line.strip())
        
        return policy_info

    @staticmethod
    def parse_systeminfo(output):
        """
        Parses system information for HSM Client.
        
        Args:
            output (str): The raw output string.
            
        Returns:
            dict: A dictionary with parsed system information.
        """
        system_info = {
            'hostname': platform.node(),
            'os_type': platform.system(),
            'os_version': platform.version(),
            'architecture': platform.machine(),
            'python_version': platform.python_version(),
            'gpfs_required': True,
            'ba_client_required': True
        }
        
        # Extract additional info from output if available
        if 'Operating system' in output:
            os_match = re.search(r'Operating system\s*:\s*(.+)', output)
            if os_match:
                system_info['client_os'] = os_match.group(1).strip()
        
        return system_info


class HSMClientResponseMapper:
    """
    Maps HSM Client response keys to developer-friendly snake_case format.
    """
    
    mapping = {
        "Filespace Name": "filespace_name",
        "FSID": "fsid",
        "Platform": "platform",
        "Filespace Type": "filespace_type",
        "Capacity (MB)": "capacity_mb",
        "Pct Util": "pct_util",
        "HSM State": "hsm_state",
        "Last Migration": "last_migration",
        "Last Recall": "last_recall",
        "HSM Version": "hsm_version",
        "BA Version": "ba_version",
        "API Version": "api_version",
        "GPFS Installed": "gpfs_installed",
        "GPFS Active": "gpfs_active",
        "GPFS Version": "gpfs_version",
        "Filesystems": "filesystems",
        "HSM Active": "hsm_active",
        "HSM Enabled": "hsm_enabled",
        "Managed Filesystems": "managed_filesystems",
        "Migration Status": "migration_status",
        "Recall Status": "recall_status",
        "Total Files Migrated": "total_files_migrated",
        "Total Bytes Migrated": "total_bytes_migrated",
        "Files Pending Migration": "files_pending_migration",
        "Migration Rate": "migration_rate",
        "Last Migration Time": "last_migration_time",
        "Total Files Recalled": "total_files_recalled",
        "Total Bytes Recalled": "total_bytes_recalled",
        "Files Pending Recall": "files_pending_recall",
        "Recall Rate": "recall_rate",
        "Last Recall Time": "last_recall_time",
        "Migration Threshold": "migration_threshold",
        "Migration Age": "migration_age",
        "Recall Priority": "recall_priority",
        "Stub Size": "stub_size",
        "Policies": "policies",
        "Hostname": "hostname",
        "OS Type": "os_type",
        "OS Version": "os_version",
        "Architecture": "architecture",
        "Python Version": "python_version",
        "Client OS": "client_os",
        "GPFS Required": "gpfs_required",
        "BA Client Required": "ba_client_required"
    }

    @staticmethod
    def map_to_developer_friendly(json_data):
        """
        Recursively maps response keys to snake_case format.
        
        Args:
            json_data: Dictionary, list, or primitive value to map
            
        Returns:
            Mapped data structure with developer-friendly keys
        """
        if isinstance(json_data, dict):
            # Recursively map each key-value pair in the dictionary
            return {
                HSMClientResponseMapper.mapping.get(key, key.lower().replace(' ', '_').replace('(', '').replace(')', '')): 
                HSMClientResponseMapper.map_to_developer_friendly(value)
                for key, value in json_data.items()
            }
        elif isinstance(json_data, list):
            # Recursively map each item in the list
            return [HSMClientResponseMapper.map_to_developer_friendly(item) for item in json_data]
        else:
            return json_data
