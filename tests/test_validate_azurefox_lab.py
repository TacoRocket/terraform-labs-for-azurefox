from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_validator_module():
    module_path = (
        Path("/Users/cfarley/Documents/HarrierOps/Azure/Terraform Labs for AzureFox")
        / "scripts"
        / "validate_azurefox_lab.py"
    )
    spec = importlib.util.spec_from_file_location("validate_azurefox_lab", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValidateAzureFoxLabTests(unittest.TestCase):
    def test_viewpoint_commands_use_full_command_surface_for_reduced_viewpoints(self) -> None:
        validator = load_validator_module()

        self.assertEqual(
            validator.viewpoint_commands("dev", set()),
            validator.COMMANDS,
        )
        self.assertEqual(
            validator.viewpoint_commands("lower-privilege", set()),
            validator.COMMANDS,
        )

    def test_run_azurefox_failure_keeps_viewpoint_in_timeline_write(self) -> None:
        validator = load_validator_module()

        recorded_viewpoints: list[str] = []

        def fake_write_command_timeline(
            artifacts_dir: Path,
            *,
            mode: str,
            viewpoint: str,
            subscription_id: str,
            commands: list[str],
            skipped_commands: set[str],
            started_at_utc: str,
            command_runs: list[dict[str, object]],
            finished_at_utc: str | None = None,
        ) -> None:
            recorded_viewpoints.append(viewpoint)

        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            with (
                patch.object(validator, "run_json", side_effect=RuntimeError("boom")),
                patch.object(validator, "write_command_timeline", side_effect=fake_write_command_timeline),
            ):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    validator.run_azurefox(
                        azurefox_dir=artifacts_dir,
                        python_bin="python3",
                        subscription_id="sub-123",
                        artifacts_dir=artifacts_dir,
                        mode="full",
                        viewpoint="admin",
                        commands=["whoami"],
                        skipped_commands=set(),
                    )

        self.assertEqual(recorded_viewpoints, ["admin", "admin"])

    def test_run_azurefox_success_keeps_viewpoint_in_timeline_write(self) -> None:
        validator = load_validator_module()

        recorded_viewpoints: list[str] = []

        def fake_write_command_timeline(
            artifacts_dir: Path,
            *,
            mode: str,
            viewpoint: str,
            subscription_id: str,
            commands: list[str],
            skipped_commands: set[str],
            started_at_utc: str,
            command_runs: list[dict[str, object]],
            finished_at_utc: str | None = None,
        ) -> None:
            recorded_viewpoints.append(viewpoint)

        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            outdir = artifacts_dir / "whoami"
            loot_dir = outdir / "loot"
            loot_dir.mkdir(parents=True, exist_ok=True)
            (loot_dir / "whoami.json").write_text("{}", encoding="utf-8")

            with (
                patch.object(validator, "run_json", return_value={"ok": True}),
                patch.object(validator, "write_command_timeline", side_effect=fake_write_command_timeline),
            ):
                outputs, loot_paths = validator.run_azurefox(
                    azurefox_dir=artifacts_dir,
                    python_bin="python3",
                    subscription_id="sub-123",
                    artifacts_dir=artifacts_dir,
                    mode="full",
                    viewpoint="admin",
                    commands=["whoami"],
                    skipped_commands=set(),
                )

        self.assertEqual(outputs, {"whoami": {"ok": True}})
        self.assertIn("whoami", loot_paths)
        self.assertEqual(recorded_viewpoints, ["admin", "admin", "admin"])

    def test_current_identity_privesc_accepts_current_foothold_direct_control(self) -> None:
        validator = load_validator_module()

        self.assertTrue(
            validator.has_current_identity_privesc_path(
                {
                    "paths": [
                        {
                            "path_type": "current-foothold-direct-control",
                            "current_identity": True,
                        }
                    ]
                }
            )
        )

    def test_managed_identity_privesc_accepts_ingress_backed_identity(self) -> None:
        validator = load_validator_module()

        self.assertTrue(
            validator.has_managed_identity_privesc_path(
                {
                    "paths": [
                        {
                            "path_type": "ingress-backed-workload-identity",
                            "principal_id": "mi-123",
                            "asset": "vm-web-01",
                        }
                    ]
                },
                "mi-123",
                "vm-web-01",
            )
        )

    def test_find_network_effective_returns_matching_row(self) -> None:
        validator = load_validator_module()

        row = validator.find_network_effective(
            {
                "effective_exposures": [
                    {
                        "asset_name": "vm-web-01",
                        "endpoint": "1.2.3.4",
                        "effective_exposure": "high",
                    }
                ]
            },
            asset_name="vm-web-01",
            endpoint="1.2.3.4",
        )

        self.assertEqual(row["effective_exposure"], "high")

    def test_validate_network_effective_output_accepts_manifest_backed_row(self) -> None:
        validator = load_validator_module()

        message = validator.validate_network_effective_output(
            {
                "network_effective": {
                    "public_vm": {
                        "asset_name": "vm-web-01",
                        "constrained_ports": [],
                        "effective_exposure": "high",
                        "endpoint": "1.2.3.4",
                        "endpoint_type": "ip",
                        "internet_exposed_ports": ["TCP/22"],
                        "observed_paths": ["Internet via subnet-nsg:rg-network/nsg-workload/allow-ssh-internet"],
                    }
                }
            },
            {
                "effective_exposures": [
                    {
                        "asset_name": "vm-web-01",
                        "constrained_ports": [],
                        "effective_exposure": "high",
                        "endpoint": "1.2.3.4",
                        "endpoint_type": "ip",
                        "internet_exposed_ports": ["TCP/22"],
                        "observed_paths": ["Internet via subnet-nsg:rg-network/nsg-workload/allow-ssh-internet"],
                        "summary": (
                            "Asset 'vm-web-01' endpoint 1.2.3.4 has internet-facing allow evidence "
                            "on TCP/22. Treat this as visible Azure network triage signal, not proof "
                            "of full effective reachability."
                        ),
                    }
                ]
            },
        )

        self.assertIn("network-effective summarized", message)

    def test_find_application_gateway_returns_matching_row(self) -> None:
        validator = load_validator_module()

        row = validator.find_application_gateway(
            {
                "application_gateways": [
                    {
                        "name": "agw-edge-123456",
                        "public_frontend_count": 1,
                    }
                ]
            },
            "agw-edge-123456",
        )

        self.assertEqual(row["public_frontend_count"], 1)

    def test_validate_application_gateway_output_accepts_manifest_backed_row(self) -> None:
        validator = load_validator_module()

        message = validator.validate_application_gateway_output(
            {
                "application_gateway": {
                    "edge": {
                        "name": "agw-edge-123456",
                        "public_frontend_count": 1,
                        "listener_count": 1,
                        "request_routing_rule_count": 1,
                        "backend_pool_count": 1,
                        "backend_target_count": 1,
                        "waf_mode": "Prevention",
                        "firewall_policy_id": "/subscriptions/sub/resourceGroups/rg-network/providers/Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies/waf-edge-123456",
                    }
                }
            },
            {
                "application_gateways": [
                    {
                        "name": "agw-edge-123456",
                        "public_frontend_count": 1,
                        "listener_count": 1,
                        "request_routing_rule_count": 1,
                        "backend_pool_count": 1,
                        "backend_target_count": 1,
                        "waf_mode": "Prevention",
                        "firewall_policy_id": "/subscriptions/sub/resourceGroups/rg-network/providers/Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies/waf-edge-123456",
                    }
                ]
            },
        )

        self.assertIn("application-gateway surfaced", message)

    def test_find_devops_pipeline_returns_matching_pipeline(self) -> None:
        validator = load_validator_module()

        pipeline = validator.find_devops_pipeline(
            {
                "pipelines": [
                    {
                        "name": "lab-proof-targeted",
                        "target_clues": ["App Service: app-public-api-123456"],
                    }
                ]
            },
            "lab-proof-targeted",
        )

        self.assertEqual(pipeline["name"], "lab-proof-targeted")

    def test_validate_application_gateway_output_accepts_firewall_policy_without_mode(self) -> None:
        validator = load_validator_module()

        message = validator.validate_application_gateway_output(
            {
                "application_gateway": {
                    "edge": {
                        "name": "agw-edge-123456",
                        "public_frontend_count": 1,
                        "listener_count": 1,
                        "request_routing_rule_count": 1,
                        "backend_pool_count": 1,
                        "backend_target_count": 1,
                        "waf_mode": "Prevention",
                        "firewall_policy_id": "/subscriptions/sub/resourceGroups/rg-network/providers/Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies/waf-edge-123456",
                    }
                }
            },
            {
                "application_gateways": [
                    {
                        "name": "agw-edge-123456",
                        "public_frontend_count": 1,
                        "listener_count": 1,
                        "request_routing_rule_count": 1,
                        "backend_pool_count": 1,
                        "backend_target_count": 1,
                        "waf_mode": None,
                        "firewall_policy_id": "/subscriptions/sub/resourceGroups/rg-network/providers/Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies/waf-edge-123456",
                    }
                ]
            },
        )

        self.assertIn("application-gateway surfaced", message)

    def test_validate_application_gateway_output_normalizes_firewall_policy_id_case(self) -> None:
        validator = load_validator_module()

        message = validator.validate_application_gateway_output(
            {
                "application_gateway": {
                    "edge": {
                        "name": "agw-edge-123456",
                        "public_frontend_count": 1,
                        "listener_count": 1,
                        "request_routing_rule_count": 1,
                        "backend_pool_count": 1,
                        "backend_target_count": 1,
                        "waf_mode": "Prevention",
                        "firewall_policy_id": "/subscriptions/sub/resourceGroups/rg-network/providers/Microsoft.Network/applicationGatewayWebApplicationFirewallPolicies/waf-edge-123456",
                    }
                }
            },
            {
                "application_gateways": [
                    {
                        "name": "agw-edge-123456",
                        "public_frontend_count": 1,
                        "listener_count": 1,
                        "request_routing_rule_count": 1,
                        "backend_pool_count": 1,
                        "backend_target_count": 1,
                        "waf_mode": None,
                        "firewall_policy_id": "/subscriptions/sub/resourceGroups/rg-network/providers/Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies/waf-edge-123456",
                    }
                ]
            },
        )

        self.assertIn("application-gateway surfaced", message)

    def test_find_container_app_returns_matching_row(self) -> None:
        validator = load_validator_module()

        row = validator.find_container_app(
            {
                "container_apps": [
                    {
                        "name": "ca-public-123456",
                        "default_hostname": "ca-public-123456.bluepond.westeurope.azurecontainerapps.io",
                    }
                ]
            },
            "ca-public-123456",
        )

        self.assertEqual(
            row["default_hostname"],
            "ca-public-123456.bluepond.westeurope.azurecontainerapps.io",
        )

    def test_validate_container_app_output_accepts_manifest_backed_row(self) -> None:
        validator = load_validator_module()

        message = validator.validate_container_app_output(
            {
                "container_apps": {
                    "public_api": {
                        "name": "ca-public-123456",
                        "default_hostname": "ca-public-123456.bluepond.westeurope.azurecontainerapps.io",
                        "external_ingress_enabled": True,
                        "ingress_target_port": 80,
                        "revision_mode": "Single",
                        "environment_id": "/subscriptions/sub/resourceGroups/rg-workload/providers/Microsoft.App/managedEnvironments/cae-ops-123456",
                        "workload_identity_type": "UserAssigned",
                    }
                }
            },
            {
                "container_apps": [
                    {
                        "name": "ca-public-123456",
                        "default_hostname": "ca-public-123456.bluepond.westeurope.azurecontainerapps.io",
                        "external_ingress_enabled": True,
                        "ingress_target_port": 80,
                        "revision_mode": "Single",
                        "environment_id": "/subscriptions/sub/resourceGroups/rg-workload/providers/Microsoft.App/managedEnvironments/cae-ops-123456",
                        "workload_identity_type": "UserAssigned",
                    }
                ]
            },
        )

        self.assertIn("container-apps surfaced", message)

    def test_find_container_instance_returns_matching_row(self) -> None:
        validator = load_validator_module()

        row = validator.find_container_instance(
            {
                "container_instances": [
                    {
                        "name": "aci-web-123456",
                        "public_ip_address": "1.2.3.4",
                    }
                ]
            },
            "aci-web-123456",
        )

        self.assertEqual(row["public_ip_address"], "1.2.3.4")

    def test_validate_container_instance_output_accepts_manifest_backed_row(self) -> None:
        validator = load_validator_module()

        message = validator.validate_container_instance_output(
            {
                "container_instances": {
                    "public_web": {
                        "name": "aci-web-123456",
                        "public_ip_address": "1.2.3.4",
                        "fqdn": "aci-web-123456.centralus.azurecontainer.io",
                        "exposed_ports": [80],
                        "restart_policy": "Always",
                        "os_type": "Linux",
                        "workload_identity_type": "UserAssigned",
                    }
                }
            },
            {
                "container_instances": [
                    {
                        "name": "aci-web-123456",
                        "public_ip_address": "1.2.3.4",
                        "fqdn": "aci-web-123456.centralus.azurecontainer.io",
                        "exposed_ports": [80],
                        "restart_policy": "Always",
                        "os_type": "Linux",
                        "workload_identity_type": "UserAssigned",
                    }
                ]
            },
        )

        self.assertIn("container-instances surfaced", message)


if __name__ == "__main__":
    unittest.main()
