# AzureFox OpenTofu Proof Lab

This repo contains an OpenTofu lab environment for demonstrating AzureFox against a real Azure subscription.

The lab is intentionally small, disposable, and security-relevant. It creates a controlled Azure footprint that AzureFox can enumerate to prove the current command set works end-to-end in a live tenant.

## What This Repo Is For

- give AzureFox a real Azure target for demos and proof-of-capability runs
- exercise the current AzureFox command set against live infrastructure
- provide a repeatable OpenTofu deployment and teardown flow
- generate validation artifacts that show AzureFox findings against known lab conditions

## AzureFox Coverage

The lab is designed to trigger the current AzureFox commands:

- `whoami`
- `inventory`
- `rbac`
- `managed-identities`
- `storage`
- `vms`

The project is OpenTofu-first, but the HCL stays Terraform-familiar on purpose. That keeps licensing concerns lower while preserving a familiar structure for Terraform users.

## Lab Shape

- Four resource groups: `rg-network`, `rg-data`, `rg-workload`, and `rg-ops`
- One VNet with a workload subnet and a private-endpoint subnet
- One public Linux VM named `vm-web-01`
- One Linux VM scale set named `vmss-api`
- One user-assigned managed identity named `ua-app`
- One storage account that allows public blob access and uses firewall default action `Allow`
- One storage account with firewall default action `Deny` plus a private endpoint
- One subscription-scope `Owner` role assignment for the managed identity

That combination is enough for AzureFox to surface:

- subscription context from `whoami`
- resource counts and resource types from `inventory`
- elevated role assignment visibility from `rbac`
- managed identity attachment plus a high-severity finding from `managed-identities`
- public storage and open firewall findings from `storage`
- a public VM with an attached identity from `vms`

## Warning

This lab intentionally creates risky posture in Azure:

- public IP exposure
- public blob access
- subscription-scope `Owner` RBAC

Use a throwaway subscription dedicated to testing. Do not deploy this into a shared or production-adjacent subscription.

## Prerequisites

- [OpenTofu](https://opentofu.org/) installed and available as `tofu`
- Azure CLI installed and available as `az`
- Access to a disposable Azure subscription
- Python 3.11+ for the AzureFox CLI
- An AzureFox checkout available locally

Recommended local checks:

```bash
tofu version
az version
python3 --version
```

## Authenticate To Azure

AzureFox prefers Azure CLI authentication first, so start there:

```bash
az login
az account set --subscription <subscription-id>
```

OpenTofu will also use the Azure CLI session unless you override authentication with environment variables.

## Configure

Copy the example variable file and replace the SSH public key:

```bash
cp tofu.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set:

- `ssh_public_key` with an RSA public key
- `name_prefix` if you want a different globally unique storage name prefix
- optional VM sizing overrides if needed

Current tested fallback defaults:

- `location = "centralus"`
- `vm_size = "Standard_D2s_v3"`
- `vmss_sku = "Standard_D2s_v3"`

Why these are the defaults:

- smaller B-series and other low-cost SKUs may be blocked for new or recently upgraded subscriptions with `NotAvailableForSubscription`
- `Standard_D2s_v3` in `centralus` was validated as available for this lab subscription and uses a family with non-zero default quota in this subscription
- this is a POC-oriented fallback, not the long-term ideal cost profile

Generate a compatible keypair:

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/azurefox_lab_rsa -C "azurefox-lab" -N ""
cat ~/.ssh/azurefox_lab_rsa.pub
```

## Deploy

```bash
tofu init
tofu plan
tofu apply
```

Useful outputs after apply:

```bash
tofu output subscription_id
tofu output -json validation_manifest
```

## Validate AzureFox Against The Lab

Install the AzureFox package dependencies in your preferred environment, then run:

```bash
python3 scripts/validate_azurefox_lab.py
```

By default the validator:

- reads `tofu output -json validation_manifest`
- executes AzureFox from `--azurefox-dir`
- runs all six supported AzureFox commands
- stores proof artifacts under `proof-artifacts/latest`

Optional flags:

```bash
python3 scripts/validate_azurefox_lab.py \
  --azurefox-dir /path/to/azurefox \
  --artifacts-dir ./proof-artifacts/run-01
```

Artifacts include:

- one JSON payload per AzureFox command
- copied loot files emitted by AzureFox
- `summary.json`
- `summary.txt`

## Destroy

Tear the lab down when you are done:

```bash
tofu destroy
```

## Terraform User Notes

If you are more comfortable with Terraform, the lab should still look familiar:

- configuration files stay in normal `.tf` files
- provider configuration uses `hashicorp/azurerm`
- local state remains `terraform.tfstate`
- the lock file remains `.terraform.lock.hcl`

The practical differences to keep in mind are:

- run `tofu` instead of `terraform`
- review `.terraform.lock.hcl` changes after `tofu init`
- avoid alternating between `terraform` and `tofu` against the same state unless the team deliberately supports that workflow
- most Azure examples online are Terraform-branded, so translate commands carefully

## Known OpenTofu Considerations

- Tooling and CI jobs need to invoke `tofu`, not `terraform`.
- The lock file name is still `.terraform.lock.hcl`, which is familiar but easy to overlook during reviews.
- Local state still uses `terraform.tfstate`, so mixed-tool usage can confuse contributors if the workflow is not documented.
- This v1 lab intentionally avoids OpenTofu-only language features to reduce surprise for Terraform users.
- If the lab later adopts remote state, re-check backend behavior and team workflow before standardizing it.

## Cost And Capacity Notes

- The intended long-term lab shape is to use lower-cost VM SKUs when the subscription allows them.
- Some new or recently upgraded Azure subscriptions return `NotAvailableForSubscription` for small VM families even across multiple regions.
- The current repo defaults use `Standard_D2s_v3` in `centralus` because that combination was verified as deployable for this subscription during bring-up.
- For public release, revisit quotas/SKU access and move back to smaller defaults when possible.
