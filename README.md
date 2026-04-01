# AzureFox OpenTofu Proof Lab

This repo contains an OpenTofu lab environment for demonstrating AzureFox against a real Azure subscription.

The lab is intentionally small, disposable, and security-relevant. It creates a controlled Azure footprint that AzureFox can enumerate to prove the current command set works end-to-end in a live tenant.

## What This Repo Is For

- give AzureFox a real Azure target for demos and proof-of-capability runs
- exercise the current AzureFox command set against live infrastructure
- provide a repeatable OpenTofu deployment and teardown flow
- generate validation artifacts that show AzureFox findings against known lab conditions

## AzureFox Coverage

The lab is designed to trigger or validate the current AzureFox checkpoint:

- `whoami`
- `inventory`
- `arm-deployments`
- `env-vars`
- `tokens-credentials`
- `rbac`
- `principals`
- `permissions`
- `privesc`
- `role-trusts`
- `resource-trusts`
- `auth-policies`
- `managed-identities`
- `keyvault`
- `storage`
- `vms`
- `all-checks --section identity`
- `all-checks --section config`
- `all-checks --section secrets`
- `all-checks --section resource`

The project is OpenTofu-first, but the HCL stays Terraform-familiar on purpose. That keeps licensing concerns lower while preserving a familiar structure for Terraform users.

## Lab Shape

- Four resource groups: `rg-network`, `rg-data`, `rg-workload`, and `rg-ops`
- One VNet with a workload subnet and a private-endpoint subnet
- One public Linux VM named `vm-web-01`
- One Linux VM scale set named `vmss-api`
- One user-assigned managed identity named `ua-app`
- Two app registrations plus backing service principals for role-trusts validation:
  `af-roletrust-api` and `af-roletrust-client`
- One federated identity credential on `af-roletrust-api`
- One internal app-role assignment from `af-roletrust-client` to `af-roletrust-api`
- Low-impact `Reader` RBAC assignments that make the proof service principals visible to AzureFox
- One storage account that allows public blob access and uses firewall default action `Allow`
- One storage account with firewall default action `Deny` plus a private endpoint
- One public blob container that hosts linked ARM template and parameter proof artifacts
- Four Key Vaults that cover:
  public network open
  public network enabled with firewall deny
  public network plus private endpoint
  private endpoint only
- One Linux App Service with a system-assigned identity and a plain-text sensitive setting
- One Linux Function App with system-assigned plus user-assigned identity and a Key Vault-backed app setting
- One Linux App Service with attached identity and intentionally empty app settings
- Three deployment-history proof objects:
  one succeeded subscription deployment with linked template URI
  one succeeded resource-group deployment with linked parameters URI
  one failed resource-group deployment with no outputs
- One subscription-scope `Owner` role assignment for the managed identity

That combination is enough for AzureFox to surface:

- subscription context from `whoami`
- resource counts and resource types from `inventory`
- deployment history posture and linked-content metadata from `arm-deployments`
- management-plane app setting exposure from `env-vars`
- correlated token and credential surfaces across apps, VMs, and deployments from `tokens-credentials`
- elevated role assignment visibility from `rbac`
- a subscription-visible principal census from `principals`
- high-impact-role triage from `permissions`
- direct-role and public-identity escalation leads from `privesc`
- app ownership, service-principal ownership, federated credential, and app-role trust edges from `role-trusts`
- storage plus Key Vault exposure rows from `resource-trusts`
- managed identity attachment plus a high-severity finding from `managed-identities`
- Key Vault public-network, private-endpoint, and purge-protection posture from `keyvault`
- public storage and open firewall findings from `storage`
- a public VM with an attached identity from `vms`
- identity checkpoint orchestration artifacts from `all-checks --section identity`
- config checkpoint orchestration artifacts from `all-checks --section config`
- secrets checkpoint orchestration artifacts from `all-checks --section secrets`
- resource checkpoint orchestration artifacts from `all-checks --section resource`

`auth-policies` is intentionally handled differently in this repo for now:

- the validator checks that AzureFox reports readable tenant auth metadata truthfully
- the validator records permission-denied or partial-read conditions explicitly
- the lab does not mutate tenant-wide Entra auth policy state during this phase

## Warning

This lab intentionally creates risky posture in Azure:

- public IP exposure
- public blob access
- subscription-scope `Owner` RBAC

Use a throwaway subscription dedicated to testing. Do not deploy this into a shared or production-adjacent subscription.

The repo does not intentionally change tenant-wide Entra auth controls in this phase. Keep it that way unless the team explicitly decides the added blast radius and rollback burden are worth it.

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

`tofu apply` now also stamps the Phase 2 ARM deployment-history proof objects through a small
Azure CLI helper after the linked template artifacts exist. That helper is intentionally narrow:
it creates one succeeded subscription deployment, one succeeded resource-group deployment, and one
failed resource-group deployment so AzureFox can validate deployment-history coverage live.

Useful outputs after apply:

```bash
tofu output subscription_id
tofu output -json role_trusts_manifest
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
- runs the current AzureFox command set covered by this lab
- runs `all-checks --section identity`
- runs `all-checks --section config`
- runs `all-checks --section secrets`
- runs `all-checks --section resource`
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
- `all-checks --section <section>` output plus `run-summary.json` for `identity`, `config`, `secrets`, and `resource`
- `summary.json`
- `summary.txt`
- `azurefox-mismatch-report.md`
- `identity-mismatch-report.md`
- `azurefox-follow-up-items.md`

## Evidence Boundary

The lab is here to validate AzureFox output, not to excuse weak wording or guessed findings.

What AzureFox can prove directly from read-only control-plane and Graph data:

- that an app registration, service principal, owner edge, federated credential, app-role assignment, or auth-policy row exists in the readable APIs
- that a resource or identity is visible and how AzureFox summarized it
- that a policy surface was partially unreadable when Graph returned a permission or visibility error
- that Key Vault network posture, private endpoint presence, and purge-protection posture are present in management metadata
- that deployment history recorded outputs, linked template or parameters URIs, and failure state metadata
- that App Service and Function App settings expose plain-text or Key Vault-backed configuration paths
- that managed-identity token surfaces correlate across web workloads, VMs, and deployment history

What only the lab can confirm once infrastructure exists and behavior is exercised:

- whether RBAC visibility is sufficient for AzureFox to pull the intended service principals into `role-trusts`
- whether the proof trust edges survive deployment and show up as expected in a live tenant
- whether AzureFox wording drifts beyond what the metadata actually proves
- whether `tokens-credentials` still includes an identity-bearing web workload when no env-var rows exist for that workload
- whether the composed `resource-trusts` path stays aligned with the storage plus Key Vault live objects
- whether the Key Vault purge-protection finding stays out of `resource-trusts`

What this phase does not attempt to prove:

- live federated token exchange from an external issuer
- delegated OAuth consent paths exercised through real sign-in flows
- tenant-wide auth-policy enforcement outcomes such as Conditional Access behavior at sign-in time
- actual Key Vault secret retrieval through a running workload
- live IMDS or managed-identity token exchange from the workloads themselves
- private endpoint reachability from inside the virtual network

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
