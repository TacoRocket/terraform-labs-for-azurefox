# Phase 2 Secrets, Config, and Resource Trust Checkpoint

Date: 2026-03-31

This file records the sister-repo catch-up boundary for the AzureFox Phase 2 milestone.

## Phase 2 Slices That Landed In AzureFox

- `keyvault`
- `resource-trusts`
- `arm-deployments`
- `env-vars`
- `tokens-credentials`

## What The Lab Needs To Add

### `keyvault`

- one Key Vault with `publicNetworkAccess=Enabled`, firewall default action `Allow`, and no
  private endpoint
- one Key Vault with `publicNetworkAccess=Enabled`, firewall default action `Deny`, and no
  private endpoint
- one Key Vault with `publicNetworkAccess=Enabled` and a private endpoint present
- one Key Vault with `publicNetworkAccess=Disabled` and a private endpoint present
- one vault with purge protection disabled so the `keyvault` command still exercises its
  recovery-control finding without leaking that finding into `resource-trusts`

### `resource-trusts`

- reuse the Phase 2 storage and Key Vault objects so this command is validated through the same
  composed path AzureFox now uses live
- validate:
  `anonymous-blob-access`
  `public-network-default`
  `public-network` for Key Vault
  `private-endpoint` for both Storage and Key Vault
- keep `resource-trusts` focused on trust-relevant exposure findings only

### `arm-deployments`

- one subscription-scope deployment with:
  output values recorded
  a linked template URI
- one resource-group deployment with:
  output values recorded
  a linked parameters URI
- one failed resource-group deployment with no outputs

### `env-vars`

- one App Service with a system-assigned identity and a plain-text sensitive setting
- one Function App with both system-assigned and user-assigned identity
- one Key Vault-backed app setting that uses `keyVaultReferenceIdentity`
- one workload identity-bearing web app with no meaningful app settings so `tokens-credentials`
  can prove that managed-identity workload coverage no longer depends on env-var rows existing

### `tokens-credentials`

- validate the Phase 2 correlation outputs rather than building a separate lab-only interpretation
- expected surface families:
  plain-text credential-like app settings
  Key Vault-backed settings
  web workload managed-identity token paths
  VM IMDS token-minting paths
  deployment outputs
  linked deployment content

## What AzureFox Can Prove Directly

- Key Vault public-network posture, private endpoint presence, RBAC mode, and purge-protection
  posture from management-plane metadata
- Storage public-access, firewall default action, and private endpoint posture
- deployment history metadata such as scope, state, output counts, and linked template or
  parameter URIs
- App Service and Function App setting names, value classification, workload identity context, and
  Key Vault reference targets
- token or credential surface correlation from readable metadata across workloads, deployments, and
  existing VM identity context

## What Only The Lab Can Confirm

- the intended Key Vault and deployment proof objects exist live and AzureFox surfaces them with
  the same narrow wording used in fixtures
- `tokens-credentials` still reports identity-bearing web workloads even when app settings are
  empty or otherwise absent from the payload
- the composed `resource-trusts` path stays aligned with the underlying `storage` and `keyvault`
  outputs in a real subscription
- table-mode wording still stays operator-first once real artifact sets are generated

## What This Phase Still Does Not Prove

- actual Key Vault secret value readability
- live IMDS or managed-identity token exchange
- secret retrieval through a running workload
- deployment output sensitivity beyond the fact that output values were recorded
- private endpoint end-to-end reachability proof

## Validator / Manifest Follow-Up

- extend `validation_manifest` with a Phase 2 checkpoint section
- include explicit Phase 2 command coverage for:
  `keyvault`
  `resource-trusts`
  `arm-deployments`
  `env-vars`
  `tokens-credentials`
- add validation for:
  `all-checks --section config`
  `all-checks --section secrets`
  `all-checks --section resource`
- add assertions that:
  `tokens-credentials` includes a managed-identity web workload even when no env-var rows carry
  that workload
  `tokens-credentials` finding ids remain unique per surface
  `resource-trusts` includes the `kvlabdeny01` and `kvlabhybrid01` style Key Vault trust rows
  `resource-trusts` does not emit the Key Vault purge-protection finding

## Recommended Sister-Repo Next Actions

- add the Phase 2 Key Vault objects first because both `keyvault` and `resource-trusts` depend on
  them
- add deployment-history proof objects next
- add App Service / Function App config proof objects, including the identity-bearing empty-settings
  workload
- extend `validation_manifest`
- extend `validate_azurefox_lab.py`
- add a Phase 2 proof-artifact summary alongside the existing Phase 1 checkpoint outputs
