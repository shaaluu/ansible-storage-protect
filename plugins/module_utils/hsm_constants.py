# -*- coding: utf-8 -*-
# IBM Storage Protect HSM Client Constants

"""
Configuration constants for HSM Client operations.
Centralizes all magic numbers, strings, and configuration values.
"""

class HSMConstants:
    """Constants for HSM Client operations"""
    
    # Timeouts (in seconds)
    DEFAULT_COMMAND_TIMEOUT = 30
    LONG_COMMAND_TIMEOUT = 300  # For operations like migration
    SHORT_COMMAND_TIMEOUT = 10  # For quick queries
    
    # Disk space requirements (in MB)
    MIN_DISK_SPACE_MB = 1500
    RECOMMENDED_DISK_SPACE_MB = 3000
    
    # Supported architectures
    SUPPORTED_ARCHITECTURES = ["x86_64", "s390x", "ppc64le", "ppc64", "powerpc", "AMD64"]
    
    # Package names
    HSM_PACKAGES = [
        "gskcrypt64",
        "gskssl64",
        "TIVsm-API64",
        "TIVsm-APIcit",
        "TIVsm-BA",        # Base Backup-Archive client
        "TIVsm-BAcit",     # BA Common Interface
        "TIVsm-HSM",       # HSM client
        "TIVsm-WEBGUI"     # Web GUI component
    ]
    
    # Installation order (dependencies first)
    INSTALL_ORDER = [
        "gskcrypt64",
        "gskssl64",
        "TIVsm-API64",
        "TIVsm-BA",
        "TIVsm-HSM"
    ]
    
    # Uninstall order (reverse of install)
    UNINSTALL_ORDER = [
        "TIVsm-WEBGUI",
        "TIVsm-HSM",
        "TIVsm-BAcit",
        "TIVsm-BA",
        "TIVsm-APIcit",
        "TIVsm-API64",
        "gskssl64",
        "gskcrypt64"
    ]
    
    # HSM-specific commands
    HSM_COMMANDS = {
        'global_deactivate': 'dsmmigfs globaldeactivate',
        'disable_failover': 'dsmmigfs disablefailover',
        'query': 'dsmmigfs q -d',
        'global_reactivate': 'dsmmigfs globalreactivate',
        'enable_failover': 'dsmmigfs enablefailover',
        'wait': 'dsmmigfs wait'
    }
    
    # DSMC binary locations by platform (Linux and AIX only)
    DSMC_PATHS = {
        'linux': [
            '/opt/tivoli/tsm/client/ba/bin/dsmc',
            '/usr/bin/dsmc',
            '/usr/local/bin/dsmc'
        ],
        'aix': [
            '/usr/bin/dsmc',
            '/opt/tivoli/tsm/client/ba/bin/dsmc',
            '/usr/tivoli/tsm/client/ba/bin/dsmc'
        ]
    }
    
    # Configuration file paths (Linux and AIX only)
    CONFIG_PATHS = {
        'linux': {
            'dsm_sys': '/opt/tivoli/tsm/client/ba/bin/dsm.sys',
            'dsm_opt': '/opt/tivoli/tsm/client/ba/bin/dsm.opt',
            'config_dir': '/opt/tivoli/tsm/client/ba/bin'
        },
        'aix': {
            'dsm_sys': '/usr/tivoli/tsm/client/ba/bin/dsm.sys',
            'dsm_opt': '/usr/tivoli/tsm/client/ba/bin/dsm.opt',
            'config_dir': '/usr/tivoli/tsm/client/ba/bin'
        }
    }
    
    # GPG key file
    GPG_KEY_FILE = "GSKit.pub4.pgp"
    
    # Version format regex
    VERSION_REGEX = r'^\d+\.\d+\.\d+\.\d+$'
    
    # Retry configuration
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2  # seconds
    RETRY_BACKOFF = 2  # multiplier
    
    # Logging levels
    LOG_LEVELS = {
        'DEBUG': 0,
        'INFO': 1,
        'WARNING': 2,
        'ERROR': 3,
        'CRITICAL': 4
    }
    
    # Error messages
    ERROR_MESSAGES = {
        'dsmc_not_found': "DSMC command not found. Please ensure IBM Storage Protect Client is installed.",
        'gpfs_not_found': "GPFS not found. HSM Client requires GPFS to be installed and active.",
        'insufficient_disk': "Insufficient disk space. Required: {required}MB, Available: {available}MB",
        'unsupported_arch': "Unsupported architecture: {arch}. Supported: {supported}",
        'invalid_version': "Invalid version format: {version}. Expected format: X.Y.Z.W",
        'permission_denied': "Permission denied. Root/Administrator privileges required.",
        'package_not_found': "Package not found: {package}",
        'installation_failed': "Installation failed: {reason}",
        'upgrade_failed': "Upgrade failed: {reason}",
        'uninstall_failed': "Uninstallation failed: {reason}"
    }
    
    # Success messages
    SUCCESS_MESSAGES = {
        'installation_complete': "HSM Client {version} installed successfully",
        'upgrade_complete': "HSM Client upgraded from {old_version} to {new_version}",
        'uninstall_complete': "HSM Client {version} uninstalled successfully",
        'verification_passed': "Post-installation verification passed",
        'hsm_activated': "HSM successfully activated",
        'hsm_deactivated': "HSM successfully deactivated"
    }
    
    # Platform identifiers (Linux and AIX only)
    PLATFORMS = {
        'LINUX': 'linux',
        'AIX': 'aix'
    }
    
    # File extensions (Linux and AIX only)
    PACKAGE_EXTENSIONS = {
        'linux': ['.tar', '.tar.gz', '.tgz', '.tar.Z'],
        'aix': ['.tar', '.tar.gz', '.tgz', '.tar.Z']
    }

