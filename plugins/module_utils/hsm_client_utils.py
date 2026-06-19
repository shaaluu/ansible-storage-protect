# -*- coding: utf-8 -*-
# IBM Storage Protect HSM Client Utility Module

import os
import platform
import re
import shutil
import subprocess

IS_WINDOWS = platform.system().lower().startswith("win")

if not IS_WINDOWS:
    # Linux / normal Ansible environment
    from ansible.module_utils.basic import AnsibleModule  # type: ignore
else:
    # Windows-safe fallback for when Ansible isn't available
    class AnsibleModule:
        def __init__(self, *args, **kwargs):
            # mimic AnsibleModule interface just enough for this helper
            self.params = {}
        def run_command(self, cmd, use_unsafe_shell=False):
            # simple subprocess wrapper
            if use_unsafe_shell:
                completed = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            else:
                completed = subprocess.run(cmd.split(), shell=False, capture_output=True, text=True)
            return completed.returncode, completed.stdout, completed.stderr
        def fail_json(self, **kwargs):
            print(f"[Windows fail_json] {kwargs.get('msg', '')}")
            raise SystemExit(1)
        def exit_json(self, **kwargs):
            print(f"[Windows exit_json] {kwargs}")
            raise SystemExit(0)
        def warn(self, msg):
            print(f"[Windows WARN] {msg}")
        def log(self, msg):
            print(f"[Windows LOG] {msg}")

# Import constants
try:
    from .hsm_constants import HSMConstants  # type: ignore[assignment]
except ImportError:
    # Fallback for standalone execution
    try:
        from hsm_constants import HSMConstants  # type: ignore[assignment]
    except ImportError:
        # Define minimal constants if import fails
        class HSMConstants:
            MIN_DISK_SPACE_MB = 1500
            SUPPORTED_ARCHITECTURES = ["x86_64", "s390x", "ppc64le", "ppc64", "powerpc", "AMD64"]
            HSM_PACKAGES = [
                "gskcrypt64", "gskssl64", "TIVsm-API64", "TIVsm-APIcit",
                "TIVsm-BA", "TIVsm-BAcit", "TIVsm-HSM", "TIVsm-WEBGUI"
            ]
            INSTALL_ORDER = ["gskcrypt64", "gskssl64", "TIVsm-API64", "TIVsm-BA", "TIVsm-HSM"]
            UNINSTALL_ORDER = ["TIVsm-WEBGUI", "TIVsm-HSM", "TIVsm-BAcit", "TIVsm-BA",
                              "TIVsm-APIcit", "TIVsm-API64", "gskssl64", "gskcrypt64"]
            HSM_COMMANDS = {
                'global_deactivate': 'dsmmigfs globaldeactivate',
                'disable_failover': 'dsmmigfs disablefailover',
                'query': 'dsmmigfs q -d',
                'global_reactivate': 'dsmmigfs globalreactivate',
                'enable_failover': 'dsmmigfs enablefailover',
                'wait': 'dsmmigfs wait'
            }
            GPG_KEY_FILE = "GSKit.pub4.pgp"


def compare_versions(version1, version2):
    """
    Compare two version strings.
    Returns: 1 if version1 > version2, -1 if version1 < version2, 0 if equal
    """
    try:
        # Split versions into parts and convert to integers where possible
        def normalize(v):
            parts = re.split(r'[.\-_]', str(v))
            normalized = []
            for part in parts:
                try:
                    normalized.append(int(part))
                except ValueError:
                    normalized.append(part)
            return normalized
        
        v1_parts = normalize(version1)
        v2_parts = normalize(version2)
        
        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))
        
        # Compare part by part
        for p1, p2 in zip(v1_parts, v2_parts):
            if isinstance(p1, int) and isinstance(p2, int):
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            else:
                # String comparison
                if str(p1) > str(p2):
                    return 1
                elif str(p1) < str(p2):
                    return -1
        return 0
    except Exception:
        # Fallback to string comparison
        if str(version1) > str(version2):
            return 1
        elif str(version1) < str(version2):
            return -1
        return 0


class HSMClientHelper:
    """Helper class for HSM Client operations on Linux, Windows, and AIX"""
    
    def __init__(self, module: AnsibleModule):
        self.module = module
        # Use constants from HSMConstants
        self.hsm_packages = HSMConstants.HSM_PACKAGES
        self.hsm_commands = HSMConstants.HSM_COMMANDS
        self.gpg_key_file = HSMConstants.GPG_KEY_FILE
    
    def run_cmd(self, cmd, use_unsafe_shell=False, check_rc=True):
        """Execute a command and return results"""
        rc, out, err = self.module.run_command(cmd, use_unsafe_shell=use_unsafe_shell)
        if check_rc and rc != 0:
            self.module.fail_json(msg=f"Command failed: {cmd}\nError: {err}")
        return rc, out, err
    
    def log(self, msg):
        """Log a message"""
        try:
            if self.is_windows():
                print(msg)
            else:
                self.module.warn(msg)
        except Exception:
            pass
    
    def file_exists(self, path):
        """Check if a file exists"""
        if self.is_windows():
            cmd = f'cmd /c if exist "{path}" (exit 0) else (exit 1)'
            rc, out, err = self.run_cmd(cmd, check_rc=False)
            return rc == 0
        else:
            return os.path.exists(path)
    
    def is_windows(self):
        """Check if running on Windows"""
        return platform.system().lower().startswith("win")
    
    def is_newer_version(self, target, current):
        """Check if target version is newer than current"""
        try:
            return compare_versions(target, current) > 0
        except Exception:
            return target != current
    
    def check_installed(self):
        """
        Check if HSM Client is installed and return version.
        Supports Linux (RPM) and AIX (lslpp).
        Returns: (is_installed: bool, version: str or None)
        """
        if self.is_windows():
            try:
                cmd = 'reg query "HKLM\\SOFTWARE\\IBM\\ADSM\\CurrentVersion\\HSM" /v PtfLevel'
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                if rc == 0 and "PtfLevel" in out:
                    version = out.split()[-1]
                    return True, version
                return False, None
            except Exception as e:
                return False, None
        else:
            # Detect platform (AIX vs Linux)
            is_aix = platform.system().lower() == 'aix'
            
            if is_aix:
                # AIX: Use lslpp to check for TIVsm.client.hsm
                cmd = "lslpp -l TIVsm.client.hsm"
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                
                if rc == 0 and "TIVsm.client.hsm" in out:
                    # Parse version from lslpp output
                    # Example output line: TIVsm.client.hsm  8.2.1.0  COMMITTED  IBM Spectrum Protect HSM
                    for line in out.strip().split('\n'):
                        if 'TIVsm.client.hsm' in line and not line.startswith('Fileset'):
                            parts = line.split()
                            if len(parts) >= 2:
                                version = parts[1]  # Version is second column
                                return True, version
                    return True, "unknown"
                elif rc == 1:
                    return False, None
                else:
                    self.module.warn(f"lslpp command failed: {err.strip()}")
                    return False, None
            else:
                # Linux: Check for any TIVsm package (HSM, BA, or API64)
                # Try HSM first
                cmd = "rpm -q TIVsm-HSM"
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                
                if rc == 0 and "TIVsm-HSM" in out:
                    # Parse version from RPM output
                    # Example: TIVsm-HSM-8.1.25-0.x86_64
                    rpm_full = out.strip().replace("TIVsm-HSM-", "")
                    rpm_no_arch = rpm_full.split(".x86_64")[0].split(".s390x")[0].split(".ppc64le")[0]
                    version = rpm_no_arch.replace("-", ".")
                    return True, version
                
                # Try BA Client
                cmd = "rpm -q TIVsm-BA"
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                
                if rc == 0 and "TIVsm-BA" in out:
                    # Parse version from RPM output
                    # Example: TIVsm-BA-8.2.2-0.x86_64
                    rpm_full = out.strip().replace("TIVsm-BA-", "")
                    rpm_no_arch = rpm_full.split(".x86_64")[0].split(".s390x")[0].split(".ppc64le")[0]
                    version = rpm_no_arch.replace("-", ".")
                    return True, version
                
                # Try API64
                cmd = "rpm -q TIVsm-API64"
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                
                if rc == 0 and "TIVsm-API64" in out:
                    # Parse version from RPM output
                    # Example: TIVsm-API64-8.2.2-0.x86_64
                    rpm_full = out.strip().replace("TIVsm-API64-", "")
                    rpm_no_arch = rpm_full.split(".x86_64")[0].split(".s390x")[0].split(".ppc64le")[0]
                    version = rpm_no_arch.replace("-", ".")
                    return True, version
                
                # Nothing found
                return False, None
    
    def verify_system_prereqs(self, check_gpfs=True):
        """
        Verify system prerequisites (OS, architecture, privileges, disk, GPFS).
        
        Args:
            check_gpfs (bool): Whether to check GPFS prerequisite (default: True)
                              Set to False for BA client installation
        
        Returns:
            dict: Summary of prerequisite checks
        """
        min_disk_mb = HSMConstants.MIN_DISK_SPACE_MB
        compatible_arch = HSMConstants.SUPPORTED_ARCHITECTURES
        
        # Get architecture - AIX needs special handling
        if platform.system() == "AIX":
            # On AIX, platform.machine() returns serial number, use uname -p instead
            rc, out, err = self.run_cmd("uname -p", check_rc=False)
            arch = out.strip() if rc == 0 else "unknown"
        else:
            arch = platform.machine()
        
        sys_info = {
            "os": platform.system(),
            "arch": arch,
            "hostname": platform.node(),
        }
        
        # Check privileges
        if self.is_windows():
            # check admin membership
            rc, out, err = self.run_cmd('whoami /groups | find "Administrators"', use_unsafe_shell=True, check_rc=False)
            if rc != 0:
                self.module.fail_json(
                    msg="Admin privileges required to install HSM Client on Windows"
                )
        else:
            if os.geteuid() != 0:
                self.module.fail_json(
                    msg="Root privileges required to install HSM Client on Linux/AIX"
                )
        
        # Check architecture
        arch_compatible = sys_info["arch"] in compatible_arch
        if not arch_compatible:
            self.module.fail_json(
                msg=f"Incompatible architecture: {sys_info['arch']}. "
                    f"Supported: {', '.join(compatible_arch)}"
            )
        
        # Check disk space
        st = shutil.disk_usage("/")
        free_mb = st.free // (1024 * 1024)
        if free_mb < min_disk_mb:
            self.module.fail_json(
                msg=f"Insufficient disk space. Required: {min_disk_mb} MB, Available: {free_mb} MB"
            )
        
        # CRITICAL: Check GPFS prerequisite for HSM Client
        gpfs_status = None
        if check_gpfs and not self.is_windows():
            self.log("Checking GPFS (IBM Spectrum Scale) prerequisite...")
            gpfs_status = self.check_gpfs_status()
            
            if not gpfs_status:
                self.module.fail_json(
                    msg="CRITICAL: GPFS (IBM Spectrum Scale) is REQUIRED for HSM Client installation but is not installed or not active. "
                        "Please install and activate GPFS before installing HSM Client. "
                        "HSM (Hierarchical Storage Management) requires GPFS to manage file migrations."
                )
            
            self.log(f"GPFS Status: {gpfs_status}")
        
        summary = (
            f"System Compatibility Summary:\n"
            f"- OS: {sys_info['os']}\n"
            f"- Architecture: {sys_info['arch']} (compatible: {arch_compatible})\n"
            f"- Free Disk Space: {free_mb} MB (required ≥ {min_disk_mb})\n"
        )
        
        if gpfs_status:
            summary += f"- GPFS Status: {'ACTIVE ✓' if gpfs_status else 'NOT ACTIVE ✗'}\n"
        
        self.module.warn(summary)
        
        return {
            "status": "ok",
            "architecture": sys_info["arch"],
            "arch_compatible": arch_compatible,
            "disk_space_ok": free_mb >= min_disk_mb,
            "free_mb": free_mb,
        }
    
    def extract_package(self, src, dest):
        """Extract tarball and ensure RPMs exist"""
        
        if self.is_windows():
            if (os.path.exists(dest)):
                self.run_cmd(cmd=f"powershell -Command \"Remove-Item -Path '{dest}' -Recurse -Force -ErrorAction SilentlyContinue\"")
            self.run_cmd(cmd=f"\"{src}\" -y -o\"{dest}\"")
            return
        
        # Validation
        if not os.path.exists(src):
            self.module.fail_json(msg=f"Package source not found: {src}")
        if os.path.isdir(src):
            self.module.fail_json(msg=f"Expected a tarball file, got directory instead: {src}")
        
        # Ensure destination directory exists
        os.makedirs(dest, exist_ok=True)
        
        # Check if file is compressed
        is_gzipped = src.endswith('.gz') or src.endswith('.tar.gz')
        is_compressed = src.endswith('.Z') or src.endswith('.tar.Z')
        
        if is_gzipped:
            # Gunzip first for GA/DVD builds
            self.module.warn("Detected gzipped archive, extracting...")
            gunzip_cmd = f'gunzip -f "{src}"'
            rc, out, err = self.run_cmd(gunzip_cmd, use_unsafe_shell=True, check_rc=False)
            # Update src to point to unzipped file
            src = src.replace('.gz', '')
        elif is_compressed:
            # Uncompress for AIX builds (.Z files) - two-step process
            self.module.warn("Detected Unix compressed archive (.Z), decompressing...")
            # Create a copy to preserve original
            uncompressed_src = src.replace('.Z', '')
            uncompress_cmd = f'uncompress -c "{src}" > "{uncompressed_src}"'
            rc, out, err = self.run_cmd(uncompress_cmd, use_unsafe_shell=True, check_rc=False)
            if rc != 0:
                self.module.fail_json(msg=f"Uncompress failed: {err}")
            # Update src to point to uncompressed file
            src = uncompressed_src
        
        # Extraction
        cmd = f'tar -xvf "{src}" -C "{dest}"'
        rc, out, err = self.run_cmd(cmd, use_unsafe_shell=True)
        if rc != 0:
            self.module.fail_json(msg=f"Extraction failed: {err}")
        
        # Log extraction output for debugging
        self.module.warn(f"Extraction output (first 500 chars): {out[:500]}")
        
        # List what was extracted
        list_cmd = f'ls -la "{dest}"'
        rc, list_out, list_err = self.run_cmd(list_cmd, use_unsafe_shell=True, check_rc=False)
        self.module.warn(f"Contents of {dest}: {list_out}")
        
        # Find package files (RPM for Linux, BFF/installp for AIX)
        package_files = []
        for root, _, files in os.walk(dest):
            for f in files:
                # RPM files for Linux
                if f.endswith(".rpm"):
                    package_files.append(os.path.join(root, f))
                # AIX installp/BFF format files (no extension or specific patterns)
                elif not f.endswith(('.htm', '.html', '.txt', '.md')):
                    # Check if it's an AIX package file
                    full_path = os.path.join(root, f)
                    # AIX packages typically start with specific prefixes
                    if any(f.startswith(prefix) for prefix in ['tivoli.', 'GSKit', 'gsk']):
                        package_files.append(full_path)
        
        if not package_files:
            # List all files found for debugging
            all_files = []
            for root, _, files in os.walk(dest):
                all_files += [os.path.join(root, f) for f in files]
            self.module.fail_json(
                msg=f"No package files found in extracted directory: {dest}",
                all_files_found=all_files[:20],  # First 20 files
                total_files=len(all_files)
            )
        
        self.module.warn(f"Found {len(package_files)} package files")
        return os.path.dirname(package_files[0])
    
    def import_gpg_key(self, rpm_dir):
        """Import GPG key for package verification"""
        gpg_key_path = os.path.join(rpm_dir, self.gpg_key_file)
        
        if os.path.exists(gpg_key_path):
            self.module.warn(f"Importing GPG key from {gpg_key_path}")
            cmd = f'rpm --import "{gpg_key_path}"'
            rc, out, err = self.run_cmd(cmd, use_unsafe_shell=True, check_rc=False)
            if rc == 0:
                self.module.warn("GPG key imported successfully")
            else:
                self.module.warn(f"GPG key import failed: {err}")
        else:
            self.module.warn(f"GPG key file not found: {gpg_key_path}")
    
    def verify_package_signatures(self, rpm_dir):
        """Verify RPM package signatures"""
        self.module.warn("Verifying package signatures...")
        cmd = f'rpm --checksig --verbose "{rpm_dir}"/*.rpm'
        rc, out, err = self.run_cmd(cmd, use_unsafe_shell=True, check_rc=False)
        
        if rc == 0:
            self.module.warn("Package signature verification successful")
            return True
        else:
            self.module.warn(f"Package signature verification failed: {err}")
            return False
    
    def check_gpfs_status(self):
        """
        Check if GPFS (IBM Spectrum Scale) is installed and active.
        
        Returns:
            bool: True if GPFS is installed and active, False otherwise
        """
        self.module.warn("Checking GPFS (IBM Spectrum Scale) status...")
        
        # On AIX, GPFS commands are in /usr/lpp/mmfs/bin/ (not in PATH)
        if platform.system() == "AIX":
            gpfs_bin = "/usr/lpp/mmfs/bin/"
            mmgetstate_cmd = f"{gpfs_bin}mmgetstate -a"
        else:
            mmgetstate_cmd = "mmgetstate -a"
        
        # Check GPFS state directly (no need to check 'which' on AIX)
        rc, out, err = self.run_cmd(mmgetstate_cmd, use_unsafe_shell=True, check_rc=False)
        
        if rc != 0:
            self.module.warn("GPFS commands not found. GPFS is not installed.")
            return False
        
        if rc == 0:
            # Check if any node is active
            if "active" in out.lower():
                self.module.warn("GPFS is installed and ACTIVE ✓")
                return True
            else:
                self.module.warn("GPFS is installed but NOT ACTIVE ✗")
                return False
        else:
            self.module.warn(f"GPFS state check failed: {err}")
            return False
    
    def check_hsm_status(self):
        """Check HSM status using dsmmigfs"""
        cmd = self.hsm_commands['query']
        rc, out, err = self.run_cmd(cmd, use_unsafe_shell=True, check_rc=False)
        
        if rc == 0:
            self.module.warn(f"HSM Status: {out}")
            return out
        else:
            self.module.warn(f"HSM status check failed (may not be configured yet): {err}")
            return None
    
    
    def verify_client_version(self):
        """Verify client version using dsmc query session"""
        self.module.warn("Verifying client version...")
        cmd = "dsmc query session"
        rc, out, err = self.run_cmd(cmd, use_unsafe_shell=True, check_rc=False)
        
        if rc == 0:
            self.module.warn(f"Client version info: {out}")
            return out
        else:
            self.module.warn(f"Client version check failed: {err}")
            return None
    
    def test_server_connectivity(self):
        """Test connectivity to TSM server"""
        self.module.warn("Testing server connectivity...")
        
        # Test session
        cmd = "dsmc query session"
        rc, out, err = self.run_cmd(cmd, use_unsafe_shell=True, check_rc=False)
        
        if rc == 0:
            self.module.warn("Server connectivity test: SUCCESS")
            return True
        else:
            self.module.warn(f"Server connectivity test: FAILED - {err}")
            return False
    
    def test_filespace_access(self):
        """Test filespace access"""
        self.module.warn("Testing filespace access...")
        cmd = "dsmc query filespace"
        rc, out, err = self.run_cmd(cmd, use_unsafe_shell=True, check_rc=False)
        
        if rc == 0:
            self.module.warn(f"Filespace access test: SUCCESS - {out}")
            return True
        else:
            self.module.warn(f"Filespace access test: FAILED - {err}")
            return False
    
    def install_hsm_client(self, package_source, install_path, temp_dir):
        """
        Install HSM Client from extracted RPMs (Linux/AIX) or EXE (Windows).
        Performs extraction automatically if needed.
        Includes GPG verification and complete package list.
        """
        if self.is_windows():
            if not os.path.exists(package_source):
                self.module.fail_json(msg=f"Package source not found: {package_source}")

            self.extract_package(package_source, temp_dir)
            # silent install typical pattern
            file_loc = os.path.dirname(package_source)
            with open("testt.txt", "w") as tfr:
                tfr.write("Installation started")

            cmd = f"\"{file_loc}/hsmClient/TSMClient/IBM Storage Protect Client.msi\" /qn INSTALLDIR=\"{install_path}\" /l*v install_hsmclient.log"
            
            rc, out, err = self.run_cmd(cmd, use_unsafe_shell=True)
            if rc != 0:
                print("Installation Failed")
                print(err)
            else:
                print("Installation succeeded. Exit code: " + str(rc))

            print("HSM Client installation completed successfully")
            return True
        else:
            # Extract package
            rpm_dir: str
            if package_source.endswith(".tar") or package_source.endswith(".tar.gz") or package_source.endswith(".tar.Z"):
                extracted_dir = self.extract_package(package_source, temp_dir)
                if not extracted_dir:
                    self.module.fail_json(msg=f"Failed to extract package: {package_source}")
                rpm_dir = extracted_dir
            elif os.path.isdir(package_source):
                rpm_dir = package_source
            else:
                self.module.fail_json(msg=f"Invalid package source: {package_source}")
            
            # Detect if AIX or Linux
            is_aix = platform.system().lower() == 'aix'
            
            if is_aix:
                # AIX uses installp, not rpm
                self.module.warn("Detected AIX system - using installp for installation")
                
                # Find all package files (BFF format)
                package_files = []
                for root, _, files in os.walk(rpm_dir):
                    for f in files:
                        if not f.endswith(('.htm', '.html', '.txt', '.md')):
                            if any(f.startswith(prefix) for prefix in ['tivoli.', 'GSKit', 'gsk']):
                                package_files.append(os.path.join(root, f))
                
                if not package_files:
                    self.module.fail_json(msg=f"No AIX package files found under {rpm_dir}")
                
                # AIX install order - HSM Client only (skip BA client)
                aix_install_order = [
                    "GSKit8.gskcrypt64",
                    "GSKit8.gskssl64",
                    "tivoli.tsm.client.api.64bit",
                    "tivoli.tsm.client.hsm",  # HSM client (includes GPFS support)
                    "tivoli.tsm.client.webgui"
                ]
                
                try:
                    for pkg_pattern in aix_install_order:
                        # Find matching package
                        matching_pkgs = [pkg for pkg in package_files if pkg_pattern in os.path.basename(pkg)]
                        if matching_pkgs:
                            for pkg in matching_pkgs:
                                pkg_name = os.path.basename(pkg)
                                # Check if already installed
                                check_cmd = f"lslpp -l {pkg_name}"
                                rc, _, _ = self.run_cmd(check_cmd, check_rc=False)
                                
                                if rc != 0:  # Not installed
                                    install_cmd = f'installp -acgXYd "{rpm_dir}" {pkg_name}'
                                    rc, out, err = self.run_cmd(install_cmd, use_unsafe_shell=True, check_rc=False)
                                    if rc != 0:
                                        raise Exception(f"Failed to install {pkg_name}: {err}")
                                    self.log(f"Installed: {pkg_name}")
                                else:
                                    self.log(f"Already installed: {pkg_name}")
                        else:
                            # Some packages might be optional
                            if "webgui" not in pkg_pattern.lower():
                                self.module.warn(f"Package {pkg_pattern} not found in directory")
                
                except Exception as e:
                    self.log(f"Installation failed: {e}")
                    raise
            else:
                # Linux uses RPM
                # Import GPG key for verification
                self.import_gpg_key(rpm_dir)
                
                # Verify package signatures
                self.verify_package_signatures(rpm_dir)
                
                # Find all RPM files
                rpm_files = []
                for root, _, files in os.walk(rpm_dir):
                    rpm_files += [os.path.join(root, f) for f in files if f.endswith(".rpm")]
                
                if not rpm_files:
                    self.module.fail_json(msg=f"No RPM files found under {rpm_dir}")
                
                # Complete install order from config.ini (packages_to_remove order)
                install_order = [
                    "gskcrypt64",
                    "gskssl64",
                    "TIVsm-API64",
                    "TIVsm-APIcit",
                    "TIVsm-BA",        # Base Backup-Archive client
                    "TIVsm-BAcit",     # BA Common Interface
                    "TIVsm-HSM",       # HSM component
                    "TIVsm-WEBGUI"     # Web GUI
                ]
                
                try:
                    for pkg_name in install_order:
                        # Find matching RPM
                        matching_rpms = [rpm for rpm in rpm_files if pkg_name in os.path.basename(rpm)]
                        if matching_rpms:
                            for rpm in matching_rpms:
                                # Check if already installed
                                check_cmd = f"rpm -q {pkg_name}"
                                rc, _, _ = self.run_cmd(check_cmd, check_rc=False)
                                
                                if rc != 0:  # Not installed
                                    install_cmd = f'rpm -ivh "{rpm}"'
                                    rc, out, err = self.run_cmd(install_cmd, use_unsafe_shell=True, check_rc=False)
                                    if rc != 0:
                                        raise Exception(f"Failed to install {pkg_name}: {err}")
                                    self.log(f"Installed: {pkg_name}")
                                else:
                                    self.log(f"Already installed: {pkg_name}")
                        else:
                            # Some packages might be optional
                            if pkg_name not in ["TIVsm-WEBGUI"]:
                                self.module.warn(f"Package {pkg_name} not found in RPM directory")
                
                except Exception as e:
                    self.log(f"Installation failed: {e}")
                    # Rollback
                    self._uninstall_packages(install_order)
                    raise
            
            self.log("HSM Client installation completed successfully")
            return True
    
    def _uninstall_packages(self, package_list):
        """Uninstall packages in reverse order"""
        for pkg in reversed(package_list):
            cmd = f"rpm -e --nodeps --noscripts {pkg}"
            self.run_cmd(cmd, check_rc=False)
    
    def rollback(self, action="install", previous_version=None):
        """
        Rollback mechanism for HSM Client operations.
        - action='install' → uninstall packages
        - action='upgrade' → restore previous version
        - action='uninstall' → reinstall packages
        """
        self.module.warn(f"Initiating rollback for action={action}")
        print(f"Initiating rollback for action={action}")

        if self.is_windows():
            return self._rollback_windows(action, previous_version)
        else:
            return self._rollback_linux(action)
    
    # LINUX/AIX ROLLBACK
    def _rollback_linux(self, action):
        results = []
        package_dir = "/opt/hsmClient"
        backup_dir = "/opt/hsmClientPackagesBk"
        
        # Detect platform
        is_aix = platform.system().lower() == 'aix'
        
        # INSTALL FAILURE
        if action == "install":
            # Platform-specific uninstall order and commands
            if is_aix:
                uninstall_order = [
                    "TIVsm.client.hsm",
                    "TIVsm.client.bacit",
                    "TIVsm.client.ba",
                    "TIVsm.client.api64cit",
                    "TIVsm.client.api64",
                    "gsk8ssl64",
                    "gsk8cry64"
                ]
                uninstall_cmd_template = "installp -u {}"
                verify_cmd = "lslpp -l 'TIVsm*'"
            else:  # Linux
                uninstall_order = [
                    "TIVsm-WEBGUI",
                    "TIVsm-HSM",
                    "TIVsm-BAcit",
                    "TIVsm-BA",
                    "TIVsm-APIcit",
                    "TIVsm-API64",
                    "gskssl64",
                    "gskcrypt64"
                ]
                uninstall_cmd_template = "rpm -e --nodeps --noscripts {}"
                verify_cmd = "rpm -qa 'TIVsm*'"
            
            self.module.warn(f"Rollback: uninstalling packages from failed installation ({'AIX' if is_aix else 'Linux'}).")
            for pkg in uninstall_order:
                cmd = uninstall_cmd_template.format(pkg)
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                results.append({
                    "package": pkg,
                    "rc": rc,
                    "stdout": out.strip(),
                    "stderr": err.strip()
                })
                if rc != 0:
                    self.module.warn(f"Rollback warning: Failed to remove {pkg}, rc={rc}")
            
            # Verify cleanup
            rc, out, _ = self.run_cmd(verify_cmd, check_rc=False)
            if not out.strip():
                rollback_status = "Rollback successful: All TIVsm packages removed."
            else:
                rollback_status = f"Rollback warning: Some TIVsm packages still present:\n{out.strip()}"
            
            self.module.warn(rollback_status)
            return {"rollback_type": action, "results": results, "status": rollback_status}
        
        # UNINSTALL FAILURE
        elif action == "uninstall":
            # Platform-specific reinstall order and commands
            if is_aix:
                reinstall_order = [
                    "gsk8cry64", "gsk8ssl64", "TIVsm.client.api64", "TIVsm.client.api64cit",
                    "TIVsm.client.ba", "TIVsm.client.bacit", "TIVsm.client.hsm"
                ]
                install_cmd_template = "installp -acXYgd {} {}"
            else:  # Linux
                reinstall_order = [
                    "gskcrypt64", "gskssl64", "TIVsm-API64", "TIVsm-APIcit",
                    "TIVsm-BA", "TIVsm-BAcit", "TIVsm-HSM", "TIVsm-WEBGUI"
                ]
                install_cmd_template = "rpm -ivh {}/{}.rpm"
            
            self.module.warn(f"Rollback: reinstalling packages due to failed uninstallation ({'AIX' if is_aix else 'Linux'}).")
            for pkg in reinstall_order:
                if is_aix:
                    cmd = install_cmd_template.format(package_dir, pkg)
                else:
                    rpm_pattern = f"{package_dir}/{pkg}*"
                    cmd = f"rpm -ivh {rpm_pattern}"
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                results.append({"package": pkg, "rc": rc, "stderr": err.strip()})
            self.module.warn("Rollback successful: All packages reinstalled after uninstall failure.")
            return {"rollback_type": "uninstall", "results": results}
        
        # UPGRADE FAILURE
        elif action == "upgrade":
            self.module.warn("Rollback: restoring previous version and configuration files.")
            backup_files = [
                "/opt/tivoli/tsm/client/hsm/bin/dsm.opt.bk",
                "/opt/tivoli/tsm/client/hsm/bin/dsm.sys.bk"
            ]
            
            # Restore configuration files
            for file in backup_files:
                orig = file.replace(".bk", "")
                if os.path.exists(file):
                    shutil.copy(file, orig)
                    results.append({"file_restored": orig, "status": "restored"})
                else:
                    results.append({"file_restored": orig, "status": "backup_missing"})
            
            # Remove the new upgrade version
            self.run_cmd("rpm -e $(rpm -qa 'TIVsm*')", check_rc=False)
            
            # Reinstall previous packages from backup
            reinstall_order = [
                "gskcrypt64", "gskssl64", "TIVsm-API64", "TIVsm-APIcit", "TIVsm-HSM"
            ]
            
            for pkg in reinstall_order:
                rpm_pattern = f"{backup_dir}/{pkg}*.rpm"
                cmd = f"rpm -ivh {rpm_pattern}"
                self.module.warn(f"Rollback command: {cmd}")
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                results.append({"package": pkg, "rc": rc, "stderr": err.strip()})
            
            # Cleanup
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir, ignore_errors=True)
                results.append({"cleanup": backup_dir, "status": "removed"})
            
            self.module.warn("Rollback successful: Previous version and configs restored after upgrade failure.")
            return {"rollback_type": "upgrade", "results": results}

    # WINDOWS ROLLBACK
    def _rollback_windows(self, action, previous_version=None):
        results = []

        # ---------------- INSTALL FAILURE -----------------
        if action == "install":
            uninstall_targets = [
                "IBM Storage Protect Client",
                "IBM Spectrum Protect Client",
                "Tivoli Storage Manager Client"
            ]
            for target in uninstall_targets:
                ps_cmd = (
                    f'Get-WmiObject -Class Win32_Product | '
                    f'Where-Object {{ $_.Name -like "*{target}*" }} | '
                    f'ForEach-Object {{ $_.Uninstall() }}'
                )
                rc, out, err = self.run_cmd(["powershell.exe", "-Command", ps_cmd], check_rc=False)
                results.append({"package": target, "rc": rc, "stderr": err.strip()})
            return {"rollback_type": "install", "results": results}

        # ---------------- UNINSTALL FAILURE -----------------
        elif action == "uninstall":
            self.module.log("Rollback: reinstalling HSM Client on Windows after uninstall failure.")
            install_dir = getattr(self, 'install_dir', r"C:\Program Files\Tivoli\tsm\client\hsm\bin")
            installer_path = os.path.join(install_dir, "TSMClient", "install.exe")
            if os.path.exists(installer_path):
                cmd = f'"{installer_path}" /qn REINSTALL=ALL REINSTALLMODE=vomus'
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                results.append({"package": "HSM Client", "rc": rc, "stderr": err.strip()})
            else:
                results.append({"package": "HSM Client", "error": "Installer not found"})
            return {"rollback_type": "uninstall", "results": results}

        # ---------------- UPGRADE FAILURE -----------------
        elif action == "upgrade":
            self.module.log("Rollback: restoring previous HSM Client version and configs on Windows.")
            backup_dir = r"C:\temp\hsmClientBackup"
            config_files = [
                r"C:\Program Files\Tivoli\tsm\client\hsm\bin\dsm.opt.bk",
                r"C:\Program Files\Tivoli\tsm\client\hsm\bin\dsm.sys.bk"
            ]

            # Step 1: Restore config backups
            for file in config_files:
                orig = file.replace(".bk", "")
                if os.path.exists(file):
                    shutil.copy(file, orig)
                    results.append({"file_restored": orig, "status": "restored"})
                else:
                    results.append({"file_restored": orig, "status": "backup_missing"})

            # Step 2: Reinstall previous version from backup
            if previous_version:
                installer_name = f"{previous_version}-TIV-TSMHSM-WinX64.exe"
                installer_path = os.path.join(backup_dir, installer_name)
            else:
                results.append({"package": "HSM Client", "error": "Previous version unknown"})
                installer_name = ""
                installer_path = ""

            if installer_name and os.path.exists(installer_path):
                install_dir = getattr(self, 'install_dir', r"C:\Program Files\Tivoli\tsm\client\hsm\bin")
                cmd = f'"{installer_path}" /qn INSTALLDIR="{install_dir}"'
                rc, out, err = self.run_cmd(cmd, check_rc=False)
                results.append({"package": "HSM Client", "rc": rc, "stderr": err.strip()})
            else:
                results.append({"package": "HSM Client", "error": "Backup installer missing"})

            # Step 3: Remove backup dir
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir, ignore_errors=True)
                results.append({"cleanup": backup_dir, "status": "removed"})

            return {"rollback_type": "upgrade", "results": results}
            return {"rollback_type": "upgrade", "results": results}
    
    def post_installation_verification(self, hsm_client_version, state):
        """Verify that HSM Client is installed correctly and return status summary"""
        
        if self.is_windows():
            check_cmd = 'wmic product get name | find "IBM Storage Protect Client"'
            print(check_cmd)
        else:
            check_cmd = "rpm -q TIVsm-HSM"
        
        rc, out, err = self.run_cmd(check_cmd, use_unsafe_shell=self.is_windows(), check_rc=False)
        
        if rc == 0:
            if self.is_windows():
                print(f"HSM Client {hsm_client_version} installation status: Installed Successfully")
            else:
                self.module.warn(f"HSM Client {hsm_client_version} installation status: Installed Successfully")
            installation_successful = True
        else:
            msg = f"HSM Client {hsm_client_version} installation status: Not Installed\nError: {err.strip()}"
            if self.is_windows():
                print(msg)
            else:
                self.module.warn(msg)
            
            if state == "install":
                self.module.fail_json(msg="HSM Client installation verification failed. Please check logs.")
            installation_successful = False
        
        return {
            "is_installation_successful": installation_successful,
            "hsm_client_version": hsm_client_version
        }
    
    def configure_hsm_client(self):
        """Configure HSM Client with default settings"""
        if self.is_windows():
            config_dir = r"C:\Program Files\Tivoli\tsm\client\hsm\bin"
        else:
            config_dir = "/opt/tivoli/tsm/client/hsm/bin"
        dsm_opt = f"{config_dir}/dsm.opt"
        dsm_sys = f"{config_dir}/dsm.sys"
        
        # Ensure directory exists
        os.makedirs(config_dir, exist_ok=True)
        
        # DSM.SYS
        sys_content = """SErvername  TSM_SERVER
    TCPServeraddress  your.server.address
    TCPPort           1500
    """
        
        if not os.path.exists(dsm_sys):
            with open(dsm_sys, "w") as f:
                f.write(sys_content)
            self.module.warn("Created default dsm.sys configuration.")
        else:
            with open(dsm_sys, "a") as f:
                f.write("\n" + sys_content)
            self.module.warn("Updated existing dsm.sys configuration.")
        
        # DSM.OPT
        if self.is_windows():
            opt_content = """SErvername  TSM_SERVER
    NODename   your_node_name
    PasswordDir C:\\Program Files\\Tivoli\\tsm\\client\\hsm\\bin
    """
        else:
            opt_content = """SErvername  TSM_SERVER
    NODename   your_node_name
    PasswordDir /opt/tivoli/tsm/client/hsm/bin
    """
        
        if not os.path.exists(dsm_opt):
            with open(dsm_opt, "w") as f:
                f.write(opt_content)
            self.module.warn("Created default dsm.opt configuration.")
        else:
            with open(dsm_opt, "a") as f:
                f.write("\n" + opt_content)
            self.module.warn("Updated existing dsm.opt configuration.")
        
        # Validation
        if os.path.exists(dsm_opt) and os.path.exists(dsm_sys):
            self.module.warn("HSM Client configuration files created/updated successfully.")
        else:
            self.module.warn("HSM Client configuration missing or not applied correctly.")
    
    def start_hsm_daemon(self, hsm_client_start_daemon):
        """Enable and start HSM Client daemon/service across platforms"""
        
        if not hsm_client_start_daemon:
            self.module.warn("Skipping daemon start as hsm_client_start_daemon=False")
            return {"daemon_enabled": False}
        
        if self.is_windows():
            # On Windows HSM Client usually does not auto-create a service.
            # We should verify existence before starting.

            rc, out, err = self.run_cmd(
                'powershell -Command "Get-Service | Where-Object {$_.Name -like \'*dsmhsm*\' } | Select -ExpandProperty Name"',
                check_rc=False
            )

            services = [s.strip() for s in out.splitlines() if s.strip()]

            if not services:
                self.module.warn("No HSM Client Windows service found. Skipping daemon start.")
                return {"daemon_enabled": False}

            for svc in services:
                rc_start, out_start, err_start = self.run_cmd(f'net start "{svc}"', check_rc=False)

                if rc_start == 0:
                    self.module.warn(f"Windows service '{svc}' started successfully.")
                else:
                    self.module.warn(f"Failed to start Windows service '{svc}': {err_start.strip()}")

            return {"daemon_enabled": True}

        else:
            # Enable service
            rc_enable, out_enable, err_enable = self.run_cmd(
                "systemctl enable dsmhsm.service",
                check_rc=False
            )
            if rc_enable != 0:
                self.module.warn(f"Failed to enable dsmhsm.service: {err_enable.strip()}")
            
            # Start service
            rc_start, out_start, err_start = self.run_cmd(
                "systemctl start dsmhsm.service",
                check_rc=False
            )
            if rc_start != 0:
                self.module.warn(f"Failed to start dsmhsm.service: {err_start.strip()}")
            else:
                self.module.warn("dsmhsm.service started successfully.")
            
            # Check status
            rc_status, out_status, err_status = self.run_cmd(
                "systemctl is-enabled dsmhsm.service",
                check_rc=False
            )
            if rc_status == 0 and out_status.strip() == "enabled":
                self.module.warn("dsmhsm.service is enabled and active.")
                daemon_enabled = True
            else:
                self.module.warn(f"Failed to enable/start dsmhsm.service. Status: {out_status.strip()}")
                daemon_enabled = False
            
            return {"daemon_enabled": daemon_enabled}
    
    def uninstall_hsm_client(self, extract_dest="/opt/hsmClient", backup_dir="/opt/hsmClientPackagesBk"):
        """
        Performs complete uninstallation of HSM Client and dependent packages with backup and rollback.
        Supports Linux (RPM) and AIX (installp) platforms.
        """
        if self.is_windows():
            cmd = 'powershell "Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like \'*IBM Storage Protect Client*\' } | ForEach-Object { $_.Uninstall() }"'
            rc, out, err = self.run_cmd(cmd, use_unsafe_shell=True, check_rc=False)
            if rc != 0:
                self.module.fail_json(msg=f"Uninstallation failed: {err}")
            return True

        # Detect platform (AIX vs Linux)
        is_aix = platform.system().lower() == 'aix'
        
        # Platform-specific commands and package names
        if is_aix:
            check_cmd = "lslpp -l TIVsm.client.hsm"
            uninstall_order = [
                "TIVsm.client.hsm",
                "TIVsm.client.bacit",
                "TIVsm.client.ba",
                "TIVsm.client.api64cit",
                "TIVsm.client.api64",
                "gsk8ssl64",
                "gsk8cry64"
            ]
            stop_service_cmd = "/etc/rc.gpfshsm stop"
        else:  # Linux
            # Check for any TIVsm package (HSM, BA, or API64)
            check_cmd = "rpm -qa 'TIVsm*'"
            uninstall_order = [
                "TIVsm-WEBGUI",
                "TIVsm-HSM",
                "TIVsm-BAcit",
                "TIVsm-BA",
                "TIVsm-APIcit",
                "TIVsm-API64",
                "gskssl64",
                "gskcrypt64"
            ]
            stop_service_cmd = "systemctl stop dsmhsm"
        
        # Check if any TIVsm packages are installed
        rc, out, err = self.run_cmd(check_cmd, check_rc=False)
        if rc != 0 or not out.strip():
            self.log("No TIVsm packages found on this system. Skipping uninstallation.")
            return False
        
        # Stop daemon (platform-specific)
        self.run_cmd(stop_service_cmd, check_rc=False)
        self.run_cmd("killall dsmhsm", check_rc=False)
        
        # Backup configuration
        os.makedirs(backup_dir, exist_ok=True)
        for f in ["/opt/tivoli/tsm/client/hsm/bin/dsm.opt", "/opt/tivoli/tsm/client/hsm/bin/dsm.sys"]:
            if os.path.exists(f):
                shutil.copy2(f, f"{f}.bk")
        
        # Backup packages (platform-specific)
        if is_aix:
            # AIX: backup all files from extraction directory
            rc, out, err = self.run_cmd(f"find {extract_dest} -type f", check_rc=False)
        else:
            # Linux: backup RPM files
            rc, out, err = self.run_cmd(f"find {extract_dest} -name '*.rpm'", check_rc=False)
        
        if out.strip():
            for pkg_path in out.strip().splitlines():
                self.run_cmd(f"cp {pkg_path} {backup_dir}", check_rc=False)
        
        # Uninstall packages
        successfully_uninstalled = []
        failed_packages = []
        
        for pkg in uninstall_order:
            # Check if package is installed (platform-specific)
            if is_aix:
                check_pkg_cmd = f"lslpp -l {pkg}"
                uninstall_cmd = f"installp -u {pkg}"
            else:
                check_pkg_cmd = f"rpm -q {pkg}"
                uninstall_cmd = f"rpm -e {pkg}"
            
            rc, _, err = self.run_cmd(check_pkg_cmd, check_rc=False)
            if rc != 0:
                continue  # Package not installed, skip
            
            rc, out, err = self.run_cmd(uninstall_cmd, check_rc=False)
            if rc == 0:
                successfully_uninstalled.append(pkg)
            else:
                failed_packages.append((pkg, err))
        
        if failed_packages:
            self.module.fail_json(
                msg=f"Uninstallation failed for packages: {', '.join([p for p, _ in failed_packages])}. "
                    f"Reason(s): {'; '.join([e for _, e in failed_packages])}."
            )
        
        # Cleanup
        shutil.rmtree(backup_dir, ignore_errors=True)
        platform_name = "AIX" if is_aix else "Linux"
        self.module.warn(f"HSM Client successfully uninstalled on {platform_name} with all components removed.")
        return True
    

