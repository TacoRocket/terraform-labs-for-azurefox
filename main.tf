data "azurerm_client_config" "current" {}

data "azurerm_subscription" "current" {}

locals {
  sanitized_prefix = substr(lower(replace(var.name_prefix, "-", "")), 0, 12)
  unique_suffix    = substr(md5("${data.azurerm_client_config.current.subscription_id}-${var.name_prefix}"), 0, 8)

  storage_public_name  = substr("st${local.sanitized_prefix}pub${local.unique_suffix}", 0, 24)
  storage_private_name = substr("st${local.sanitized_prefix}priv${local.unique_suffix}", 0, 24)

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

  network_rules {
    default_action = "Allow"
    bypass         = ["AzureServices"]
  }
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

resource "azurerm_role_assignment" "ua_app_owner" {
  scope                            = data.azurerm_subscription.current.id
  role_definition_name             = "Owner"
  principal_id                     = azurerm_user_assigned_identity.ua_app.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}
