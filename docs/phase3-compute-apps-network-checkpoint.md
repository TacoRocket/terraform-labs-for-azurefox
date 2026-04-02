# Phase 3 Compute, Apps, Network, and DNS Checkpoint

Date: 2026-04-02

This file records the sister-repo catch-up boundary for the AzureFox Phase 3 milestone.

## Phase 3 Slices That Landed In AzureFox

- `nics`
- `endpoints`
- `network-ports`
- `workloads`
- `app-services`
- `functions`
- `api-mgmt`
- `aks`
- `acr`
- `databases`
- `dns`

## What The Lab Needs To Add

### Shared Network / Workload Proof

- keep the existing public VM, VMSS, App Services, and Function App as the joined workload base
- add one explicit NSG allow rule on the workload subnet so `network-ports` has narrow, readable ingress evidence for the public VM
- validate:
  `nics` attachment plus public-IP reference
  `endpoints` public IP plus Azure-managed hostname visibility
  `network-ports` NSG-backed public port evidence
  `workloads` joined compute plus web census

### Web / App Proof

- reuse the existing App Service and Function App proof workloads from Phase 2
- make public-network and TLS posture explicit in Terraform so `app-services` and `functions` stay deterministic
- keep Azure-managed hostname output evidence-based rather than treating it as proven live ingress

### Service-Specific Resource Proof

- one API Management service with management-plane inventory counts and managed identity visible
- one AKS cluster with a visible control-plane FQDN and cluster identity
- one ACR registry with a visible login server and public auth posture
- one Azure SQL server with at least one visible user database

### DNS V1 Proof

- one public DNS zone with visible Azure name servers
- one private DNS zone with a registration-enabled virtual-network link
- keep DNS proof at zone metadata only:
  record-set totals from zone metadata
  public-zone delegation count
  private-zone linked-VNet and registration-link counts

## What AzureFox Can Prove Directly

- NIC attachment, IP context, and public-IP references from control-plane network metadata
- public IP visibility and Azure-managed default hostnames as visible endpoint paths
- NSG allow-rule evidence for NIC-backed public exposure
- joined workload identity and endpoint context across compute and web assets
- App Service and Function App runtime, hostname, identity, and posture metadata
- API Management, AKS, ACR, and Azure SQL inventory and posture metadata
- DNS zone inventory, public delegation counts, and private-zone VNet-link counts

## What Only The Lab Can Confirm

- the intended Phase 3 proof objects exist live and AzureFox surfaces them in the current JSON shape
- `endpoints` and `workloads` wording stays evidence-based for Azure-managed hostnames
- `network-ports` remains the stronger ingress-evidence surface for NIC-backed public exposure
- compute, network, and resource `all-checks` sections still emit stable artifact sets once run against a real tenant

## What This Phase Still Does Not Prove

- full effective-network reachability analysis
- actual HTTP reachability behind App Service or Function hostname publication
- AKS cluster internals beyond the visible control-plane metadata
- ACR image contents or pull success
- database query access or firewall-behavior proof
- DNS record contents, record targets, live resolution behavior, or takeover heuristics

## Validator / Manifest Follow-Up

- extend `validation_manifest` with a Phase 3 checkpoint section
- include explicit Phase 3 command coverage for:
  `nics`
  `dns`
  `endpoints`
  `network-ports`
  `workloads`
  `app-services`
  `functions`
  `api-mgmt`
  `aks`
  `acr`
  `databases`
- add validation for:
  `all-checks --section network`
  `all-checks --section compute`
  `all-checks --section resource`
- keep the existing Phase 2 assertions in place so catch-up work does not silently regress earlier coverage

## Known Live-Proof Gaps To Track

- local AzureFox checkout drift can invalidate Phase 3 validation if it is behind `main`, especially for `dns`
- sibling-repo proof should stay narrow if Azure control-plane defaults differ from the intended posture
- any live drift between manifest claims and actual Azure output should be treated as a sister-repo fix item, not silently accepted
