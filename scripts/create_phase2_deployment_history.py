#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the Phase 2 ARM deployment-history proof objects for the AzureFox lab."
    )
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--subscription-deployment-name", required=True)
    parser.add_argument("--subscription-template-uri", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--resource-group-deployment-name", required=True)
    parser.add_argument("--resource-group-parameters-uri", required=True)
    parser.add_argument("--failed-resource-group", required=True)
    parser.add_argument("--failed-deployment-name", required=True)
    return parser.parse_args()


def run(cmd: list[str], *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if expect_success and completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed


def run_json(cmd: list[str]) -> dict:
    completed = run(cmd)
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Command did not return JSON: {' '.join(cmd)}\nSTDOUT:\n{completed.stdout}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from: {' '.join(cmd)}")
    return payload


def put_resource(uri_path: str, body: dict, *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "az",
            "rest",
            "--method",
            "put",
            "--uri",
            f"https://management.azure.com{uri_path}?api-version=2022-09-01",
            "--body",
            json.dumps(body),
            "--only-show-errors",
            "--output",
            "json",
        ],
        expect_success=expect_success,
    )


def get_resource_json(uri_path: str) -> dict:
    return run_json(
        [
            "az",
            "rest",
            "--method",
            "get",
            "--uri",
            f"https://management.azure.com{uri_path}?api-version=2022-09-01",
            "--output",
            "json",
        ]
    )


def wait_for_group_deployment(
    *,
    subscription_id: str,
    resource_group: str,
    deployment_name: str,
    allowed_states: set[str],
    retries: int = 10,
    delay_seconds: float = 2.0,
) -> dict:
    uri_path = (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.Resources/deployments/{deployment_name}"
    )
    last_error: RuntimeError | None = None
    for _ in range(retries):
        try:
            payload = get_resource_json(uri_path)
        except RuntimeError as exc:
            last_error = exc
            time.sleep(delay_seconds)
            continue

        state = ((payload.get("properties") or {}).get("provisioningState")) or ""
        if state in allowed_states:
            return payload
        time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error
    raise RuntimeError(
        f"Deployment '{deployment_name}' in resource group '{resource_group}' did not reach one of "
        f"{sorted(allowed_states)}."
    )


def ensure_failed_deployment(
    *,
    subscription_id: str,
    failed_resource_group: str,
    failed_deployment_name: str,
    templates_dir: Path,
) -> None:
    failed_template_path = templates_dir / "app-failed.json"
    deployment_uri_path = (
        f"/subscriptions/{subscription_id}/resourceGroups/{failed_resource_group}"
        f"/providers/Microsoft.Resources/deployments/{failed_deployment_name}"
    )
    put_resource(
        deployment_uri_path,
        {
            "properties": {
                "mode": "Incremental",
                "template": json.loads(failed_template_path.read_text()),
            }
        },
        expect_success=False,
    )
    payload = wait_for_group_deployment(
        subscription_id=subscription_id,
        resource_group=failed_resource_group,
        deployment_name=failed_deployment_name,
        allowed_states={"Failed", "Succeeded"},
    )
    state = ((payload.get("properties") or {}).get("provisioningState")) or ""
    if state != "Failed":
        raise RuntimeError(
            f"Deployment '{failed_deployment_name}' did not persist in Failed state; saw '{state}'."
        )


def main() -> int:
    args = parse_args()
    templates_dir = Path(__file__).resolve().parent / "arm-templates"

    run(
        [
            "az",
            "deployment",
            "sub",
            "create",
            "--location",
            args.location,
            "--name",
            args.subscription_deployment_name,
            "--template-uri",
            args.subscription_template_uri,
            "--only-show-errors",
            "--output",
            "json",
        ]
    )

    put_resource(
        (
            f"/subscriptions/{args.subscription_id}/resourceGroups/{args.resource_group}"
            f"/providers/Microsoft.Resources/deployments/{args.resource_group_deployment_name}"
        ),
        {
            "properties": {
                "mode": "Incremental",
                "template": json.loads((templates_dir / "kv-secrets.json").read_text()),
                "parametersLink": {
                    "uri": args.resource_group_parameters_uri,
                    "contentVersion": "1.0.0.0",
                },
            }
        },
    )
    wait_for_group_deployment(
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        deployment_name=args.resource_group_deployment_name,
        allowed_states={"Succeeded"},
    )

    ensure_failed_deployment(
        subscription_id=args.subscription_id,
        failed_resource_group=args.failed_resource_group,
        failed_deployment_name=args.failed_deployment_name,
        templates_dir=templates_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
