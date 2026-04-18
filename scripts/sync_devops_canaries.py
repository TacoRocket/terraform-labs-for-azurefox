#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


LAB_DIR = Path(__file__).resolve().parents[1]
CANARY_DIR = LAB_DIR / "devops-canaries"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render and sync Azure DevOps proof canaries into the lab-proof repo."
    )
    parser.add_argument(
        "--lab-dir",
        type=Path,
        default=LAB_DIR,
        help="Path to the Terraform lab root.",
    )
    parser.add_argument(
        "--org",
        default=os.environ.get("AZUREFOX_DEVOPS_ORG"),
        help="Azure DevOps organization name or URL. Defaults to AZUREFOX_DEVOPS_ORG.",
    )
    parser.add_argument(
        "--project",
        default="Azurefox Proof Lab",
        help="Azure DevOps project name.",
    )
    parser.add_argument(
        "--repo",
        default="lab-proof",
        help="Azure DevOps repo name that stores the proof YAML.",
    )
    parser.add_argument(
        "--service-connection",
        default="af-rg-reader",
        help="Azure service connection name used by the canaries.",
    )
    parser.add_argument(
        "--variable-group",
        default="af-proof-lab-vars",
        help="Variable group name used by the canaries.",
    )
    parser.add_argument(
        "--root-pipeline-name",
        default="lab-proof",
        help="Pipeline definition name for the root-YAML canary.",
    )
    parser.add_argument(
        "--template-pipeline-name",
        default="lab-proof-template",
        help="Pipeline definition name for the same-repo template canary.",
    )
    parser.add_argument(
        "--named-target-pipeline-name",
        default="lab-proof-targeted",
        help="Pipeline definition name for the named-target canary.",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Azure Repos branch to update.",
    )
    parser.add_argument(
        "--skip-pipeline-create",
        action="store_true",
        help="Only sync repo content and skip pipeline-definition creation.",
    )
    args = parser.parse_args()
    if not args.org:
        parser.error("--org or AZUREFOX_DEVOPS_ORG is required")
    return args


def normalize_org_url(value: str) -> str:
    if value.startswith("https://") or value.startswith("http://"):
        return value.rstrip("/")
    return f"https://dev.azure.com/{value.rstrip('/')}"


def run_json(cmd: list[str], *, cwd: Path | None = None, input_text: str | None = None) -> Any:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return json.loads(result.stdout)


def read_manifest(lab_dir: Path) -> dict[str, Any]:
    value = run_json(["tofu", "output", "-json", "validation_manifest"], cwd=lab_dir)
    if not isinstance(value, dict):
        raise RuntimeError("validation_manifest output was not a JSON object")
    return value


def select_named_webapp(manifest: dict[str, Any]) -> str:
    app_services = manifest["phase3_checkpoint"]["app_services"]["expected_assets"]
    public_candidates = [
        asset["name"]
        for asset in app_services
        if asset.get("public_network_access") == "Enabled"
    ]
    if not public_candidates:
        raise RuntimeError("validation_manifest did not expose a public app-service canary target")
    public_candidates.sort(key=lambda name: ("public" not in name, name))
    return public_candidates[0]


def render_canary_files(manifest: dict[str, Any], args: argparse.Namespace) -> dict[str, str]:
    substitutions = {
        "__SERVICE_CONNECTION__": args.service_connection,
        "__VARIABLE_GROUP__": args.variable_group,
        "__OPS_RESOURCE_GROUP__": manifest["resource_groups"]["ops"],
        "__WORKLOAD_RESOURCE_GROUP__": manifest["resource_groups"]["workload"],
        "__NAMED_WEBAPP__": select_named_webapp(manifest),
    }
    templates = {
        "/azure-pipelines.yml": (CANARY_DIR / "azure-pipelines.yml.tmpl").read_text(
            encoding="utf-8"
        ),
        "/pipelines/template-follow.yml": (
            CANARY_DIR / "pipelines" / "template-follow.yml.tmpl"
        ).read_text(encoding="utf-8"),
        "/pipelines/named-target.yml": (
            CANARY_DIR / "pipelines" / "named-target.yml.tmpl"
        ).read_text(encoding="utf-8"),
        "/templates/deploy-canary.yml": (
            CANARY_DIR / "templates" / "deploy-canary.yml.tmpl"
        ).read_text(encoding="utf-8"),
    }
    rendered: dict[str, str] = {}
    for path, content in templates.items():
        rendered_content = content
        for needle, replacement in substitutions.items():
            rendered_content = rendered_content.replace(needle, replacement)
        rendered[path] = rendered_content
    return rendered


def get_repository(repo_name: str, *, org: str, project: str) -> dict[str, Any]:
    return run_json(
        [
            "az",
            "repos",
            "show",
            "--org",
            org,
            "--project",
            project,
            "--repository",
            repo_name,
            "--output",
            "json",
        ]
    )


def get_branch_head(repo_id: str, branch: str, *, org: str, project: str) -> str:
    refs = run_json(
        [
            "az",
            "devops",
            "invoke",
            "--org",
            org,
            "--area",
            "git",
            "--resource",
            "refs",
            "--route-parameters",
            f"project={project}",
            f"repositoryId={repo_id}",
            "--query-parameters",
            f"filter=heads/{branch}",
            "--output",
            "json",
        ]
    )
    values = refs.get("value", [])
    if not values:
        raise RuntimeError(f"Azure DevOps repo is missing branch '{branch}'")
    return values[0]["objectId"]


def list_repo_paths(repo_id: str, branch: str, *, org: str, project: str) -> set[str]:
    items = run_json(
        [
            "az",
            "devops",
            "invoke",
            "--org",
            org,
            "--area",
            "git",
            "--resource",
            "items",
            "--route-parameters",
            f"project={project}",
            f"repositoryId={repo_id}",
            "--query-parameters",
            "scopePath=/",
            "recursionLevel=Full",
            f"versionDescriptor.version={branch}",
            "versionDescriptor.versionType=branch",
            "--output",
            "json",
        ]
    )
    return {item["path"] for item in items.get("value", [])}


def push_repo_content(
    *,
    repo_id: str,
    branch: str,
    old_object_id: str,
    files: dict[str, str],
    existing_paths: set[str],
    org: str,
    project: str,
) -> dict[str, Any]:
    changes = [
        {
            "changeType": "edit" if path in existing_paths else "add",
            "item": {"path": path},
            "newContent": {
                "content": content,
                "contentType": "rawtext",
            },
        }
        for path, content in files.items()
    ]
    payload = {
        "refUpdates": [
            {
                "name": f"refs/heads/{branch}",
                "oldObjectId": old_object_id,
            }
        ],
        "commits": [
            {
                "comment": "Add AzureFox DevOps canary files",
                "changes": changes,
            }
        ],
    }
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        json.dump(payload, handle)
        temp_path = handle.name
    try:
        return run_json(
            [
                "az",
                "devops",
                "invoke",
                "--org",
                org,
                "--area",
                "git",
                "--resource",
                "pushes",
                "--route-parameters",
                f"project={project}",
                f"repositoryId={repo_id}",
                "--http-method",
                "POST",
                "--in-file",
                temp_path,
                "--output",
                "json",
            ]
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)


def list_pipelines(*, org: str, project: str) -> list[dict[str, Any]]:
    value = run_json(
        [
            "az",
            "pipelines",
            "list",
            "--org",
            org,
            "--project",
            project,
            "--output",
            "json",
        ]
    )
    if not isinstance(value, list):
        raise RuntimeError("az pipelines list did not return a list")
    return value


def list_service_endpoints(*, org: str, project: str) -> list[dict[str, Any]]:
    value = run_json(
        [
            "az",
            "devops",
            "service-endpoint",
            "list",
            "--org",
            org,
            "--project",
            project,
            "--output",
            "json",
        ]
    )
    if not isinstance(value, list):
        raise RuntimeError("az devops service-endpoint list did not return a list")
    return value


def list_variable_groups(*, org: str, project: str) -> list[dict[str, Any]]:
    value = run_json(
        [
            "az",
            "pipelines",
            "variable-group",
            "list",
            "--org",
            org,
            "--project",
            project,
            "--output",
            "json",
        ]
    )
    if not isinstance(value, list):
        raise RuntimeError("az pipelines variable-group list did not return a list")
    return value


def validate_devops_prerequisites(
    *,
    org: str,
    project: str,
    repo_name: str,
    service_connection_name: str,
    variable_group_name: str,
) -> None:
    missing: list[str] = []
    try:
        get_repository(repo_name, org=org, project=project)
    except RuntimeError:
        missing.append(f"- create Azure Repos repo '{repo_name}' in project '{project}'")

    if service_connection_name not in {
        endpoint.get("name") for endpoint in list_service_endpoints(org=org, project=project)
    }:
        missing.append(
            "- create Azure Resource Manager service connection "
            f"'{service_connection_name}' in project '{project}'"
        )

    if variable_group_name not in {
        group.get("name") for group in list_variable_groups(org=org, project=project)
    }:
        missing.append(
            f"- create variable group '{variable_group_name}' in project '{project}' "
            "with at least one placeholder variable such as LAB_PROOF_SECRET=not-real"
        )

    if missing:
        raise RuntimeError(
            "Azure DevOps lab prerequisites are missing for the canary sync:\n"
            + "\n".join(missing)
        )


def ensure_pipeline(
    *,
    pipeline_name: str,
    yaml_path: str,
    repo_name: str,
    branch: str,
    existing_names: set[str],
    org: str,
    project: str,
) -> None:
    if pipeline_name in existing_names:
        return
    run_json(
        [
            "az",
            "pipelines",
            "create",
            "--org",
            org,
            "--project",
            project,
            "--name",
            pipeline_name,
            "--repository",
            repo_name,
            "--repository-type",
            "tfsgit",
            "--branch",
            branch,
            "--yml-path",
            yaml_path.lstrip("/"),
            "--skip-first-run",
            "true",
            "--output",
            "json",
        ]
    )


def main() -> None:
    args = parse_args()
    org_url = normalize_org_url(args.org)
    validate_devops_prerequisites(
        org=org_url,
        project=args.project,
        repo_name=args.repo,
        service_connection_name=args.service_connection,
        variable_group_name=args.variable_group,
    )
    manifest = read_manifest(args.lab_dir)
    rendered_files = render_canary_files(manifest, args)
    repo = get_repository(args.repo, org=org_url, project=args.project)
    head_commit = get_branch_head(repo["id"], args.branch, org=org_url, project=args.project)
    existing_paths = list_repo_paths(repo["id"], args.branch, org=org_url, project=args.project)
    push_repo_content(
        repo_id=repo["id"],
        branch=args.branch,
        old_object_id=head_commit,
        files=rendered_files,
        existing_paths=existing_paths,
        org=org_url,
        project=args.project,
    )

    if args.skip_pipeline_create:
        return

    existing_names = {pipeline["name"] for pipeline in list_pipelines(org=org_url, project=args.project)}
    ensure_pipeline(
        pipeline_name=args.root_pipeline_name,
        yaml_path="/azure-pipelines.yml",
        repo_name=args.repo,
        branch=args.branch,
        existing_names=existing_names,
        org=org_url,
        project=args.project,
    )
    existing_names.add(args.root_pipeline_name)
    ensure_pipeline(
        pipeline_name=args.template_pipeline_name,
        yaml_path="/pipelines/template-follow.yml",
        repo_name=args.repo,
        branch=args.branch,
        existing_names=existing_names,
        org=org_url,
        project=args.project,
    )
    existing_names.add(args.template_pipeline_name)
    ensure_pipeline(
        pipeline_name=args.named_target_pipeline_name,
        yaml_path="/pipelines/named-target.yml",
        repo_name=args.repo,
        branch=args.branch,
        existing_names=existing_names,
        org=org_url,
        project=args.project,
    )


if __name__ == "__main__":
    main()
