data "azuread_application_published_app_ids" "well_known" {}

data "azuread_client_config" "current" {}

data "azurerm_client_config" "current" {}

data "azurerm_subscription" "current" {}

locals {
  sanitized_prefix = substr(lower(replace(var.name_prefix, "-", "")), 0, 12)
  unique_suffix    = substr(md5("${data.azurerm_client_config.current.subscription_id}-${var.name_prefix}"), 0, 8)

  storage_public_name            = substr("st${local.sanitized_prefix}pub${local.unique_suffix}", 0, 24)
  storage_private_name           = substr("st${local.sanitized_prefix}priv${local.unique_suffix}", 0, 24)
  function_storage_name          = substr("st${local.sanitized_prefix}func${local.unique_suffix}", 0, 24)
  roletrust_api_name             = "af-roletrust-api"
  roletrust_client_name          = "af-roletrust-client"
  keyvault_open_name             = substr("kvlabopen01${local.unique_suffix}", 0, 24)
  keyvault_private_name          = substr("kvlabpriv01${local.unique_suffix}", 0, 24)
  keyvault_deny_name             = substr("kvlabdeny01${local.unique_suffix}", 0, 24)
  keyvault_hybrid_name           = substr("kvlabhybrid01${local.unique_suffix}", 0, 24)
  phase2_app_name                = "app-public-api-${substr(local.unique_suffix, 0, 6)}"
  phase2_function_name           = "func-orders-${substr(local.unique_suffix, 0, 6)}"
  phase2_empty_app_name          = "app-empty-mi-${substr(local.unique_suffix, 0, 6)}"
  phase2_plan_name               = "asp-phase2-linux"
  phase2_proof_container_name    = "phase2proof"
  phase2_sub_template_hash       = substr(filemd5("${path.module}/scripts/arm-templates/sub-foundation.json"), 0, 8)
  phase2_rg_parameters_hash      = substr(filemd5("${path.module}/scripts/arm-templates/kv-secrets.parameters.json"), 0, 8)
  phase2_sub_template_blob_name  = "templates/sub-foundation-${local.phase2_sub_template_hash}.json"
  phase2_rg_parameters_blob_name = "parameters/kv-secrets-${local.phase2_rg_parameters_hash}.parameters.json"
  phase2_deployment_names = {
    subscription   = "sub-foundation"
    resource_group = "kv-secrets"
    failed         = "app-failed"
  }

  resource_groups = {
    network  = "rg-network"
    data     = "rg-data"
    workload = "rg-workload"
    ops      = "rg-ops"
  }

  tags = {
    project     = "azurefox-proof-lab"
    managed_by  = "opentofu"
    environment = "lab"
  }

  roletrust_api_app_role_id = "0db62ee5-39df-4cb8-a72b-8d1ca8a07301" # gitleaks:allow
}

resource "azurerm_resource_group" "network" {
  name     = local.resource_groups.network
  location = var.location
  tags     = local.tags
}

resource "azurerm_resource_group" "data" {
  name     = local.resource_groups.data
  location = var.location
  tags     = local.tags
}

resource "azurerm_resource_group" "workload" {
  name     = local.resource_groups.workload
  location = var.location
  tags     = local.tags
}

resource "azurerm_resource_group" "ops" {
  name     = local.resource_groups.ops
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "lab" {
  name                = "vnet-azurefox-lab"
  address_space       = ["10.42.0.0/16"]
  location            = azurerm_resource_group.network.location
  resource_group_name = azurerm_resource_group.network.name
  tags                = local.tags
}

resource "azurerm_subnet" "workload" {
  name                 = "snet-workload"
  resource_group_name  = azurerm_resource_group.network.name
  virtual_network_name = azurerm_virtual_network.lab.name
  address_prefixes     = ["10.42.1.0/24"]
}

resource "azurerm_subnet" "private_endpoints" {
  name                              = "snet-private-endpoints"
  resource_group_name               = azurerm_resource_group.network.name
  virtual_network_name              = azurerm_virtual_network.lab.name
  address_prefixes                  = ["10.42.2.0/24"]
  private_endpoint_network_policies = "Disabled"
}

resource "azurerm_network_security_group" "workload" {
  name                = "nsg-workload"
  location            = azurerm_resource_group.network.location
  resource_group_name = azurerm_resource_group.network.name
  tags                = local.tags
}

resource "azurerm_subnet_network_security_group_association" "workload" {
  subnet_id                 = azurerm_subnet.workload.id
  network_security_group_id = azurerm_network_security_group.workload.id
}

resource "azurerm_public_ip" "vm_web" {
  name                = "pip-vm-web-01"
  location            = azurerm_resource_group.workload.location
  resource_group_name = azurerm_resource_group.workload.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_network_interface" "vm_web" {
  name                = "nic-web-01"
  location            = azurerm_resource_group.workload.location
  resource_group_name = azurerm_resource_group.workload.name
  tags                = local.tags

  ip_configuration {
    name                          = "ipconfig-web-01"
    subnet_id                     = azurerm_subnet.workload.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.vm_web.id
  }
}

resource "azurerm_user_assigned_identity" "ua_app" {
  name                = "ua-app"
  location            = azurerm_resource_group.workload.location
  resource_group_name = azurerm_resource_group.workload.name
  tags                = local.tags
}

resource "azuread_application" "roletrust_api" {
  display_name     = local.roletrust_api_name
  owners           = [data.azuread_client_config.current.object_id]
  sign_in_audience = "AzureADMyOrg"

  api {
    mapped_claims_enabled          = false
    requested_access_token_version = 2

    oauth2_permission_scope {
      admin_consent_description  = "Allow the AzureFox role-trusts client app to read the proof API."
      admin_consent_display_name = "Read proof API"
      enabled                    = true
      id                         = "0a8db3fa-4df2-46dc-97b7-a3184b4f2156"
      type                       = "Admin"
      user_consent_description   = "Allow the AzureFox role-trusts client app to read the proof API."
      user_consent_display_name  = "Read proof API"
      value                      = "Proof.Read"
    }
  }

  app_role {
    allowed_member_types = ["Application"]
    description          = "Allow a lab client application to call the proof API."
    display_name         = "Proof.Invoke"
    enabled              = true
    id                   = local.roletrust_api_app_role_id
    value                = "Proof.Invoke"
  }
}

resource "azuread_service_principal" "roletrust_api" {
  client_id                    = azuread_application.roletrust_api.client_id
  app_role_assignment_required = false
  owners                       = [data.azuread_client_config.current.object_id]
}

resource "azuread_application_federated_identity_credential" "roletrust_api_github" {
  application_id = azuread_application.roletrust_api.id
  display_name   = "github-main"
  description    = "Proof-only federated credential for AzureFox role-trusts validation."
  issuer         = "https://token.actions.githubusercontent.com"
  audiences      = ["api://AzureADTokenExchange"]
  subject        = "repo:TacoRocket/AzureFox:ref:refs/heads/main"
}

resource "azuread_application" "roletrust_client" {
  display_name     = local.roletrust_client_name
  owners           = [data.azuread_client_config.current.object_id]
  sign_in_audience = "AzureADMyOrg"

  required_resource_access {
    resource_app_id = azuread_application.roletrust_api.client_id

    resource_access {
      id   = local.roletrust_api_app_role_id
      type = "Role"
    }
  }

  required_resource_access {
    resource_app_id = data.azuread_application_published_app_ids.well_known.result.MicrosoftGraph

    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d"
      type = "Scope"
    }
  }
}

resource "azuread_service_principal" "roletrust_client" {
  client_id                    = azuread_application.roletrust_client.client_id
  app_role_assignment_required = false
  owners                       = [data.azuread_client_config.current.object_id]
}

resource "azuread_app_role_assignment" "roletrust_client_to_api" {
  app_role_id         = local.roletrust_api_app_role_id
  principal_object_id = azuread_service_principal.roletrust_client.object_id
  resource_object_id  = azuread_service_principal.roletrust_api.object_id
}

resource "azurerm_linux_virtual_machine" "vm_web" {
  name                = "vm-web-01"
  location            = azurerm_resource_group.workload.location
  resource_group_name = azurerm_resource_group.workload.name
  size                = var.vm_size
  admin_username      = var.vm_admin_username
  network_interface_ids = [
    azurerm_network_interface.vm_web.id,
  ]
  disable_password_authentication = true
  tags                            = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.ua_app.id]
  }

  admin_ssh_key {
    username   = var.vm_admin_username
    public_key = trimspace(var.ssh_public_key)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}

resource "azurerm_role_assignment" "roletrust_api_reader" {
  scope                = azurerm_resource_group.ops.id
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.roletrust_api.object_id
}

resource "azurerm_role_assignment" "roletrust_client_reader" {
  scope                = azurerm_resource_group.ops.id
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.roletrust_client.object_id
}

resource "azurerm_linux_virtual_machine_scale_set" "vmss_api" {
  name                            = "vmss-api"
  location                        = azurerm_resource_group.workload.location
  resource_group_name             = azurerm_resource_group.workload.name
  sku                             = var.vmss_sku
  instances                       = 1
  admin_username                  = var.vm_admin_username
  disable_password_authentication = true
  overprovision                   = false
  tags                            = local.tags

  admin_ssh_key {
    username   = var.vm_admin_username
    public_key = trimspace(var.ssh_public_key)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  network_interface {
    name    = "nic-vmss-api"
    primary = true

    ip_configuration {
      name      = "ipconfig-vmss-api"
      primary   = true
      subnet_id = azurerm_subnet.workload.id
    }
  }
}

resource "azurerm_storage_account" "public" {
  name                            = local.storage_public_name
  resource_group_name             = azurerm_resource_group.data.name
  location                        = azurerm_resource_group.data.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  access_tier                     = "Hot"
  public_network_access_enabled   = true
  allow_nested_items_to_be_public = true
  tags                            = local.tags
}

resource "azurerm_storage_account" "private" {
  name                            = local.storage_private_name
  resource_group_name             = azurerm_resource_group.data.name
  location                        = azurerm_resource_group.data.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  access_tier                     = "Hot"
  public_network_access_enabled   = true
  allow_nested_items_to_be_public = false
  tags                            = local.tags

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }
}

resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = azurerm_resource_group.network.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "blob-zone-link"
  resource_group_name   = azurerm_resource_group.network.name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = azurerm_virtual_network.lab.id
  registration_enabled  = false
  tags                  = local.tags
}

resource "azurerm_private_endpoint" "storage_private_blob" {
  name                = "pe-${azurerm_storage_account.private.name}-blob"
  location            = azurerm_resource_group.data.location
  resource_group_name = azurerm_resource_group.data.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-${azurerm_storage_account.private.name}-blob"
    private_connection_resource_id = azurerm_storage_account.private.id
    is_manual_connection           = false
    subresource_names              = ["blob"]
  }

  private_dns_zone_group {
    name                 = "blob-zone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }
}

resource "azurerm_storage_container" "phase2_proof" {
  name                  = local.phase2_proof_container_name
  storage_account_name  = azurerm_storage_account.public.name
  container_access_type = "blob"
}

resource "azurerm_storage_blob" "phase2_sub_template" {
  name                   = local.phase2_sub_template_blob_name
  storage_account_name   = azurerm_storage_account.public.name
  storage_container_name = azurerm_storage_container.phase2_proof.name
  type                   = "Block"
  source                 = "${path.module}/scripts/arm-templates/sub-foundation.json"
}

resource "azurerm_storage_blob" "phase2_rg_parameters" {
  name                   = local.phase2_rg_parameters_blob_name
  storage_account_name   = azurerm_storage_account.public.name
  storage_container_name = azurerm_storage_container.phase2_proof.name
  type                   = "Block"
  source                 = "${path.module}/scripts/arm-templates/kv-secrets.parameters.json"
}

resource "azurerm_key_vault" "open" {
  name                          = local.keyvault_open_name
  location                      = azurerm_resource_group.data.location
  resource_group_name           = azurerm_resource_group.data.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  soft_delete_retention_days    = 7
  purge_protection_enabled      = false
  public_network_access_enabled = true
  enable_rbac_authorization     = false
  tags                          = local.tags

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    secret_permissions = [
      "Delete",
      "Get",
      "List",
      "Purge",
      "Recover",
      "Set",
    ]
  }

  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }
}

resource "azurerm_key_vault" "private" {
  name                          = local.keyvault_private_name
  location                      = azurerm_resource_group.data.location
  resource_group_name           = azurerm_resource_group.data.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "premium"
  soft_delete_retention_days    = 7
  purge_protection_enabled      = true
  public_network_access_enabled = false
  enable_rbac_authorization     = true
  tags                          = local.tags

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
  }
}

resource "azurerm_key_vault" "deny" {
  name                          = local.keyvault_deny_name
  location                      = azurerm_resource_group.data.location
  resource_group_name           = azurerm_resource_group.data.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  soft_delete_retention_days    = 7
  purge_protection_enabled      = true
  public_network_access_enabled = true
  enable_rbac_authorization     = true
  tags                          = local.tags

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
  }
}

resource "azurerm_key_vault" "hybrid" {
  name                          = local.keyvault_hybrid_name
  location                      = azurerm_resource_group.data.location
  resource_group_name           = azurerm_resource_group.data.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "premium"
  soft_delete_retention_days    = 7
  purge_protection_enabled      = true
  public_network_access_enabled = true
  enable_rbac_authorization     = true
  tags                          = local.tags

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
  }
}

resource "azurerm_private_dns_zone" "keyvault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = azurerm_resource_group.network.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "keyvault" {
  name                  = "keyvault-zone-link"
  resource_group_name   = azurerm_resource_group.network.name
  private_dns_zone_name = azurerm_private_dns_zone.keyvault.name
  virtual_network_id    = azurerm_virtual_network.lab.id
  registration_enabled  = false
  tags                  = local.tags
}

resource "azurerm_private_endpoint" "keyvault_private" {
  name                = "pe-${azurerm_key_vault.private.name}-vault"
  location            = azurerm_resource_group.data.location
  resource_group_name = azurerm_resource_group.data.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-${azurerm_key_vault.private.name}-vault"
    private_connection_resource_id = azurerm_key_vault.private.id
    is_manual_connection           = false
    subresource_names              = ["vault"]
  }

  private_dns_zone_group {
    name                 = "keyvault-zone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.keyvault.id]
  }
}

resource "azurerm_private_endpoint" "keyvault_hybrid" {
  name                = "pe-${azurerm_key_vault.hybrid.name}-vault"
  location            = azurerm_resource_group.data.location
  resource_group_name = azurerm_resource_group.data.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-${azurerm_key_vault.hybrid.name}-vault"
    private_connection_resource_id = azurerm_key_vault.hybrid.id
    is_manual_connection           = false
    subresource_names              = ["vault"]
  }

  private_dns_zone_group {
    name                 = "keyvault-zone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.keyvault.id]
  }
}

resource "azurerm_service_plan" "phase2_linux" {
  name                = local.phase2_plan_name
  resource_group_name = azurerm_resource_group.workload.name
  location            = azurerm_resource_group.workload.location
  os_type             = "Linux"
  sku_name            = "B1"
  tags                = local.tags
}

resource "azurerm_storage_account" "function" {
  name                     = local.function_storage_name
  resource_group_name      = azurerm_resource_group.workload.name
  location                 = azurerm_resource_group.workload.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  access_tier              = "Hot"
  tags                     = local.tags
}

resource "azurerm_linux_web_app" "phase2_public" {
  name                = local.phase2_app_name
  resource_group_name = azurerm_resource_group.workload.name
  location            = azurerm_resource_group.workload.location
  service_plan_id     = azurerm_service_plan.phase2_linux.id
  https_only          = true
  tags                = local.tags

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = false

    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    API_BASE_URL = "https://example.internal/api"
    DB_PASSWORD  = "AzureFox-Lab-PlainText-Only"
  }
}

resource "azurerm_linux_web_app" "phase2_empty" {
  name                = local.phase2_empty_app_name
  resource_group_name = azurerm_resource_group.workload.name
  location            = azurerm_resource_group.workload.location
  service_plan_id     = azurerm_service_plan.phase2_linux.id
  https_only          = true
  tags                = local.tags

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = false

    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {}
}

resource "azurerm_linux_function_app" "phase2_orders" {
  name                            = local.phase2_function_name
  resource_group_name             = azurerm_resource_group.workload.name
  location                        = azurerm_resource_group.workload.location
  service_plan_id                 = azurerm_service_plan.phase2_linux.id
  storage_account_name            = azurerm_storage_account.function.name
  storage_account_access_key      = azurerm_storage_account.function.primary_access_key
  key_vault_reference_identity_id = azurerm_user_assigned_identity.ua_app.id
  functions_extension_version     = "~4"
  https_only                      = true
  tags                            = local.tags

  identity {
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.ua_app.id]
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    PAYMENT_API_KEY = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.open.name};SecretName=payment-api-key)"
  }
}

locals {
  phase2_proof_blob_base_url = trimsuffix(azurerm_storage_account.public.primary_blob_endpoint, "/")
  phase2_sub_template_uri    = "${local.phase2_proof_blob_base_url}/${azurerm_storage_container.phase2_proof.name}/${azurerm_storage_blob.phase2_sub_template.name}"
  phase2_rg_parameters_uri   = "${local.phase2_proof_blob_base_url}/${azurerm_storage_container.phase2_proof.name}/${azurerm_storage_blob.phase2_rg_parameters.name}"
  phase2_payment_api_target  = "${azurerm_key_vault.open.name}.vault.azure.net/secrets/payment-api-key"
}

resource "terraform_data" "phase2_deployment_history" {
  input = {
    failed_deployment_name         = local.phase2_deployment_names.failed
    failed_resource_group          = azurerm_resource_group.workload.name
    location                       = azurerm_resource_group.workload.location
    resource_group                 = azurerm_resource_group.data.name
    resource_group_deployment_name = local.phase2_deployment_names.resource_group
    resource_group_parameters_uri  = local.phase2_rg_parameters_uri
    subscription_deployment_name   = local.phase2_deployment_names.subscription
    subscription_id                = data.azurerm_subscription.current.subscription_id
    subscription_template_uri      = local.phase2_sub_template_uri
  }

  triggers_replace = {
    failed_deployment_name        = local.phase2_deployment_names.failed
    resource_group                = azurerm_resource_group.data.name
    resource_group_parameters_uri = local.phase2_rg_parameters_uri
    subscription_deployment_name  = local.phase2_deployment_names.subscription
    subscription_template_uri     = local.phase2_sub_template_uri
  }

  provisioner "local-exec" {
    command = "python3 ${path.module}/scripts/create_phase2_deployment_history.py --subscription-id '${self.input.subscription_id}' --location '${self.input.location}' --subscription-deployment-name '${self.input.subscription_deployment_name}' --subscription-template-uri '${self.input.subscription_template_uri}' --resource-group '${self.input.resource_group}' --resource-group-deployment-name '${self.input.resource_group_deployment_name}' --resource-group-parameters-uri '${self.input.resource_group_parameters_uri}' --failed-resource-group '${self.input.failed_resource_group}' --failed-deployment-name '${self.input.failed_deployment_name}'"
  }

  depends_on = [
    azurerm_storage_blob.phase2_rg_parameters,
    azurerm_storage_blob.phase2_sub_template,
  ]
}

resource "azurerm_role_assignment" "ua_app_owner" {
  scope                            = data.azurerm_subscription.current.id
  role_definition_name             = "Owner"
  principal_id                     = azurerm_user_assigned_identity.ua_app.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}
