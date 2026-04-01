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
    "arm-deployments",
    "env-vars",
    "tokens-credentials",
    "rbac",
    "principals",
    "permissions",
    "privesc",
    "role-trusts",
    "resource-trusts",
    "auth-policies",
    "managed-identities",
    "keyvault",
    "storage",
    "vms",
]

AUTH_POLICY_FINDINGS = {
    "guest-invites:everyone": "auth-policy-guest-invites-everyone",
    "risky-app-consent:enabled": "auth-policy-risky-app-consent-enabled",
    "user-consent:self-service": "auth-policy-user-consent-enabled",
    "users-can-register-apps": "auth-policy-users-can-register-apps",
}


def parse_args() -> argparse.Namespace:
    default_azurefox_dir = Path(
        os.environ.get("AZUREFOX_DIR", str(Path(__file__).resolve().parents[2] / "AzureFox"))
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
        help="Path to the AzureFox checkout. Defaults to AZUREFOX_DIR or a sibling AzureFox checkout.",
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
    try:
        value = run_json(["tofu", "output", "-json", "validation_manifest"], cwd=lab_dir)
    except RuntimeError as exc:
        message = str(exc)
        if 'Output "validation_manifest" not found' in message:
            raise RuntimeError(
                "validation_manifest is not present in the current OpenTofu state. "
                "Run `tofu apply` for this revision of the lab before validating AzureFox."
            ) from exc
        raise

    if not isinstance(value, dict):
        raise RuntimeError("validation_manifest output was not a JSON object")
    return value


def run_azurefox(
    azurefox_dir: Path,
    python_bin: str,
    subscription_id: str,
    artifacts_dir: Path,
    all_checks_sections: list[str],
) -> tuple[dict[str, Any], dict[str, Path], dict[str, Any], dict[str, Path]]:
    outputs: dict[str, Any] = {}
    loot_paths: dict[str, Path] = {}
    run_summaries: dict[str, Any] = {}
    run_summary_paths: dict[str, Path] = {}
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

    for section in all_checks_sections:
        checkpoint_dir = artifacts_dir / f"{section}-checkpoint"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        run_summary = run_json(
            [
                python_bin,
                "-m",
                "azurefox",
                "--subscription",
                subscription_id,
                "--output",
                "json",
                "--outdir",
                str(checkpoint_dir),
                "all-checks",
                "--section",
                section,
            ],
            cwd=azurefox_dir,
            env=env,
        )
        run_summary_path = checkpoint_dir / "run-summary.json"
        if not run_summary_path.exists():
            raise AssertionError(
                f"AzureFox did not emit {section}-checkpoint/run-summary.json"
            )
        (artifacts_dir / f"all-checks-{section}.json").write_text(
            json.dumps(run_summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        run_summaries[section] = run_summary
        run_summary_paths[section] = run_summary_path

    return outputs, loot_paths, run_summaries, run_summary_paths


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def normalize_principal_type(value: str | None) -> str:
    return (value or "").replace("_", "").replace("-", "").lower()


def find_storage_asset(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in payload.get("storage_assets", []):
        if asset.get("name") == name:
            return asset
    raise AssertionError(f"Storage account '{name}' not found in storage output")


def find_key_vault(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for vault in payload.get("key_vaults", []):
        if vault.get("name") == name:
            return vault
    raise AssertionError(f"Key Vault '{name}' not found in keyvault output")


def key_vault_default_action_matches(observed: Any, expected: str, *, public_network_access: Any) -> bool:
    if observed == expected:
        return True
    # Azure omits network ACLs entirely for a fully open vault, which AzureFox surfaces as null/unknown.
    if expected == "Allow" and public_network_access == "Enabled" and observed in {None, "", "unknown"}:
        return True
    return False


def find_identity(payload: dict[str, Any], identity_name: str) -> dict[str, Any]:
    for identity in payload.get("identities", []):
        if identity.get("name") == identity_name:
            return identity
    raise AssertionError(f"Managed identity '{identity_name}' not found in managed-identities output")


def find_principal(payload: dict[str, Any], principal_id: str) -> dict[str, Any]:
    for principal in payload.get("principals", []):
        if principal.get("id") == principal_id:
            return principal
    raise AssertionError(f"Principal '{principal_id}' not found in principals output")


def find_permission(payload: dict[str, Any], principal_id: str) -> dict[str, Any]:
    for permission in payload.get("permissions", []):
        if permission.get("principal_id") == principal_id:
            return permission
    raise AssertionError(f"Principal '{principal_id}' not found in permissions output")


def find_vm(payload: dict[str, Any], vm_name: str) -> dict[str, Any]:
    for asset in payload.get("vm_assets", []):
        if asset.get("name") == vm_name:
            return asset
    raise AssertionError(f"VM asset '{vm_name}' not found in vms output")


def find_trust(
    payload: dict[str, Any],
    trust_type: str,
    *,
    source_object_id: str | None = None,
    target_object_id: str | None = None,
) -> dict[str, Any]:
    for trust in payload.get("trusts", []):
        if trust.get("trust_type") != trust_type:
            continue
        if source_object_id is not None and trust.get("source_object_id") != source_object_id:
            continue
        if target_object_id is not None and trust.get("target_object_id") != target_object_id:
            continue
        return trust
    criteria = {
        "trust_type": trust_type,
        "source_object_id": source_object_id,
        "target_object_id": target_object_id,
    }
    raise AssertionError(f"role-trusts output missing expected trust: {criteria}")


def find_resource_trust(
    payload: dict[str, Any],
    *,
    resource_name: str,
    trust_type: str,
) -> dict[str, Any]:
    for trust in payload.get("resource_trusts", []):
        if trust.get("resource_name") == resource_name and trust.get("trust_type") == trust_type:
            return trust
    raise AssertionError(
        f"resource-trusts output missing trust '{trust_type}' for resource '{resource_name}'"
    )


def find_deployment(
    payload: dict[str, Any],
    *,
    name: str,
    scope_type: str,
) -> dict[str, Any]:
    for deployment in payload.get("deployments", []):
        if deployment.get("name") == name and deployment.get("scope_type") == scope_type:
            return deployment
    raise AssertionError(
        f"arm-deployments output missing deployment '{name}' with scope_type '{scope_type}'"
    )


def find_env_var(
    payload: dict[str, Any],
    *,
    asset_name: str,
    setting_name: str,
) -> dict[str, Any]:
    for env_var in payload.get("env_vars", []):
        if env_var.get("asset_name") == asset_name and env_var.get("setting_name") == setting_name:
            return env_var
    raise AssertionError(
        f"env-vars output missing setting '{setting_name}' for asset '{asset_name}'"
    )


def env_vars_for_asset(payload: dict[str, Any], asset_name: str) -> list[dict[str, Any]]:
    return [item for item in payload.get("env_vars", []) if item.get("asset_name") == asset_name]


def find_surface(
    payload: dict[str, Any],
    *,
    asset_name: str,
    surface_type: str,
) -> dict[str, Any]:
    for surface in payload.get("surfaces", []):
        if surface.get("asset_name") == asset_name and surface.get("surface_type") == surface_type:
            return surface
    raise AssertionError(
        f"tokens-credentials output missing surface '{surface_type}' for asset '{asset_name}'"
    )


def finding_ids(payload: dict[str, Any]) -> list[str]:
    return [finding.get("id", "") for finding in payload.get("findings", []) if finding.get("id")]


def validate_outputs(
    manifest: dict[str, Any],
    outputs: dict[str, Any],
    loot_paths: dict[str, Path],
    run_summaries: dict[str, Any],
    run_summary_paths: dict[str, Path],
) -> tuple[list[str], list[str], list[str]]:
    checks: list[str] = []
    mismatches: list[str] = []
    follow_ups: list[str] = []

    subscription_id = manifest["subscription_id"]
    rg_count = len(manifest["resource_groups"])
    public_storage_name = manifest["storage_accounts"]["public"]["name"]
    private_storage_name = manifest["storage_accounts"]["private"]["name"]
    identity_name = manifest["managed_identity"]["name"]
    identity_principal_id = manifest["managed_identity"]["principal_id"]
    vm_name = manifest["vm"]["name"]
    vmss_name = manifest["vmss"]["name"]
    role_trusts_manifest = manifest["role_trusts"]
    phase2_manifest = manifest["phase2_checkpoint"]

    whoami = outputs["whoami"]
    assert_true(whoami["metadata"]["command"] == "whoami", "whoami metadata.command mismatch")
    assert_true(whoami["subscription"]["id"] == subscription_id, "whoami subscription mismatch")
    checks.append("whoami matched the deployed subscription and returned caller context")

    inventory = outputs["inventory"]
    assert_true(not inventory.get("issues"), "inventory reported collector issues")
    assert_true(
        inventory.get("resource_group_count", 0) >= rg_count,
        f"inventory reported fewer than {rg_count} resource groups",
    )
    resource_types = inventory.get("top_resource_types", {})
    for resource_type in (
        "Microsoft.Compute/virtualMachines",
        "Microsoft.Storage/storageAccounts",
        "Microsoft.Network/networkInterfaces",
        "Microsoft.KeyVault/vaults",
        "Microsoft.Web/sites",
    ):
        assert_true(
            resource_type in resource_types,
            f"inventory missing {resource_type}",
        )
    checks.append("inventory exposed the expected lab resource classes")

    rbac = outputs["rbac"]
    owner_assignments = [
        assignment
        for assignment in rbac.get("role_assignments", [])
        if assignment.get("principal_id") == identity_principal_id
        and assignment.get("role_name") == manifest["role_assignment"]["role_name"]
    ]
    assert_true(owner_assignments, "rbac missing Owner assignment for managed identity principal")
    roletrust_sp_ids = {
        role_trusts_manifest["service_principals"]["api"]["object_id"],
        role_trusts_manifest["service_principals"]["client"]["object_id"],
    }
    reader_ids = {
        assignment.get("principal_id")
        for assignment in rbac.get("role_assignments", [])
        if assignment.get("role_name") == "Reader"
    }
    assert_true(
        roletrust_sp_ids.issubset(reader_ids),
        "rbac missing Reader assignments for role-trusts proof service principals",
    )
    checks.append("rbac exposed both elevated identity and low-impact proof service principals")

    principals = outputs["principals"]
    current_principal = whoami.get("principal", {})
    principal_row = find_principal(principals, current_principal.get("id", ""))
    whoami_type = normalize_principal_type(current_principal.get("principal_type"))
    principals_type = normalize_principal_type(principal_row.get("principal_type"))
    if whoami_type and principals_type and whoami_type != principals_type:
        mismatches.append(
            "Current identity type drift: whoami reports "
            f"{current_principal.get('principal_type')} while principals reports "
            f"{principal_row.get('principal_type')} for object id {current_principal.get('id')}."
        )
        follow_ups.append(
            "Align whoami, principals, and rbac principal typing for the same object id so the "
            "identity checkpoint does not present contradictory actor types."
        )
    for service_principal in role_trusts_manifest["service_principals"].values():
        principal = find_principal(principals, service_principal["object_id"])
        principal_type = normalize_principal_type(principal.get("principal_type"))
        assert_true(
            principal_type == "serviceprincipal",
            f"Principal '{service_principal['display_name']}' did not surface as ServicePrincipal",
        )
    checks.append("principals surfaced the role-trusts proof service principals through RBAC visibility")

    permissions = outputs["permissions"]
    current_permissions = find_permission(permissions, current_principal.get("id", ""))
    assert_true(
        manifest["expected_signals"]["high_privilege_role"] in current_permissions.get("high_impact_roles", []),
        "permissions output missing the expected high-impact role for the current identity",
    )
    for service_principal in role_trusts_manifest["service_principals"].values():
        permission = find_permission(permissions, service_principal["object_id"])
        assert_true(
            permission.get("privileged") is False,
            f"Role-trusts proof service principal '{service_principal['display_name']}' unexpectedly surfaced as privileged",
        )
    checks.append("permissions kept the proof service principals visible without overstating their privilege")

    privesc = outputs["privesc"]
    assert_true(
        any(
            path.get("path_type") == "direct-role-abuse" and path.get("current_identity") is True
            for path in privesc.get("paths", [])
        ),
        "privesc output missing direct-role-abuse path for the current identity",
    )
    assert_true(
        any(
            path.get("path_type") == "public-identity-pivot"
            and path.get("principal_id") == identity_principal_id
            and path.get("asset") == vm_name
            for path in privesc.get("paths", [])
        ),
        "privesc output missing the public managed-identity pivot path",
    )
    checks.append("privesc surfaced both the current privileged identity and the public managed-identity pivot")

    role_trusts = outputs["role-trusts"]
    api_app = role_trusts_manifest["applications"]["api"]
    client_sp = role_trusts_manifest["service_principals"]["client"]
    api_sp = role_trusts_manifest["service_principals"]["api"]

    federated_trust = find_trust(
        role_trusts,
        "federated-credential",
        source_object_id=api_app["object_id"],
        target_object_id=api_sp["object_id"],
    )
    assert_true(
        role_trusts_manifest["federated_credential"]["issuer"] in federated_trust.get("summary", ""),
        "role-trusts federated credential summary is missing the expected issuer",
    )
    assert_true(
        role_trusts_manifest["federated_credential"]["subject"] in federated_trust.get("summary", ""),
        "role-trusts federated credential summary is missing the expected subject",
    )
    find_trust(role_trusts, "app-owner", target_object_id=api_app["object_id"])
    find_trust(role_trusts, "service-principal-owner", target_object_id=api_sp["object_id"])
    find_trust(
        role_trusts,
        "app-to-service-principal",
        source_object_id=client_sp["object_id"],
        target_object_id=api_sp["object_id"],
    )
    present_trust_types = {trust.get("trust_type") for trust in role_trusts.get("trusts", [])}
    missing_types = sorted(set(role_trusts_manifest["expected_trust_types"]) - present_trust_types)
    assert_true(not missing_types, f"role-trusts output missing trust types: {', '.join(missing_types)}")
    if not {"admin-consent", "delegated-consent"} & present_trust_types:
        mismatches.append(
            "role-trusts currently validates ownership, federated identity, and app-role edges, "
            "but no delegated or admin OAuth consent grant surfaced in the lab output."
        )
        follow_ups.append(
            "If consent-grant coverage becomes important before the future Entra graph slice, add a "
            "separate low-risk consent scenario with explicit tenant-permission prerequisites."
        )
    checks.append("role-trusts surfaced owned apps, owned service principals, federation, and app-role trust edges")

    auth_policies = outputs["auth-policies"]
    assert_true(
        manifest["auth_policies"]["validation_mode"] == "non-invasive",
        "auth-policies validation mode drifted from the agreed non-invasive scope",
    )
    policy_rows = auth_policies.get("auth_policies", [])
    authorization_policy = next(
        (policy for policy in policy_rows if policy.get("policy_type") == "authorization-policy"),
        None,
    )
    assert_true(authorization_policy is not None, "auth-policies missing authorization-policy row")
    findings_by_id = {
        finding.get("id"): finding for finding in auth_policies.get("findings", []) if finding.get("id")
    }
    controls = set(authorization_policy.get("controls", []))
    for control, finding_id in AUTH_POLICY_FINDINGS.items():
        if control == "user-consent:self-service" and "risky-app-consent:enabled" in controls:
            continue
        if control in controls:
            assert_true(
                finding_id in findings_by_id,
                f"auth-policies missing finding '{finding_id}' for control '{control}'",
            )
    security_defaults_visible = any(
        policy.get("policy_type") == "security-defaults" for policy in policy_rows
    )
    security_defaults_issue = next(
        (
            issue
            for issue in auth_policies.get("issues", [])
            if (issue.get("context") or {}).get("collector") == "auth_policies.security_defaults"
        ),
        None,
    )
    assert_true(
        security_defaults_visible or security_defaults_issue is not None,
        "auth-policies neither returned security defaults metadata nor recorded the read failure",
    )
    if security_defaults_issue is not None:
        mismatches.append(
            "auth-policies could not fully read security defaults from Graph and recorded "
            f"{security_defaults_issue.get('kind')} for auth_policies.security_defaults."
        )
        follow_ups.append(
            "Keep auth-policies wording evidence-based when security defaults or Conditional Access "
            "surfaces are partially unreadable; partial visibility should remain explicit."
        )
    checks.append("auth-policies stayed in metadata-validation mode and handled partial Graph visibility explicitly")

    managed_identities = outputs["managed-identities"]
    identity = find_identity(managed_identities, identity_name)
    assert_true(
        vm_name in {attached.split("/")[-1] for attached in identity.get("attached_to", [])},
        "managed identity not attached to vm-web-01",
    )
    identity_findings = managed_identities.get("findings", [])
    assert_true(
        any(finding.get("severity") == "high" for finding in identity_findings),
        "managed-identities missing high-severity finding",
    )
    checks.append("managed-identities reported the attached high-impact identity")

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
    checks.append("storage reported the public and private posture split correctly")

    vms = outputs["vms"]
    vm_asset = find_vm(vms, vm_name)
    vmss_asset = find_vm(vms, vmss_name)
    assert_true(bool(vm_asset.get("public_ips")), "public VM is missing public IPs in vms output")
    assert_true(
        identity["id"] in set(vm_asset.get("identity_ids", [])),
        "public VM missing attached user-assigned identity",
    )
    assert_true(vmss_asset.get("vm_type") == "vmss", "vmss-api not reported as vmss")
    vm_findings = vms.get("findings", [])
    assert_true(
        any(finding.get("id", "").startswith("vm-public-identity-") for finding in vm_findings),
        "vms output missing public workload with identity finding",
    )
    checks.append("vms reported the public VM, attached identity, and VM scale set")

    keyvault = outputs["keyvault"]
    for label, expected in phase2_manifest["key_vaults"].items():
        vault = find_key_vault(keyvault, expected["name"])
        assert_true(
            vault.get("public_network_access") == expected["public_network_access"],
            f"Key Vault '{expected['name']}' public network access mismatch",
        )
        assert_true(
            key_vault_default_action_matches(
                vault.get("network_default_action"),
                expected["network_default_action"],
                public_network_access=vault.get("public_network_access"),
            ),
            f"Key Vault '{expected['name']}' network default action mismatch",
        )
        assert_true(
            bool(vault.get("private_endpoint_enabled")) is expected["private_endpoint_enabled"],
            f"Key Vault '{expected['name']}' private endpoint posture mismatch",
        )
        assert_true(
            bool(vault.get("purge_protection_enabled")) is expected["purge_protection_enabled"],
            f"Key Vault '{expected['name']}' purge protection posture mismatch",
        )
        expected_id_prefix = expected["expected_finding_prefix"]
        if expected_id_prefix:
            assert_true(
                any(
                    finding.get("id", "").startswith(expected_id_prefix)
                    and expected["name"] in str(finding.get("description") or "")
                    for finding in keyvault.get("findings", [])
                ),
                f"keyvault output missing finding with prefix '{expected_id_prefix}' for '{expected['name']}'",
            )
    assert_true(
        any(
            finding.get("id", "").startswith("keyvault-purge-protection-disabled-")
            for finding in keyvault.get("findings", [])
        ),
        "keyvault output missing purge-protection-disabled finding",
    )
    checks.append("keyvault surfaced the intended public, hybrid, private, and recovery-control postures")

    resource_trusts = outputs["resource-trusts"]
    for expected in phase2_manifest["resource_trusts"]["expected_rows"]:
        trust = find_resource_trust(
            resource_trusts,
            resource_name=expected["resource_name"],
            trust_type=expected["trust_type"],
        )
        assert_true(
            trust.get("resource_type") == expected["resource_type"],
            f"resource-trusts row type mismatch for {expected['resource_name']}::{expected['trust_type']}",
        )
    resource_trust_finding_ids = finding_ids(resource_trusts)
    assert_true(
        not any(
            finding_id.startswith("keyvault-purge-protection-disabled-")
            for finding_id in resource_trust_finding_ids
        ),
        "resource-trusts unexpectedly emitted the Key Vault purge-protection finding",
    )
    checks.append("resource-trusts stayed on the composed storage plus Key Vault exposure path without purge-protection bleed-through")

    arm_deployments = outputs["arm-deployments"]
    subscription_deployment = phase2_manifest["arm_deployments"]["subscription"]
    resource_group_deployment = phase2_manifest["arm_deployments"]["resource_group"]
    failed_deployment = phase2_manifest["arm_deployments"]["failed"]

    subscription_row = find_deployment(
        arm_deployments,
        name=subscription_deployment["name"],
        scope_type=subscription_deployment["scope_type"],
    )
    assert_true(
        subscription_row.get("outputs_count") == subscription_deployment["outputs_count"],
        "subscription deployment outputs_count mismatch",
    )
    assert_true(
        subscription_row.get("template_link") == subscription_deployment["template_link"],
        "subscription deployment template_link mismatch",
    )

    resource_group_row = find_deployment(
        arm_deployments,
        name=resource_group_deployment["name"],
        scope_type=resource_group_deployment["scope_type"],
    )
    assert_true(
        resource_group_row.get("resource_group") == resource_group_deployment["resource_group"],
        "resource-group deployment resource_group mismatch",
    )
    assert_true(
        resource_group_row.get("outputs_count") == resource_group_deployment["outputs_count"],
        "resource-group deployment outputs_count mismatch",
    )
    assert_true(
        resource_group_row.get("parameters_link") == resource_group_deployment["parameters_link"],
        "resource-group deployment parameters_link mismatch",
    )

    failed_row = find_deployment(
        arm_deployments,
        name=failed_deployment["name"],
        scope_type=failed_deployment["scope_type"],
    )
    assert_true(
        failed_row.get("resource_group") == failed_deployment["resource_group"],
        "failed deployment resource_group mismatch",
    )
    assert_true(
        failed_row.get("provisioning_state") == failed_deployment["provisioning_state"],
        "failed deployment provisioning_state mismatch",
    )
    assert_true(
        failed_row.get("outputs_count") == failed_deployment["outputs_count"],
        "failed deployment outputs_count mismatch",
    )
    checks.append("arm-deployments surfaced the intended subscription, resource-group, and failed history proofs")

    env_vars = outputs["env-vars"]
    plain_text_setting = phase2_manifest["env_vars"]["plain_text_sensitive"]
    plain_text_row = find_env_var(
        env_vars,
        asset_name=plain_text_setting["asset_name"],
        setting_name=plain_text_setting["setting_name"],
    )
    assert_true(
        plain_text_row.get("value_type") == "plain-text" and plain_text_row.get("looks_sensitive") is True,
        "plain-text sensitive app setting did not surface as expected",
    )

    keyvault_ref_setting = phase2_manifest["env_vars"]["keyvault_reference"]
    keyvault_ref_row = find_env_var(
        env_vars,
        asset_name=keyvault_ref_setting["asset_name"],
        setting_name=keyvault_ref_setting["setting_name"],
    )
    assert_true(
        keyvault_ref_row.get("value_type") == "keyvault-ref",
        "Key Vault-backed app setting did not surface as keyvault-ref",
    )
    assert_true(
        keyvault_ref_row.get("reference_target") == keyvault_ref_setting["reference_target"],
        "Key Vault-backed app setting reference_target mismatch",
    )
    expected_kv_identity = keyvault_ref_setting.get("key_vault_reference_identity")
    if expected_kv_identity:
        assert_true(
            keyvault_ref_row.get("key_vault_reference_identity") == expected_kv_identity,
            "Key Vault-backed app setting key_vault_reference_identity mismatch",
        )

    function_workload = phase2_manifest["env_vars"]["function_workload"]
    function_rows = env_vars_for_asset(env_vars, function_workload["asset_name"])
    assert_true(function_rows, "function workload produced no env-vars rows")
    function_identity_types = {
        normalize_principal_type(row.get("workload_identity_type")) for row in function_rows
    }
    assert_true(
        any("systemassigned" in value and "userassigned" in value for value in function_identity_types),
        "function workload did not surface both system-assigned and user-assigned identity context",
    )

    empty_workload = phase2_manifest["env_vars"]["empty_identity_workload"]
    assert_true(
        not env_vars_for_asset(env_vars, empty_workload["asset_name"]),
        "empty identity-bearing workload unexpectedly surfaced env-vars rows",
    )
    checks.append("env-vars surfaced plain-text, Key Vault-backed, mixed-identity, and empty-settings workload evidence correctly")

    tokens_credentials = outputs["tokens-credentials"]
    surfaces = tokens_credentials.get("surfaces", [])
    surface_types = {surface.get("surface_type") for surface in surfaces}
    expected_surface_types = set(phase2_manifest["tokens_credentials"]["expected_surface_types"])
    assert_true(
        expected_surface_types.issubset(surface_types),
        "tokens-credentials output missing one or more expected surface families",
    )
    empty_surface = find_surface(
        tokens_credentials,
        asset_name=empty_workload["asset_name"],
        surface_type="managed-identity-token",
    )
    assert_true(
        empty_surface.get("access_path") == "workload-identity",
        "empty identity-bearing web workload did not surface through workload-identity access path",
    )
    token_finding_ids = finding_ids(tokens_credentials)
    assert_true(
        len(token_finding_ids) == len(set(token_finding_ids)),
        "tokens-credentials finding IDs were not unique per surfaced item",
    )
    checks.append("tokens-credentials correlated app settings, deployment history, VM IMDS, and empty-settings web workloads without duplicate finding IDs")

    for command in COMMANDS:
        payload_command = outputs[command]["metadata"]["command"]
        assert_true(payload_command == command, f"{command} metadata.command mismatch")
        assert_true(loot_paths.get(command, Path()).exists(), f"{command} loot artifact missing")
    checks.append("all single-command runs returned JSON payloads and emitted loot artifacts")

    for section, expected_commands in manifest["all_checks_sections"].items():
        run_summary = run_summaries[section]
        run_summary_path = run_summary_paths[section]
        assert_true(run_summary["metadata"]["command"] == "all-checks", f"{section} run-summary command mismatch")
        assert_true(run_summary.get("section") == section, f"{section} run-summary section mismatch")
        result_map = {item.get("command"): item for item in run_summary.get("results", [])}
        assert_true(
            set(expected_commands).issubset(result_map),
            f"{section} run-summary missing expected commands",
        )
        for command in expected_commands:
            result = result_map[command]
            assert_true(result.get("status") == "ok", f"{section} run-summary reported non-ok status for {command}")
            artifact_paths = result.get("artifact_paths") or {}
            for label, path in artifact_paths.items():
                assert_true(
                    path and Path(path).exists(),
                    f"{section} run-summary missing {label} artifact for {command}",
                )
        assert_true(run_summary_path.exists(), f"{section} run-summary.json path is missing on disk")
    checks.append("all-checks emitted complete artifact sets for identity, config, secrets, and resource sections")

    return checks, mismatches, follow_ups


def write_summary(
    artifacts_dir: Path,
    checks: list[str],
    mismatches: list[str],
    follow_ups: list[str],
    run_summary_paths: dict[str, Path],
) -> None:
    summary = {
        "checks": checks,
        "follow_ups": follow_ups,
        "mismatches": mismatches,
        "run_summary_paths": {
            section: str(path) for section, path in sorted(run_summary_paths.items())
        },
        "status": "pass",
    }
    (artifacts_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = ["AzureFox lab validation passed.", ""]
    lines.append("Checks:")
    lines.extend(f"- {check}" for check in checks)
    lines.append("")
    lines.append("Mismatch report:")
    if mismatches:
        lines.extend(f"- {item}" for item in mismatches)
    else:
        lines.append("- No AzureFox-to-lab mismatches were observed in this run.")
    lines.append("")
    lines.append("Follow-up items:")
    if follow_ups:
        lines.extend(f"- {item}" for item in follow_ups)
    else:
        lines.append("- No follow-up items were generated in this run.")
    (artifacts_dir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    mismatch_lines = [
        "# AzureFox Lab Mismatch Report",
        "",
        "This report compares AzureFox output to the deployed lab's observable behavior.",
        "",
    ]
    if mismatches:
        mismatch_lines.extend(f"- {item}" for item in mismatches)
    else:
        mismatch_lines.append("- No AzureFox-to-lab mismatches were observed in this run.")
    mismatch_report = "\n".join(mismatch_lines) + "\n"
    (artifacts_dir / "azurefox-mismatch-report.md").write_text(
        mismatch_report,
        encoding="utf-8",
    )
    (artifacts_dir / "identity-mismatch-report.md").write_text(
        mismatch_report,
        encoding="utf-8",
    )

    follow_up_lines = [
        "# AzureFox Follow-Up Items",
        "",
        "These items came from the lab validation pass and should stay evidence-based.",
        "",
    ]
    if follow_ups:
        follow_up_lines.extend(f"- {item}" for item in follow_ups)
    else:
        follow_up_lines.append("- No follow-up items were generated in this run.")
    (artifacts_dir / "azurefox-follow-up-items.md").write_text(
        "\n".join(follow_up_lines) + "\n",
        encoding="utf-8",
    )


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
    all_checks_sections = list(manifest["all_checks_sections"].keys())
    outputs, loot_paths, run_summaries, run_summary_paths = run_azurefox(
        azurefox_dir=azurefox_dir,
        python_bin=args.python,
        subscription_id=manifest["subscription_id"],
        artifacts_dir=artifacts_dir,
        all_checks_sections=all_checks_sections,
    )
    checks, mismatches, follow_ups = validate_outputs(
        manifest,
        outputs,
        loot_paths,
        run_summaries,
        run_summary_paths,
    )
    write_summary(artifacts_dir, checks, mismatches, follow_ups, run_summary_paths)
    print(f"Validation complete. Artifacts written to {artifacts_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        raise
