#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
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
    "resource-trusts",
    "auth-policies",
    "managed-identities",
    "keyvault",
    "storage",
    "vms",
    "nics",
    "dns",
    "endpoints",
    "network-ports",
    "workloads",
    "app-services",
    "functions",
    "api-mgmt",
    "aks",
    "acr",
    "databases",
    "role-trusts",
]

ALL_CHECK_SECTION_ORDER = [
    "config",
    "secrets",
    "resource",
    "network",
    "compute",
    "identity",
]

AUTH_POLICY_FINDINGS = {
    "guest-invites:everyone": "auth-policy-guest-invites-everyone",
    "risky-app-consent:enabled": "auth-policy-risky-app-consent-enabled",
    "user-consent:self-service": "auth-policy-user-consent-enabled",
    "users-can-register-apps": "auth-policy-users-can-register-apps",
}

RUN_MODE_CHOICES = ("full", "commands-only", "all-checks-only")


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
    parser.add_argument(
        "--mode",
        choices=RUN_MODE_CHOICES,
        default="full",
        help=(
            "Validation scope to run: full executes both standalone commands and all-checks; "
            "commands-only skips all-checks; all-checks-only skips standalone commands."
        ),
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


def log_progress(message: str) -> None:
    print(message, flush=True)


def ordered_all_checks_sections(sections: list[str]) -> list[str]:
    preferred_positions = {
        section: index for index, section in enumerate(ALL_CHECK_SECTION_ORDER)
    }
    return sorted(
        sections,
        key=lambda section: (
            preferred_positions.get(section, len(ALL_CHECK_SECTION_ORDER)),
            section,
        ),
    )


def mode_runs_commands(mode: str) -> bool:
    return mode in {"full", "commands-only"}


def mode_runs_all_checks(mode: str) -> bool:
    return mode in {"full", "all-checks-only"}


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
    mode: str,
    all_checks_sections: list[str],
) -> tuple[dict[str, Any], dict[str, Path], dict[str, Any], dict[str, Path]]:
    outputs: dict[str, Any] = {}
    loot_paths: dict[str, Path] = {}
    run_summaries: dict[str, Any] = {}
    run_summary_paths: dict[str, Path] = {}
    env = os.environ.copy()
    pythonpath = str(azurefox_dir / "src")
    env["PYTHONPATH"] = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else pythonpath

    if mode_runs_commands(mode):
        loot_root = artifacts_dir / "loot"
        loot_root.mkdir(parents=True, exist_ok=True)
        command_total = len(COMMANDS)
        for index, command in enumerate(COMMANDS, start=1):
            step_started = time.monotonic()
            outdir = artifacts_dir / command
            outdir.mkdir(parents=True, exist_ok=True)
            log_progress(
                f"[run {index}/{command_total}] azurefox {command} -> {outdir}"
            )
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
            log_progress(
                f"[done {index}/{command_total}] azurefox {command} "
                f"({time.monotonic() - step_started:.1f}s)"
            )

    if mode_runs_all_checks(mode):
        section_total = len(all_checks_sections)
        for index, section in enumerate(all_checks_sections, start=1):
            step_started = time.monotonic()
            checkpoint_dir = artifacts_dir / f"{section}-checkpoint"
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            log_progress(
                f"[run {index}/{section_total}] azurefox all-checks --section {section} "
                f"-> {checkpoint_dir}"
            )
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
            log_progress(
                f"[done {index}/{section_total}] azurefox all-checks --section {section} "
                f"({time.monotonic() - step_started:.1f}s)"
            )

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


def find_nic(payload: dict[str, Any], nic_name: str) -> dict[str, Any]:
    for asset in payload.get("nic_assets", []):
        if asset.get("name") == nic_name:
            return asset
    raise AssertionError(f"NIC asset '{nic_name}' not found in nics output")


def find_endpoint(
    payload: dict[str, Any],
    *,
    endpoint: str,
    source_asset_name: str,
) -> dict[str, Any]:
    for row in payload.get("endpoints", []):
        if row.get("endpoint") == endpoint and row.get("source_asset_name") == source_asset_name:
            return row
    raise AssertionError(
        f"endpoints output missing endpoint '{endpoint}' for asset '{source_asset_name}'"
    )


def find_network_port(
    payload: dict[str, Any],
    *,
    asset_name: str,
    endpoint: str,
    port: str,
    protocol: str,
) -> dict[str, Any]:
    for row in payload.get("network_ports", []):
        if (
            row.get("asset_name") == asset_name
            and row.get("endpoint") == endpoint
            and str(row.get("port")) == port
            and str(row.get("protocol")).upper() == protocol.upper()
        ):
            return row
    raise AssertionError(
        f"network-ports output missing {protocol} {port} for asset '{asset_name}' on endpoint '{endpoint}'"
    )


def find_workload(payload: dict[str, Any], asset_name: str) -> dict[str, Any]:
    for workload in payload.get("workloads", []):
        if workload.get("asset_name") == asset_name:
            return workload
    raise AssertionError(f"workloads output missing asset '{asset_name}'")


def find_app_service(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in payload.get("app_services", []):
        if asset.get("name") == name:
            return asset
    raise AssertionError(f"app-services output missing asset '{name}'")


def find_function_app(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in payload.get("function_apps", []):
        if asset.get("name") == name:
            return asset
    raise AssertionError(f"functions output missing asset '{name}'")


def find_api_management_service(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in payload.get("api_management_services", []):
        if asset.get("name") == name:
            return asset
    raise AssertionError(f"api-mgmt output missing service '{name}'")


def find_aks_cluster(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in payload.get("aks_clusters", []):
        if asset.get("name") == name:
            return asset
    raise AssertionError(f"aks output missing cluster '{name}'")


def find_registry(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in payload.get("registries", []):
        if asset.get("name") == name:
            return asset
    raise AssertionError(f"acr output missing registry '{name}'")


def find_database_server(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in payload.get("database_servers", []):
        if asset.get("name") == name:
            return asset
    raise AssertionError(f"databases output missing server '{name}'")


def find_dns_zone(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in payload.get("dns_zones", []):
        if asset.get("name") == name:
            return asset
    raise AssertionError(f"dns output missing zone '{name}'")


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
    mode: str,
    outputs: dict[str, Any],
    loot_paths: dict[str, Path],
    run_summaries: dict[str, Any],
    run_summary_paths: dict[str, Path],
) -> tuple[list[str], list[str], list[str]]:
    checks: list[str] = []
    mismatches: list[str] = []
    follow_ups: list[str] = []

    if mode_runs_commands(mode):
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
        phase3_manifest = manifest["phase3_checkpoint"]

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
        assert_true(
            inventory.get("resource_count", 0) >= rg_count,
            "inventory reported an unexpectedly low resource_count",
        )
        resource_types = inventory.get("top_resource_types", {})
        assert_true(
            isinstance(resource_types, dict) and resource_types,
            "inventory did not return a usable top_resource_types summary",
        )
        checks.append("inventory exposed healthy counts and a usable capped resource-type summary")

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

        nics = outputs["nics"]
        vm_primary_nic = phase3_manifest["nics"]["vm_primary"]
        nic_asset = find_nic(nics, vm_primary_nic["name"])
        assert_true(
            nic_asset.get("attached_asset_name") == vm_primary_nic["attached_asset_name"],
            "nics output missing the expected VM attachment on the primary NIC",
        )
        assert_true(
            vm_primary_nic["public_ip_id"] in set(nic_asset.get("public_ip_ids", [])),
            "nics output missing the public IP reference on the primary NIC",
        )
        assert_true(
            vm_primary_nic["subnet_id"] in set(nic_asset.get("subnet_ids", [])),
            "nics output missing the workload subnet reference on the primary NIC",
        )
        assert_true(
            vm_primary_nic["vnet_id"] in set(nic_asset.get("vnet_ids", [])),
            "nics output missing the workload VNet reference on the primary NIC",
        )
        checks.append("nics exposed the primary VM NIC attachment, public IP reference, and network placement")

        endpoints = outputs["endpoints"]
        public_vm_endpoint = phase3_manifest["endpoints"]["public_vm"]
        public_vm_row = find_endpoint(
            endpoints,
            endpoint=public_vm_endpoint["endpoint"],
            source_asset_name=public_vm_endpoint["source_asset_name"],
        )
        assert_true(
            public_vm_row.get("endpoint_type") == "ip",
            "endpoints output did not classify the VM endpoint as an IP",
        )
        assert_true(
            public_vm_row.get("exposure_family") == public_vm_endpoint["exposure_family"],
            "endpoints output public VM exposure family mismatch",
        )
        assert_true(
            public_vm_row.get("ingress_path") == public_vm_endpoint["ingress_path"],
            "endpoints output public VM ingress path mismatch",
        )
        assert_true(
            public_vm_row.get("source_asset_kind") == public_vm_endpoint["source_asset_kind"],
            "endpoints output public VM source asset kind mismatch",
        )
        for expected in phase3_manifest["endpoints"]["app_services"]:
            row = find_endpoint(
                endpoints,
                endpoint=expected["endpoint"],
                source_asset_name=expected["source_asset_name"],
            )
            assert_true(
                row.get("endpoint_type") == "hostname",
                f"endpoints output did not classify '{expected['source_asset_name']}' as a hostname surface",
            )
            assert_true(
                row.get("exposure_family") == "managed-web-hostname",
                f"endpoints output exposure family drifted for '{expected['source_asset_name']}'",
            )
            assert_true(
                row.get("ingress_path") == expected["ingress_path"],
                f"endpoints output ingress path drifted for '{expected['source_asset_name']}'",
            )
            assert_true(
                row.get("source_asset_kind") == expected["source_asset_kind"],
                f"endpoints output source asset kind drifted for '{expected['source_asset_name']}'",
            )
        expected_function_endpoint = phase3_manifest["endpoints"]["function"]
        function_endpoint_row = find_endpoint(
            endpoints,
            endpoint=expected_function_endpoint["endpoint"],
            source_asset_name=expected_function_endpoint["source_asset_name"],
        )
        assert_true(
            function_endpoint_row.get("endpoint_type") == "hostname",
            "endpoints output did not classify the Function App hostname as a hostname surface",
        )
        assert_true(
            function_endpoint_row.get("exposure_family") == "managed-web-hostname",
            "endpoints output Function App exposure family drifted",
        )
        assert_true(
            function_endpoint_row.get("ingress_path") == expected_function_endpoint["ingress_path"],
            "endpoints output Function App ingress path drifted",
        )
        checks.append("endpoints surfaced the public VM IP and Azure-managed web hostnames without overstating reachability")

        network_ports = outputs["network-ports"]
        expected_ssh = phase3_manifest["network_ports"]["ssh"]
        ssh_row = find_network_port(
            network_ports,
            asset_name=expected_ssh["asset_name"],
            endpoint=expected_ssh["endpoint"],
            port=expected_ssh["port"],
            protocol=expected_ssh["protocol"],
        )
        assert_true(
            ssh_row.get("allow_source_summary") == expected_ssh["allow_source_summary"],
            "network-ports allow_source_summary drifted from the intended subnet NSG proof",
        )
        checks.append("network-ports surfaced subnet-NSG-backed ingress evidence for the public VM without inferring full reachability")

        workloads = outputs["workloads"]
        for expected in phase3_manifest["workloads"]["expected_assets"]:
            workload = find_workload(workloads, expected["asset_name"])
            assert_true(
                workload.get("asset_kind") == expected["asset_kind"],
                f"workloads asset kind mismatch for '{expected['asset_name']}'",
            )
            assert_true(
                workload.get("identity_type") == expected["identity_type"],
                f"workloads identity type mismatch for '{expected['asset_name']}'",
            )
            expected_endpoint = expected["endpoint"]
            if expected_endpoint is None:
                assert_true(
                    not workload.get("endpoints"),
                    f"workloads unexpectedly showed endpoints for '{expected['asset_name']}'",
                )
            else:
                assert_true(
                    expected_endpoint in workload.get("endpoints", []),
                    f"workloads missing endpoint '{expected_endpoint}' for '{expected['asset_name']}'",
                )
        checks.append("workloads joined compute and web assets into the expected identity and endpoint census")

        app_services = outputs["app-services"]
        for expected in phase3_manifest["app_services"]["expected_assets"]:
            asset = find_app_service(app_services, expected["name"])
            assert_true(
                asset.get("default_hostname") == expected["default_hostname"],
                f"app-services default hostname mismatch for '{expected['name']}'",
            )
            assert_true(
                bool(asset.get("https_only")) is expected["https_only"],
                f"app-services HTTPS-only posture mismatch for '{expected['name']}'",
            )
            assert_true(
                asset.get("public_network_access") == expected["public_network_access"],
                f"app-services public network access mismatch for '{expected['name']}'",
            )
            assert_true(
                asset.get("workload_identity_type") == expected["workload_identity_type"],
                f"app-services workload identity type mismatch for '{expected['name']}'",
            )
        checks.append("app-services surfaced the intended App Service hostname, identity, and public-network posture proof")

        functions = outputs["functions"]
        expected_function = phase3_manifest["functions"]["orders"]
        function_app = find_function_app(functions, expected_function["name"])
        assert_true(
            function_app.get("default_hostname") == expected_function["default_hostname"],
            "functions default hostname mismatch",
        )
        assert_true(
            function_app.get("key_vault_reference_count") == expected_function["key_vault_reference_count"],
            "functions Key Vault reference count mismatch",
        )
        assert_true(
            function_app.get("public_network_access") == expected_function["public_network_access"],
            "functions public network access mismatch",
        )
        assert_true(
            function_app.get("workload_identity_type") == expected_function["workload_identity_type"],
            "functions workload identity type mismatch",
        )
        assert_true(
            function_app.get("azure_webjobs_storage_value_type") == "plain-text",
            "functions output lost the AzureWebJobsStorage plain-text deployment signal",
        )
        checks.append("functions surfaced the intended Function App hostname, Key Vault reference, and identity proof")

        api_mgmt = outputs["api-mgmt"]
        expected_api_mgmt = phase3_manifest["api_mgmt"]["edge"]
        api_mgmt_service = find_api_management_service(api_mgmt, expected_api_mgmt["name"])
        assert_true(
            api_mgmt_service.get("public_network_access") == expected_api_mgmt["public_network_access"],
            "api-mgmt public network access mismatch",
        )
        assert_true(
            api_mgmt_service.get("workload_identity_type") == expected_api_mgmt["workload_identity_type"],
            "api-mgmt workload identity type mismatch",
        )
        assert_true(
            api_mgmt_service.get("api_count", 0) >= expected_api_mgmt["api_count"],
            "api-mgmt did not surface the intended API inventory count",
        )
        assert_true(
            api_mgmt_service.get("backend_count", 0) >= expected_api_mgmt["backend_count"],
            "api-mgmt did not surface the intended backend inventory count",
        )
        assert_true(
            api_mgmt_service.get("named_value_count", 0) >= expected_api_mgmt["named_value_count"],
            "api-mgmt did not surface the intended named value inventory count",
        )
        assert_true(
            any(
                str(hostname).endswith(expected_api_mgmt["gateway_hostname_suffix"])
                for hostname in api_mgmt_service.get("gateway_hostnames", [])
            ),
            "api-mgmt output missing the default Azure gateway hostname",
        )
        checks.append("api-mgmt surfaced gateway inventory, identity context, and public network posture from management metadata")

        aks = outputs["aks"]
        expected_aks = phase3_manifest["aks"]["ops"]
        aks_cluster = find_aks_cluster(aks, expected_aks["name"])
        assert_true(
            bool(aks_cluster.get("private_cluster_enabled")) is expected_aks["private_cluster_enabled"],
            "aks private cluster posture mismatch",
        )
        assert_true(
            aks_cluster.get("cluster_identity_type") == expected_aks["cluster_identity_type"],
            "aks cluster identity type mismatch",
        )
        assert_true(
            bool(aks_cluster.get("fqdn")),
            "aks output did not expose a control-plane FQDN for the public cluster",
        )
        assert_true(
            aks_cluster.get("agent_pool_count", 0) >= 1,
            "aks output did not expose an agent pool count",
        )
        checks.append("aks surfaced the public control-plane endpoint and cluster identity proof without requiring deeper cluster access")

        acr = outputs["acr"]
        expected_registry = phase3_manifest["acr"]["public"]
        registry = find_registry(acr, expected_registry["name"])
        assert_true(
            registry.get("login_server") == expected_registry["login_server"],
            "acr login server mismatch",
        )
        assert_true(
            registry.get("public_network_access") == expected_registry["public_network_access"],
            "acr public network access mismatch",
        )
        assert_true(
            bool(registry.get("admin_user_enabled")) is expected_registry["admin_user_enabled"],
            "acr admin user posture mismatch",
        )
        assert_true(
            registry.get("workload_identity_type") == expected_registry["workload_identity_type"],
            "acr workload identity type mismatch",
        )
        checks.append("acr surfaced the intended registry login-server, identity, and public auth posture proof")

        databases = outputs["databases"]
        expected_database = phase3_manifest["databases"]["primary"]
        database_server = find_database_server(databases, expected_database["name"])
        assert_true(
            database_server.get("engine") == expected_database["engine"],
            "databases engine mismatch",
        )
        assert_true(
            database_server.get("fully_qualified_domain_name") == expected_database["fully_qualified_domain_name"],
            "databases FQDN mismatch",
        )
        assert_true(
            database_server.get("public_network_access") == expected_database["public_network_access"],
            "databases public network access mismatch",
        )
        assert_true(
            set(expected_database["user_database_names"]).issubset(
                set(database_server.get("user_database_names", []))
            ),
            "databases output missing one or more expected user database names",
        )
        assert_true(
            database_server.get("database_count", 0) >= len(expected_database["user_database_names"]),
            "databases output reported fewer visible user databases than expected",
        )
        checks.append("databases surfaced the intended Azure SQL server endpoint and visible user-database inventory")

        dns = outputs["dns"]
        expected_public_zone = phase3_manifest["dns"]["public_zone"]
        public_zone = find_dns_zone(dns, expected_public_zone["name"])
        assert_true(
            public_zone.get("zone_kind") == expected_public_zone["zone_kind"],
            "dns public zone kind mismatch",
        )
        assert_true(
            len(public_zone.get("name_servers", [])) == expected_public_zone["expected_name_server_count"],
            "dns public zone name server count mismatch",
        )
        assert_true(
            public_zone.get("record_set_count", 0) >= expected_public_zone["minimum_record_set_count"],
            "dns public zone record_set_count was lower than expected",
        )
        expected_private_zone = phase3_manifest["dns"]["private_zone"]
        private_zone = find_dns_zone(dns, expected_private_zone["name"])
        assert_true(
            private_zone.get("zone_kind") == expected_private_zone["zone_kind"],
            "dns private zone kind mismatch",
        )
        assert_true(
            private_zone.get("linked_virtual_network_count") == expected_private_zone["linked_virtual_network_count"],
            "dns private zone linked virtual network count mismatch",
        )
        assert_true(
            private_zone.get("registration_virtual_network_count") == expected_private_zone["registration_virtual_network_count"],
            "dns private zone registration-enabled link count mismatch",
        )
        assert_true(
            private_zone.get("record_set_count", 0) >= expected_private_zone["minimum_record_set_count"],
            "dns private zone record_set_count was lower than expected",
        )
        checks.append("dns stayed within the DNS v1 boundary: zone inventory, delegation counts, and VNet-link counts only")

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

    if mode_runs_all_checks(mode):
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
        checks.append(
            "all-checks emitted complete artifact sets for identity, network, compute, config, secrets, and resource sections"
        )

    return checks, mismatches, follow_ups


def write_summary(
    artifacts_dir: Path,
    mode: str,
    checks: list[str],
    mismatches: list[str],
    follow_ups: list[str],
    run_summary_paths: dict[str, Path],
) -> None:
    summary = {
        "checks": checks,
        "follow_ups": follow_ups,
        "mismatches": mismatches,
        "mode": mode,
        "run_summary_paths": {
            section: str(path) for section, path in sorted(run_summary_paths.items())
        },
        "status": "pass",
    }
    (artifacts_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [f"AzureFox lab validation passed ({mode}).", ""]
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

    log_progress(f"[info] validation mode: {args.mode}")
    log_progress(f"[info] artifacts directory: {artifacts_dir}")
    manifest = read_manifest(lab_dir)
    all_checks_sections = ordered_all_checks_sections(
        list(manifest["all_checks_sections"].keys())
    )
    outputs, loot_paths, run_summaries, run_summary_paths = run_azurefox(
        azurefox_dir=azurefox_dir,
        python_bin=args.python,
        subscription_id=manifest["subscription_id"],
        artifacts_dir=artifacts_dir,
        mode=args.mode,
        all_checks_sections=all_checks_sections,
    )
    checks, mismatches, follow_ups = validate_outputs(
        manifest,
        args.mode,
        outputs,
        loot_paths,
        run_summaries,
        run_summary_paths,
    )
    write_summary(artifacts_dir, args.mode, checks, mismatches, follow_ups, run_summary_paths)
    print(f"Validation complete. Artifacts written to {artifacts_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        raise
