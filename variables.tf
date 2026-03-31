variable "location" {
  description = "Azure region for all lab resources."
  type        = string
  default     = "centralus"
}

variable "name_prefix" {
  description = "Short prefix used in globally-unique resource names."
  type        = string
  default     = "azurefoxlab"

  validation {
    condition     = can(regex("^[a-zA-Z0-9-]{3,18}$", var.name_prefix))
    error_message = "name_prefix must be 3-18 characters and contain only letters, numbers, or hyphens."
  }
}

variable "vm_admin_username" {
  description = "Admin username for the lab VM and VM scale set."
  type        = string
  default     = "azurefox"
}

variable "ssh_public_key" {
  description = "RSA SSH public key used for the lab VM and VM scale set."
  type        = string
  nullable    = false

  validation {
    condition     = length(trimspace(var.ssh_public_key)) > 0
    error_message = "ssh_public_key must be provided."
  }

  validation {
    condition     = startswith(trimspace(var.ssh_public_key), "ssh-rsa ")
    error_message = "Azure requires an RSA SSH public key for this lab. Generate one with ssh-keygen -t rsa -b 4096."
  }
}

variable "vm_size" {
  description = "Azure VM size for the public VM workload. Standard_D2s_v3 is the tested fallback when smaller SKUs are restricted."
  type        = string
  default     = "Standard_D2s_v3"
}

variable "vmss_sku" {
  description = "Azure SKU for the VM scale set. Standard_D2s_v3 is the tested fallback when smaller SKUs are restricted."
  type        = string
  default     = "Standard_D2s_v3"
}
