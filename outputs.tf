output "subscription_id" {
  description = "Azure subscription ID used for the lab deployment."
  value       = data.azurerm_subscription.current.subscription_id
}

output "tenant_id" {
  description = "Azure tenant ID used for the lab deployment."
  value       = data.azurerm_client_config.current.tenant_id
}

output "resource_group_names" {
  description = "Resource groups created for the lab."
  value = {
    network  = azurerm_resource_group.network.name
    data     = azurerm_resource_group.data.name
    workload = azurerm_resource_group.workload.name
    ops      = azurerm_resource_group.ops.name
  }
}

output "vm_web_name" {
  description = "Public VM workload name."
  value       = azurerm_linux_virtual_machine.vm_web.name
}

output "vm_web_public_ip" {
  description = "Public IP assigned to the public VM."
  value       = azurerm_public_ip.vm_web.ip_address
}

output "vmss_api_name" {
  description = "Internal VM scale set name."
  value       = azurerm_linux_virtual_machine_scale_set.vmss_api.name
}

output "storage_account_names" {
  description = "Storage accounts created for the lab."
  value = {
    public  = azurerm_storage_account.public.name
    private = azurerm_storage_account.private.name
  }
}

output "managed_identity" {
  description = "Managed identity details for the public VM workload."
  value = {
    id           = azurerm_user_assigned_identity.ua_app.id
    name         = azurerm_user_assigned_identity.ua_app.name
    principal_id = azurerm_user_assigned_identity.ua_app.principal_id
    client_id    = azurerm_user_assigned_identity.ua_app.client_id
  }
}

output "role_trusts_manifest" {
  description = "Role-trusts scenario details for the AzureFox lab."
  value = {
    applications = {
      api = {
        client_id    = azuread_application.roletrust_api.client_id
        display_name = azuread_application.roletrust_api.display_name
        object_id    = azuread_application.roletrust_api.object_id
      }
      client = {
        client_id    = azuread_application.roletrust_client.client_id
        display_name = azuread_application.roletrust_client.display_name
        object_id    = azuread_application.roletrust_client.object_id
      }
    }
    federated_credential = {
      audiences    = azuread_application_federated_identity_credential.roletrust_api_github.audiences
      display_name = azuread_application_federated_identity_credential.roletrust_api_github.display_name
      issuer       = azuread_application_federated_identity_credential.roletrust_api_github.issuer
      subject      = azuread_application_federated_identity_credential.roletrust_api_github.subject
    }
    known_gaps = [
      "AzureFox only sees service principals in role-trusts when they are already visible through principals, so the lab exposes proof apps via low-impact Reader RBAC.",
      "The current lab validates app-role consent style edges, but not delegated OAuth permission grants exercised through live sign-in flows.",
      "The lab does not prove live federated token exchange; it proves only that the federated credential metadata exists and is surfaced correctly.",
    ]
    service_principals = {
      api = {
        display_name = azuread_service_principal.roletrust_api.display_name
        object_id    = azuread_service_principal.roletrust_api.object_id
      }
      client = {
        display_name = azuread_service_principal.roletrust_client.display_name
        object_id    = azuread_service_principal.roletrust_client.object_id
      }
    }
  }
}

output "validation_manifest" {
  description = "Stable manifest consumed by the AzureFox validation runner."
  value = {
    subscription_id = data.azurerm_subscription.current.subscription_id
    tenant_id       = data.azurerm_client_config.current.tenant_id
    auth_policies = {
      expected_findings = [
        "auth-policy-users-can-register-apps",
        "auth-policy-guest-invites-everyone",
        "auth-policy-user-consent-enabled",
      ]
      known_gaps = [
        "Tenant-wide auth policy enforcement is not mutated by this lab.",
        "Security defaults and Conditional Access may be partially unreadable depending on Graph policy permissions.",
        "Policy metadata does not prove sign-in enforcement outcomes without separate exercised workflows.",
      ]
      validation_mode = "non-invasive"
    }
    identity_checkpoint = {
      commands = [
        "whoami",
        "rbac",
        "principals",
        "permissions",
        "privesc",
        "role-trusts",
        "auth-policies",
        "managed-identities",
      ]
      grouped_follow_up = [
        "chains credential-path",
        "chains escalation-path",
      ]
    }
    phase2_checkpoint = {
      commands = [
        "keyvault",
        "resource-trusts",
        "arm-deployments",
        "env-vars",
        "tokens-credentials",
      ]
      grouped_follow_up = [
        "chains deployment-path",
      ]
      key_vaults = {
        open = {
          expected_finding_prefix  = "keyvault-public-network-open-"
          name                     = azurerm_key_vault.open.name
          network_default_action   = "Allow"
          private_endpoint_enabled = false
          public_network_access    = "Enabled"
          purge_protection_enabled = false
        }
        private = {
          expected_finding_prefix  = ""
          name                     = azurerm_key_vault.private.name
          network_default_action   = "Deny"
          private_endpoint_enabled = true
          public_network_access    = "Disabled"
          purge_protection_enabled = true
        }
        deny = {
          expected_finding_prefix  = "keyvault-public-network-enabled-"
          name                     = azurerm_key_vault.deny.name
          network_default_action   = "Deny"
          private_endpoint_enabled = false
          public_network_access    = "Enabled"
          purge_protection_enabled = true
        }
        hybrid = {
          expected_finding_prefix  = "keyvault-public-network-with-private-endpoint-"
          name                     = azurerm_key_vault.hybrid.name
          network_default_action   = "Deny"
          private_endpoint_enabled = true
          public_network_access    = "Enabled"
          purge_protection_enabled = true
        }
      }
      resource_trusts = {
        expected_rows = [
          {
            resource_name = azurerm_storage_account.public.name
            resource_type = "StorageAccount"
            trust_type    = "anonymous-blob-access"
          },
          {
            resource_name = azurerm_storage_account.public.name
            resource_type = "StorageAccount"
            trust_type    = "public-network-default"
          },
          {
            resource_name = azurerm_storage_account.private.name
            resource_type = "StorageAccount"
            trust_type    = "private-endpoint"
          },
          {
            resource_name = azurerm_key_vault.open.name
            resource_type = "KeyVault"
            trust_type    = "public-network"
          },
          {
            resource_name = azurerm_key_vault.deny.name
            resource_type = "KeyVault"
            trust_type    = "public-network"
          },
          {
            resource_name = azurerm_key_vault.hybrid.name
            resource_type = "KeyVault"
            trust_type    = "public-network"
          },
          {
            resource_name = azurerm_key_vault.hybrid.name
            resource_type = "KeyVault"
            trust_type    = "private-endpoint"
          },
          {
            resource_name = azurerm_key_vault.private.name
            resource_type = "KeyVault"
            trust_type    = "private-endpoint"
          },
        ]
      }
      arm_deployments = {
        failed = {
          name               = local.phase2_deployment_names.failed
          outputs_count      = 0
          provisioning_state = "Failed"
          resource_group     = azurerm_resource_group.workload.name
          scope_type         = "resource_group"
        }
        resource_group = {
          name            = local.phase2_deployment_names.resource_group
          outputs_count   = 1
          parameters_link = local.phase2_rg_parameters_uri
          resource_group  = azurerm_resource_group.data.name
          scope_type      = "resource_group"
        }
        subscription = {
          name          = local.phase2_deployment_names.subscription
          outputs_count = 2
          scope_type    = "subscription"
          template_link = local.phase2_sub_template_uri
        }
      }
      env_vars = {
        empty_identity_workload = {
          asset_name = azurerm_linux_web_app.phase2_empty.name
        }
        function_workload = {
          asset_name = azurerm_linux_function_app.phase2_orders.name
        }
        keyvault_reference = {
          asset_name                   = azurerm_linux_function_app.phase2_orders.name
          key_vault_reference_identity = azurerm_user_assigned_identity.ua_app.id
          reference_target             = local.phase2_payment_api_target
          setting_name                 = "PAYMENT_API_KEY"
        }
        plain_text_sensitive = {
          asset_name   = azurerm_linux_web_app.phase2_public.name
          setting_name = "DB_PASSWORD"
        }
      }
      tokens_credentials = {
        expected_surface_types = [
          "plain-text-secret",
          "keyvault-reference",
          "managed-identity-token",
          "deployment-output",
          "linked-deployment-content",
        ]
      }
    }
    phase3_checkpoint = {
      commands = [
        "storage",
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
        "vmss",
      ]
      grouped_follow_up = [
        "chains deployment-path",
      ]
      storage = {
        public = {
          allow_shared_key_access    = true
          dns_endpoint_type          = "Standard"
          https_traffic_only_enabled = true
          is_hns_enabled             = false
          is_sftp_enabled            = false
          minimum_tls_version        = "TLS1_2"
          name                       = azurerm_storage_account.public.name
          network_default_action     = "Allow"
          nfs_v3_enabled             = false
          private_endpoint_enabled   = false
          public_access              = true
          public_network_access      = "Enabled"
        }
        private = {
          allow_shared_key_access    = true
          dns_endpoint_type          = "Standard"
          https_traffic_only_enabled = true
          is_hns_enabled             = false
          is_sftp_enabled            = false
          minimum_tls_version        = "TLS1_2"
          name                       = azurerm_storage_account.private.name
          network_default_action     = "Deny"
          nfs_v3_enabled             = false
          private_endpoint_enabled   = true
          public_access              = false
          public_network_access      = "Enabled"
        }
      }
      nics = {
        vm_primary = {
          attached_asset_name = azurerm_linux_virtual_machine.vm_web.name
          name                = azurerm_network_interface.vm_web.name
          public_ip_id        = azurerm_public_ip.vm_web.id
          subnet_id           = azurerm_subnet.workload.id
          vnet_id             = azurerm_virtual_network.lab.id
        }
      }
      endpoints = {
        app_services = [
          {
            endpoint          = azurerm_linux_web_app.phase2_empty.default_hostname
            ingress_path      = "azurewebsites-default-hostname"
            source_asset_kind = "AppService"
            source_asset_name = azurerm_linux_web_app.phase2_empty.name
          },
          {
            endpoint          = azurerm_linux_web_app.phase2_public.default_hostname
            ingress_path      = "azurewebsites-default-hostname"
            source_asset_kind = "AppService"
            source_asset_name = azurerm_linux_web_app.phase2_public.name
          },
        ]
        function = {
          endpoint          = azurerm_linux_function_app.phase2_orders.default_hostname
          ingress_path      = "azure-functions-default-hostname"
          source_asset_kind = "FunctionApp"
          source_asset_name = azurerm_linux_function_app.phase2_orders.name
        }
        public_vm = {
          endpoint          = azurerm_public_ip.vm_web.ip_address
          exposure_family   = "public-ip"
          ingress_path      = "direct-vm-ip"
          source_asset_kind = "VM"
          source_asset_name = azurerm_linux_virtual_machine.vm_web.name
        }
      }
      network_ports = {
        ssh = {
          allow_source_summary = "Internet via subnet-nsg:${azurerm_resource_group.network.name}/${azurerm_network_security_group.workload.name}/${azurerm_network_security_rule.workload_allow_ssh_internet.name}"
          asset_name           = azurerm_linux_virtual_machine.vm_web.name
          endpoint             = azurerm_public_ip.vm_web.ip_address
          port                 = "22"
          protocol             = "TCP"
        }
      }
      workloads = {
        expected_assets = [
          {
            asset_kind    = "VM"
            asset_name    = azurerm_linux_virtual_machine.vm_web.name
            endpoint      = azurerm_public_ip.vm_web.ip_address
            identity_type = "UserAssigned"
          },
          {
            asset_kind    = "AppService"
            asset_name    = azurerm_linux_web_app.phase2_empty.name
            endpoint      = azurerm_linux_web_app.phase2_empty.default_hostname
            identity_type = "SystemAssigned"
          },
          {
            asset_kind    = "AppService"
            asset_name    = azurerm_linux_web_app.phase2_public.name
            endpoint      = azurerm_linux_web_app.phase2_public.default_hostname
            identity_type = "SystemAssigned"
          },
          {
            asset_kind    = "FunctionApp"
            asset_name    = azurerm_linux_function_app.phase2_orders.name
            endpoint      = azurerm_linux_function_app.phase2_orders.default_hostname
            identity_type = "SystemAssigned, UserAssigned"
          },
        ]
      }
      app_services = {
        expected_assets = [
          {
            default_hostname       = azurerm_linux_web_app.phase2_empty.default_hostname
            https_only             = true
            name                   = azurerm_linux_web_app.phase2_empty.name
            public_network_access  = "Enabled"
            workload_identity_type = "SystemAssigned"
          },
          {
            default_hostname       = azurerm_linux_web_app.phase2_public.default_hostname
            https_only             = true
            name                   = azurerm_linux_web_app.phase2_public.name
            public_network_access  = "Enabled"
            workload_identity_type = "SystemAssigned"
          },
        ]
      }
      functions = {
        orders = {
          default_hostname          = azurerm_linux_function_app.phase2_orders.default_hostname
          key_vault_reference_count = 1
          name                      = azurerm_linux_function_app.phase2_orders.name
          public_network_access     = "Enabled"
          workload_identity_type    = "SystemAssigned, UserAssigned"
        }
      }
      api_mgmt = {
        edge = {
          active_subscription_count       = 1
          api_count                       = 1
          api_subscription_required_count = 0
          backend_count                   = 1
          backend_hostnames               = [azurerm_linux_web_app.phase2_public.default_hostname]
          gateway_hostname_suffix         = ".azure-api.net"
          name                            = azurerm_api_management.phase3.name
          named_value_count               = 1
          named_value_key_vault_count     = 0
          named_value_secret_count        = 0
          public_network_access           = "Enabled"
          subscription_count              = 1
          workload_identity_type          = "SystemAssigned"
        }
      }
      aks = {
        ops = {
          agent_pool_count      = 1
          cluster_identity_type = "SystemAssigned"
          name                  = azurerm_kubernetes_cluster.phase3.name
          oidc_issuer_enabled   = true
        }
      }
      acr = {
        public = {
          admin_user_enabled       = true
          enabled_webhook_count    = 0
          login_server             = azurerm_container_registry.phase3.login_server
          name                     = azurerm_container_registry.phase3.name
          quarantine_policy_status = "disabled"
          replication_count        = 0
          retention_policy_days    = 7
          retention_policy_status  = "disabled"
          trust_policy_status      = "disabled"
          trust_policy_type        = "notary"
          webhook_count            = 0
        }
      }
      databases = {
        primary = {
          engine                      = "AzureSql"
          fully_qualified_domain_name = azurerm_mssql_server.phase3.fully_qualified_domain_name
          minimal_tls_version         = "1.2"
          name                        = azurerm_mssql_server.phase3.name
          public_network_access       = "Enabled"
          user_database_names         = [azurerm_mssql_database.phase3.name]
        }
      }
      vmss = {
        api = {
          identity_type                 = null
          instance_count                = 1
          name                          = azurerm_linux_virtual_machine_scale_set.vmss_api.name
          nic_configuration_count       = 1
          public_ip_configuration_count = 0
          sku_name                      = var.vmss_sku
          subnet_id                     = azurerm_subnet.workload.id
        }
      }
      dns = {
        public_zone = {
          name      = azurerm_dns_zone.phase3_public.name
          zone_kind = "public"
        }
        private_zones = {
          blob = {
            name                             = azurerm_private_dns_zone.blob.name
            private_endpoint_reference_count = 1
            zone_kind                        = "private"
          }
          internal = {
            name                             = azurerm_private_dns_zone.phase3_internal.name
            private_endpoint_reference_count = 0
            zone_kind                        = "private"
          }
          keyvault = {
            name                             = azurerm_private_dns_zone.keyvault.name
            private_endpoint_reference_count = 2
            zone_kind                        = "private"
          }
        }
      }
      known_gaps = [
        "Azure-managed hostnames in endpoints and workloads are visibility proof, not proven live ingress reachability.",
        "network-ports remains narrow NIC-backed public endpoint evidence and does not prove full effective-network reachability.",
        "Current DNS validation in this lab stays at namespace-usage metadata and private-endpoint reference counts because the current read path did not expose stable record totals, delegation details, or VNet-link counters.",
        "If a live rerun against the current AzureFox checkout still omits ACR public-network or managed-identity posture, keep the validator conservative instead of overclaiming fields the read path does not return consistently.",
      ]
    }
    phase4_checkpoint = {
      commands = [
        "automation",
        "devops",
        "lighthouse",
        "cross-tenant",
        "snapshots-disks",
      ]
      automation = {
        ops = {
          certificate_count         = 0
          connection_count          = 0
          credential_count          = 0
          encrypted_variable_count  = 0
          hybrid_worker_group_count = 0
          identity_type             = null
          job_schedule_count        = 0
          name                      = azurerm_automation_account.phase4.name
          runbook_count             = 0
          schedule_count            = 0
          variable_count            = 0
          webhook_count             = 0
        }
      }
      devops = {
        expect_unconfigured_issue_without_org = true
      }
      lighthouse = {
        validation_mode = "evidence-led"
      }
      cross_tenant = {
        validation_mode = "evidence-led"
      }
      snapshots_disks = {
        vm_web_os_disk = {
          attached_to_name      = azurerm_linux_virtual_machine.vm_web.name
          attachment_state      = "attached"
          encryption_type       = "EncryptionAtRestWithPlatformKey"
          network_access_policy = "AllowAll"
          os_type               = "Linux"
          public_network_access = "Enabled"
        }
      }
      known_gaps = [
        "cross-tenant remains tenant- and permission-dependent, so the lab keeps it evidence-led rather than row-count gated.",
        "lighthouse remains subscription- and tenant-shaped; promote stronger assertions only if the lab intentionally adds delegated-management proof.",
        "devops needs a real Azure DevOps organization, project, and pipeline path before it can move past conditional validation of command behavior and truthful issue surfacing.",
        "automation currently validates the visible zero-object execution posture, but the current AzureFox read path did not return a managed-identity type for the lab-owned Automation account during the April 8, 2026 live pass.",
      ]
    }
    grouped_follow_up = {
      command = "chains"
      implemented_families = [
        "credential-path",
        "deployment-path",
        "escalation-path",
      ]
      validation_mode = "optional-follow-up"
    }
    resource_groups = {
      network  = azurerm_resource_group.network.name
      data     = azurerm_resource_group.data.name
      workload = azurerm_resource_group.workload.name
      ops      = azurerm_resource_group.ops.name
    }
    vm = {
      name      = azurerm_linux_virtual_machine.vm_web.name
      public_ip = azurerm_public_ip.vm_web.ip_address
      nic_id    = azurerm_network_interface.vm_web.id
    }
    vmss = {
      name = azurerm_linux_virtual_machine_scale_set.vmss_api.name
    }
    managed_identity = {
      id           = azurerm_user_assigned_identity.ua_app.id
      name         = azurerm_user_assigned_identity.ua_app.name
      principal_id = azurerm_user_assigned_identity.ua_app.principal_id
      client_id    = azurerm_user_assigned_identity.ua_app.client_id
    }
    storage_accounts = {
      public = {
        id   = azurerm_storage_account.public.id
        name = azurerm_storage_account.public.name
      }
      private = {
        id   = azurerm_storage_account.private.id
        name = azurerm_storage_account.private.name
      }
    }
    role_assignment = {
      scope     = data.azurerm_subscription.current.id
      role_name = azurerm_role_assignment.ua_app_owner.role_definition_name
    }
    role_trusts = {
      applications = {
        api = {
          client_id    = azuread_application.roletrust_api.client_id
          display_name = azuread_application.roletrust_api.display_name
          object_id    = azuread_application.roletrust_api.object_id
        }
        client = {
          client_id    = azuread_application.roletrust_client.client_id
          display_name = azuread_application.roletrust_client.display_name
          object_id    = azuread_application.roletrust_client.object_id
        }
      }
      expected_trust_types = [
        "app-owner",
        "service-principal-owner",
        "federated-credential",
        "app-to-service-principal",
      ]
      federated_credential = {
        issuer  = azuread_application_federated_identity_credential.roletrust_api_github.issuer
        subject = azuread_application_federated_identity_credential.roletrust_api_github.subject
      }
      service_principals = {
        api = {
          display_name = azuread_service_principal.roletrust_api.display_name
          object_id    = azuread_service_principal.roletrust_api.object_id
        }
        client = {
          display_name = azuread_service_principal.roletrust_client.display_name
          object_id    = azuread_service_principal.roletrust_client.object_id
        }
      }
    }
    viewpoints = {
      admin = {
        commands = [
          "whoami",
          "inventory",
          "automation",
          "devops",
          "arm-deployments",
          "env-vars",
          "tokens-credentials",
          "rbac",
          "principals",
          "permissions",
          "privesc",
          "role-trusts",
          "lighthouse",
          "cross-tenant",
          "resource-trusts",
          "auth-policies",
          "managed-identities",
          "keyvault",
          "storage",
          "vms",
          "vmss",
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
          "snapshots-disks",
        ]
        expected_visibility = "broadest-lab-truth"
        principal_type      = "User"
        validation_mode     = "release-gate"
      }
      dev = {
        artifact_subdir     = "dev"
        commands            = ["whoami", "principals", "permissions", "managed-identities", "workloads", "functions"]
        display_name        = azuread_application.viewpoint_dev.display_name
        expected_visibility = "scoped-workload-operator"
        forbidden_roles     = ["Owner"]
        principal_object_id = azuread_service_principal.viewpoint_dev.object_id
        principal_type      = "ServicePrincipal"
        scopes = [
          {
            role_name  = azurerm_role_assignment.viewpoint_dev_workload_contributor.role_definition_name
            scope_kind = "resource-group"
            scope_name = azurerm_resource_group.workload.name
          },
        ]
      }
      lower_privilege = {
        artifact_subdir     = "lower-privilege"
        commands            = ["whoami", "principals", "permissions", "managed-identities", "workloads", "functions"]
        display_name        = azuread_application.viewpoint_low_priv.display_name
        expected_visibility = "constrained-workload-reader"
        forbidden_roles     = ["Owner", "Contributor"]
        principal_object_id = azuread_service_principal.viewpoint_low_priv.object_id
        principal_type      = "ServicePrincipal"
        scopes = [
          {
            role_name  = azurerm_role_assignment.viewpoint_low_priv_workload_reader.role_definition_name
            scope_kind = "resource-group"
            scope_name = azurerm_resource_group.workload.name
          },
        ]
      }
    }
    expected_signals = {
      public_storage_default_action  = "Allow"
      private_storage_default_action = "Deny"
      private_endpoint_enabled       = true
      vm_has_public_ip               = true
      vm_identity_name               = azurerm_user_assigned_identity.ua_app.name
      high_privilege_role            = "Owner"
    }
  }
}

output "validation_viewpoints" {
  description = "Sensitive credentials and login metadata for viewpoint-aware AzureFox validation."
  sensitive   = true
  value = {
    dev = {
      client_id           = azuread_application.viewpoint_dev.client_id
      client_secret       = azuread_application_password.viewpoint_dev.value
      display_name        = azuread_application.viewpoint_dev.display_name
      principal_object_id = azuread_service_principal.viewpoint_dev.object_id
      subscription_id     = data.azurerm_subscription.current.subscription_id
      tenant_id           = data.azurerm_client_config.current.tenant_id
      viewpoint           = "dev"
    }
    lower_privilege = {
      client_id           = azuread_application.viewpoint_low_priv.client_id
      client_secret       = azuread_application_password.viewpoint_low_priv.value
      display_name        = azuread_application.viewpoint_low_priv.display_name
      principal_object_id = azuread_service_principal.viewpoint_low_priv.object_id
      subscription_id     = data.azurerm_subscription.current.subscription_id
      tenant_id           = data.azurerm_client_config.current.tenant_id
      viewpoint           = "lower-privilege"
    }
  }
}
