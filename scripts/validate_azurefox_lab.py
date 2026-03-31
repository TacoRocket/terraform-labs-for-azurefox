#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


COMMANDS = [
    "whoami",
    "inventory",
    "rbac",
    "managed-identities",
    "storage",
    "vms",
]


def parse_args() -> argparse.Namespace:
    default_azurefox_dir = Path(
        os.environ.get("AZUREFOX_DIR", str(Path(__file__).resolve().parents[2] / "CodexPlus"))
    )
    parser = argparse.ArgumentParser(
        description="Run AzureFox against the deployed OpenTofu lab and validate expected signals."
    )
    parser.add_argument(
        "--lab-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to the OpenTofu lab root.",
    )
    parser.add_argument(
        "--azurefox-dir",
        type=Path,
        default=default_azurefox_dir,
        help="Path to the AzureFox checkout. Defaults to AZUREFOX_DIR or a sibling CodexPlus checkout.",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Directory where AzureFox outputs and summaries will be written.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter to use for AzureFox execution.",
    )
    return parser.parse_args()


def run_json(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> Any:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Command did not return JSON: {' '.join(cmd)}\nSTDOUT:\n{completed.stdout}"
        ) from exc


def read_manifest(lab_dir: Path) -> dict[str, Any]:
    value = run_json(["tofu", "output", "-json", "validation_manifest"], cwd=lab_dir)
    if not isinstance(value, dict):
        raise RuntimeError("validation_manifest output was not a JSON object")
    return value


def run_azurefox(
    azurefox_dir: Path,
    python_bin: str,
    subscription_id: str,
    artifacts_dir: Path,
) -> tuple[dict[str, Any], dict[str, Path]]:
    outputs: dict[str, Any] = {}
    loot_paths: dict[str, Path] = {}
    env = os.environ.copy()
    pythonpath = str(azurefox_dir / "src")
    env["PYTHONPATH"] = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else pythonpath

    loot_root = artifacts_dir / "loot"
    loot_root.mkdir(parents=True, exist_ok=True)

    for command in COMMANDS:
        outdir = artifacts_dir / command
        outdir.mkdir(parents=True, exist_ok=True)
        payload = run_json(
            [
                python_bin,
                "-m",
                "azurefox",
                "--subscription",
                subscription_id,
                "--output",
                "json",
                "--outdir",
                str(outdir),
                command,
            ],
            cwd=azurefox_dir,
            env=env,
        )
        outputs[command] = payload
        (artifacts_dir / f"{command}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        emitted_loot = outdir / "loot" / f"{command}.json"
        if not emitted_loot.exists():
            raise AssertionError(f"AzureFox did not emit loot/{command}.json")
        target = loot_root / f"{command}.json"
        target.write_text(emitted_loot.read_text(encoding="utf-8"), encoding="utf-8")
        loot_paths[command] = target

    return outputs, loot_paths


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def find_storage_asset(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in payload.get("storage_assets", []):
        if asset.get("name") == name:
            return asset
    raise AssertionError(f"Storage account '{name}' not found in storage output")


def find_identity(payload: dict[str, Any], identity_name: str) -> dict[str, Any]:
    for identity in payload.get("identities", []):
        if identity.get("name") == identity_name:
            return identity
    raise AssertionError(f"Managed identity '{identity_name}' not found in managed-identities output")


def find_vm(payload: dict[str, Any], vm_name: str) -> dict[str, Any]:
    for asset in payload.get("vm_assets", []):
        if asset.get("name") == vm_name:
            return asset
    raise AssertionError(f"VM asset '{vm_name}' not found in vms output")


def validate_outputs(
    manifest: dict[str, Any],
    outputs: dict[str, Any],
    loot_paths: dict[str, Path],
) -> list[str]:
    checks: list[str] = []
    subscription_id = manifest["subscription_id"]
    rg_count = len(manifest["resource_groups"])
    public_storage_name = manifest["storage_accounts"]["public"]["name"]
    private_storage_name = manifest["storage_accounts"]["private"]["name"]
    identity_name = manifest["managed_identity"]["name"]
    identity_principal_id = manifest["managed_identity"]["principal_id"]
    vm_name = manifest["vm"]["name"]
    vmss_name = manifest["vmss"]["name"]

    whoami = outputs["whoami"]
    assert_true(whoami["metadata"]["command"] == "whoami", "whoami metadata.command mismatch")
    assert_true(whoami["subscription"]["id"] == subscription_id, "whoami subscription mismatch")
    checks.append("whoami matched deployed subscription")

    inventory = outputs["inventory"]
    assert_true(not inventory.get("issues"), "inventory reported collector issues")
    assert_true(
        inventory.get("resource_group_count", 0) >= rg_count,
        f"inventory reported fewer than {rg_count} resource groups",
    )
    resource_types = inventory.get("top_resource_types", {})
    assert_true(
        "Microsoft.Compute/virtualMachines" in resource_types,
        "inventory missing Microsoft.Compute/virtualMachines",
    )
    assert_true(
        "Microsoft.Storage/storageAccounts" in resource_types,
        "inventory missing Microsoft.Storage/storageAccounts",
    )
    assert_true(
        "Microsoft.Network/networkInterfaces" in resource_types,
        "inventory missing Microsoft.Network/networkInterfaces",
    )
    checks.append("inventory exposed expected resource classes")

    rbac = outputs["rbac"]
    owner_assignments = [
        assignment
        for assignment in rbac.get("role_assignments", [])
        if assignment.get("principal_id") == identity_principal_id
        and assignment.get("role_name") == manifest["role_assignment"]["role_name"]
    ]
    assert_true(owner_assignments, "rbac missing Owner assignment for managed identity principal")
    checks.append("rbac reported elevated role assignment")

    managed_identities = outputs["managed-identities"]
    identity = find_identity(managed_identities, identity_name)
    assert_true(vm_name in {attached.split("/")[-1] for attached in identity.get("attached_to", [])}, "managed identity not attached to vm-web-01")
    identity_findings = managed_identities.get("findings", [])
    assert_true(
        any(finding.get("severity") == "high" for finding in identity_findings),
        "managed-identities missing high-severity finding",
    )
    checks.append("managed-identities reported attachment and high-severity finding")

    storage = outputs["storage"]
    public_asset = find_storage_asset(storage, public_storage_name)
    private_asset = find_storage_asset(storage, private_storage_name)
    assert_true(public_asset.get("public_access") is True, "public storage account is not marked public")
    assert_true(
        public_asset.get("network_default_action") == manifest["expected_signals"]["public_storage_default_action"],
        "public storage default action mismatch",
    )
    assert_true(private_asset.get("public_access") is False, "private storage account unexpectedly public")
    assert_true(
        private_asset.get("network_default_action") == manifest["expected_signals"]["private_storage_default_action"],
        "private storage default action mismatch",
    )
    assert_true(
        bool(private_asset.get("private_endpoint_enabled")) is manifest["expected_signals"]["private_endpoint_enabled"],
        "private storage account missing private endpoint signal",
    )
    storage_findings = storage.get("findings", [])
    assert_true(
        any(finding.get("id", "").startswith("storage-public-") for finding in storage_findings),
        "storage output missing public access finding",
    )
    assert_true(
        any(finding.get("id", "").startswith("storage-firewall-open-") for finding in storage_findings),
        "storage output missing firewall-open finding",
    )
    checks.append("storage reported public and private posture correctly")

    vms = outputs["vms"]
    vm_asset = find_vm(vms, vm_name)
    vmss_asset = find_vm(vms, vmss_name)
    assert_true(bool(vm_asset.get("public_ips")), "public VM is missing public IPs in vms output")
    assert_true(identity["id"] in set(vm_asset.get("identity_ids", [])), "public VM missing attached user-assigned identity")
    assert_true(vmss_asset.get("vm_type") == "vmss", "vmss-api not reported as vmss")
    vm_findings = vms.get("findings", [])
    assert_true(
        any(finding.get("id", "").startswith("vm-public-identity-") for finding in vm_findings),
        "vms output missing public workload with identity finding",
    )
    checks.append("vms reported public VM, identity, and VMSS")

    for command in COMMANDS:
        payload_command = outputs[command]["metadata"]["command"]
        assert_true(payload_command == command, f"{command} metadata.command mismatch")
        assert_true(loot_paths.get(command, Path()).exists(), f"{command} loot artifact missing")
    checks.append("all commands returned JSON payloads and emitted loot artifacts")

    return checks


def write_summary(artifacts_dir: Path, checks: list[str]) -> None:
    summary = {
        "status": "pass",
        "checks": checks,
    }
    (artifacts_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = ["AzureFox lab validation passed.", ""]
    lines.extend(f"- {check}" for check in checks)
    (artifacts_dir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    lab_dir = args.lab_dir.resolve()
    azurefox_dir = args.azurefox_dir.resolve()
    artifacts_dir = (
        args.artifacts_dir.resolve()
        if args.artifacts_dir is not None
        else (lab_dir / "proof-artifacts" / "latest").resolve()
    )
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    manifest = read_manifest(lab_dir)
    outputs, loot_paths = run_azurefox(
        azurefox_dir=azurefox_dir,
        python_bin=args.python,
        subscription_id=manifest["subscription_id"],
        artifacts_dir=artifacts_dir,
    )
    checks = validate_outputs(manifest, outputs, loot_paths)
    write_summary(artifacts_dir, checks)
    print(f"Validation complete. Artifacts written to {artifacts_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        raise
