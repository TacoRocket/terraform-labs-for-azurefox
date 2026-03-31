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

output "validation_manifest" {
  description = "Stable manifest consumed by the AzureFox validation runner."
  value = {
    subscription_id = data.azurerm_subscription.current.subscription_id
    tenant_id       = data.azurerm_client_config.current.tenant_id
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
