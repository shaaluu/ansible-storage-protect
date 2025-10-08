#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ..module_utils.ba_client import (
    get_os_family,
    get_ba_client_version_linux, get_ba_client_version_windows,
    install_linux, install_windows,
    upgrade_linux, upgrade_windows,
    patch_linux, patch_windows,
    uninstall_linux, uninstall_windows
)

def run_module():
    module_args = dict(
        installer_path=dict(type="str", required=False),
        state=dict(type="str",
                   choices=["present", "absent", "upgrade", "patch"],
                   default="present"),
        product_code=dict(type="str", required=False),
        pkg_name=dict(type="str", required=False)
    )

    result = dict(
        changed=False,
        msg="",
        rc=0, stdout="", stderr=""
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    installer_path = module.params.get("installer_path")
    state = module.params["state"]
    product_code = module.params.get("product_code")
    pkg_name = module.params.get("pkg_name")

    os_family = get_os_family()

    if os_family == "linux":
        version = get_ba_client_version_linux()
    else:
        version = get_ba_client_version_windows()

    # Handle states
    if state == "present":
        if version:
            result["msg"] = f"BA Client already installed (version {version})"
        else:
            if module.check_mode:
                result["changed"] = True
                result["msg"] = "BA Client would be installed"
            else:
                if os_family == "linux":
                    rc, out, err = install_linux(installer_path)
                else:
                    rc, out, err = install_windows(installer_path)
                result.update(rc=rc, stdout=out, stderr=err)
                if rc == 0:
                    result["changed"] = True
                    result["msg"] = "BA Client installed successfully"
                else:
                    module.fail_json(msg="Installation failed", **result)

    elif state == "upgrade":
        if not version:
            module.fail_json(msg="Nothing to upgrade; BA Client not installed", **result)
        if module.check_mode:
            result["changed"] = True
            result["msg"] = "BA Client would be upgraded"
        else:
            if os_family == "linux":
                rc, out, err = upgrade_linux(installer_path)
            else:
                rc, out, err = upgrade_windows(installer_path)
            result.update(rc=rc, stdout=out, stderr=err)
            if rc == 0:
                result["changed"] = True
                result["msg"] = "BA Client upgraded successfully"
            else:
                module.fail_json(msg="Upgrade failed", **result)

    elif state == "patch":
        if not version:
            module.fail_json(msg="Cannot patch; BA Client not installed", **result)
        if module.check_mode:
            result["changed"] = True
            result["msg"] = "BA Client patch would be applied"
        else:
            if os_family == "linux":
                rc, out, err = patch_linux(installer_path)
            else:
                rc, out, err = patch_windows(installer_path)
            result.update(rc=rc, stdout=out, stderr=err)
            if rc == 0:
                result["changed"] = True
                result["msg"] = "Patch applied successfully"
            else:
                module.fail_json(msg="Patch failed", **result)

    elif state == "absent":
        if not version:
            result["msg"] = "BA Client already absent"
        else:
            if module.check_mode:
                result["changed"] = True
                result["msg"] = "BA Client would be uninstalled"
            else:
                if os_family == "linux":
                    rc, out, err = uninstall_linux(pkg_name)
                else:
                    rc, out, err = uninstall_windows(product_code)
                result.update(rc=rc, stdout=out, stderr=err)
                if rc == 0:
                    result["changed"] = True
                    result["msg"] = "Uninstalled successfully"
                else:
                    module.fail_json(msg="Uninstall failed", **result)

    module.exit_json(**result)


def main():
    run_module()

if __name__ == "__main__":
    main()
