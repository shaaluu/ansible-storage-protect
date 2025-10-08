# module_utils/ba_client.py
import platform
import subprocess
import shutil
import re
from .ba_client_pkg import detect_pkg_type, list_installed_linux

def run_command(cmd, check=True):
    """Run a command (shell) and return (rc, stdout, stderr)."""
    try:
        res = subprocess.run(cmd, shell=True, check=check,
                             capture_output=True, text=True)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr

def get_os_family():
    if platform.system().lower().startswith("win"):
        return "windows"
    return "linux"

# ------------------------
# Version / Installed Check
# ------------------------
def get_ba_client_version_linux():
    """Return version string if installed on Linux, else None."""
    # Use package query or fallback to `dsmc q sess`
    # Try package query first
    for pkg in ["TIVsm-BA", "ba_client", "dsmba"]:  # possible names
        ver = list_installed_linux(pkg)
        if ver:
            return ver
    # fallback: `dsmc q sess`
    rc, out, err = run_command("dsmc q sess", check=False)
    if rc == 0:
        # parse version in output
        m = re.search(r"Version\s+(\d+),\s+Release\s+(\d+),\s+Level\s+([\d.]+)", out)
        if m:
            return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return None

def get_ba_client_version_windows():
    """Return version if installed on Windows, else None."""
    dsmc = shutil.which("dsmc.exe")
    if not dsmc:
        return None
    rc, out, err = run_command(f'"{dsmc}" q sess', check=False)
    if rc != 0:
        return None
    m = re.search(r"Version\s+(\d+),\s+Release\s+(\d+),\s+Level\s+([\d.]+)", out)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return None

# ------------------------
# Actions: install / upgrade / patch / uninstall
# ------------------------
def install_linux(installer_path):
    pkg_type = detect_pkg_type()
    if pkg_type == "rpm":
        return run_command(f"rpm -Uvh {installer_path}")
    elif pkg_type == "deb":
        return run_command(f"dpkg -i {installer_path}")
    else:
        return 1, "", "Unsupported Linux package system"

def install_windows(installer_path, silent_opts="/qn /norestart"):
    if installer_path.lower().endswith(".msi"):
        return run_command(f'msiexec /i "{installer_path}" {silent_opts}')
    else:
        return 1, "", "Unsupported Windows installer type"

def upgrade_linux(installer_path):
    # rpm -U or dpkg -i also works
    return install_linux(installer_path)

def upgrade_windows(installer_path, silent_opts="/qn /norestart"):
    return install_windows(installer_path, silent_opts)

def patch_linux(patch_path):
    return install_linux(patch_path)

def patch_windows(patch_path, silent_opts="/qn /norestart"):
    return install_windows(patch_path, silent_opts)

def uninstall_linux(pkg_name=None):
    # If pkg_name given, try remove that; else attempt generic names
    names = [pkg_name] if pkg_name else ["TIVsm-BA", "ba_client"]
    # Try rpm first
    for name in names:
        if name:
            rc, out, err = run_command(f"rpm -e {name}", check=False)
            if rc == 0:
                return rc, out, err
            # try dpkg
            rc2, out2, err2 = run_command(f"dpkg -r {name}", check=False)
            if rc2 == 0:
                return rc2, out2, err2
    return 1, "", "Failed to uninstall: package not found"

def uninstall_windows(product_code=None):
    if product_code:
        return run_command(f'msiexec /x {product_code} /qn /norestart')
    # fallback via wmic
    return run_command('wmic product where "name like \'%Tivoli Storage Manager%\'" call uninstall')
