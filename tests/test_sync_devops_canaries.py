from __future__ import annotations

import importlib.util
import unittest
from unittest import mock
from pathlib import Path


def load_sync_module():
    module_path = (
        Path("/Users/cfarley/Documents/HarrierOps/Azure/Terraform Labs for AzureFox")
        / "scripts"
        / "sync_devops_canaries.py"
    )
    spec = importlib.util.spec_from_file_location("sync_devops_canaries", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SyncDevOpsCanariesTests(unittest.TestCase):
    def test_normalize_org_url_accepts_name_or_url(self) -> None:
        sync = load_sync_module()

        self.assertEqual(
            sync.normalize_org_url("example-proof-lab"),
            "https://dev.azure.com/example-proof-lab",
        )
        self.assertEqual(
            sync.normalize_org_url("https://dev.azure.com/example-proof-lab/"),
            "https://dev.azure.com/example-proof-lab",
        )

    def test_select_named_webapp_prefers_public_named_asset(self) -> None:
        sync = load_sync_module()

        selected = sync.select_named_webapp(
            {
                "phase3_checkpoint": {
                    "app_services": {
                        "expected_assets": [
                            {
                                "name": "app-empty-mi-123456",
                                "public_network_access": "Enabled",
                            },
                            {
                                "name": "app-public-api-123456",
                                "public_network_access": "Enabled",
                            },
                        ]
                    }
                }
            }
        )

        self.assertEqual(selected, "app-public-api-123456")

    def test_render_canary_files_includes_lab_specific_values(self) -> None:
        sync = load_sync_module()

        args = type(
            "Args",
            (),
            {
                "service_connection": "af-rg-reader",
                "variable_group": "af-proof-lab-vars",
            },
        )()
        rendered = sync.render_canary_files(
            {
                "resource_groups": {
                    "ops": "rg-ops",
                    "workload": "rg-workload",
                },
                "phase3_checkpoint": {
                    "app_services": {
                        "expected_assets": [
                            {
                                "name": "app-empty-mi-123456",
                                "public_network_access": "Enabled",
                            },
                            {
                                "name": "app-public-api-123456",
                                "public_network_access": "Enabled",
                            },
                        ]
                    }
                },
            },
            args,
        )

        self.assertIn("af-proof-lab-vars", rendered["/azure-pipelines.yml"])
        self.assertIn("/templates/deploy-canary.yml", rendered["/pipelines/template-follow.yml"])
        self.assertIn("af-rg-reader", rendered["/templates/deploy-canary.yml"])
        self.assertIn("af-proof-lab-vars", rendered["/templates/deploy-canary.yml"])
        self.assertIn("rg-workload", rendered["/templates/deploy-canary.yml"])
        self.assertIn("app-public-api-123456", rendered["/pipelines/named-target.yml"])

    def test_validate_devops_prerequisites_raises_for_missing_items(self) -> None:
        sync = load_sync_module()

        with self.assertRaisesRegex(RuntimeError, "Azure DevOps lab prerequisites are missing"):
            with mock.patch.object(sync, "get_repository", side_effect=RuntimeError("missing")), \
                 mock.patch.object(sync, "list_service_endpoints", return_value=[]), \
                 mock.patch.object(sync, "list_variable_groups", return_value=[]):
                sync.validate_devops_prerequisites(
                    org="https://dev.azure.com/example",
                    project="Azurefox Proof Lab",
                    repo_name="lab-proof",
                    service_connection_name="af-rg-reader",
                    variable_group_name="af-proof-lab-vars",
                )


if __name__ == "__main__":
    unittest.main()
