# Phase 3.5 Compute, Apps, Network, and DNS Checkpoint

Date: 2026-04-05

This file records the sister-repo catch-up boundary for the AzureFox `v1.1.0` Phase 3.5 release.

The lab already proves the original end-of-Phase-3 breadth. The current catch-up target is the
Phase 3.5 follow-on depth that AzureFox shipped inside:

- `storage`
- `dns`
- `api-mgmt`
- `aks`
- `acr`
- `databases`

This checkpoint is intentionally narrower than current AzureFox `main`.

- Immediate parity target: released AzureFox `v1.1.0`
- Do not block this checkpoint on later Phase 4 and `1.2.0` work
- Separate live-capture note for the current Phase 4 command lane:
  `docs/phase4-command-discovery-checkpoint.md`

## Catch-Up Execution Lanes

Keep the lab work split by whether live Azure is actually needed.

### No-Azure Lane

- compare the shipped AzureFox command depth against the current lab manifest and validator
- restate the proof target in repo docs before changing release alignment
- queue release/version edits separately so minor doc or validator work does not force an Azure run

### Azure Discovery Lane

- deploy the current lab shape once and capture the current AzureFox `v1.1.0`-boundary evidence
- answer one question first: which grounded depth cues already exist in the current lab without new
  OpenTofu objects?

### No-Azure Implementation Lane

- update `validation_manifest`, validator assertions, and checkpoint wording for every depth cue the
  current live lab already proves

### Azure Gap Lane

- only add new OpenTofu objects when the discovery pass shows a real parity gap
- keep those changes isolated so infra-required work does not block unrelated repo maintenance

### Azure Final-Proof Lane

- rerun the deployed lab against AzureFox once the catch-up slice is implemented
- use that final run for proof artifacts and release readiness, not for exploratory discovery

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

## Phase 3.5 Target Boundary

The `v1.1.0` catch-up extends the original Phase 3 boundary into Phase 3.5 in these specific ways.

### `storage`

Keep the existing two-account proof shape and validate the grounded management-plane depth AzureFox
now ships:

- `public_network_access`
- `allow_shared_key_access`
- transport hardening such as `https_only` and `min_tls_version`
- service-shape cues such as `is_hns_enabled`, `is_sftp_enabled`, and other readable endpoint or
  protocol posture

Do not turn this into blob, container, queue, or file-share enumeration.

### `dns`

Keep DNS at namespace-usage depth rather than record analysis.

- preserve public-zone name-server and record-count proof
- preserve private-zone virtual-network link and registration-link proof
- add private-endpoint-backed namespace cues such as `private_endpoint_reference_count` when the
  lab exposes them

Do not turn this into record export, live resolution testing, or takeover heuristics.

### `api-mgmt`

Extend APIM proof beyond the basic census:

- subscription counts and active-state cues
- API subscription-required counts
- named-value total, secret-marked, and Key Vault-backed counts
- backend destination host visibility

Do not treat this as proof of backend reachability or secret retrieval.

### `aks`

Extend AKS proof with Azure-side cluster depth:

- `oidc_issuer_enabled`
- `workload_identity_enabled`
- readable addon and ingress-profile cues such as `addon_names`

Do not cross into kubeconfig, pod, service, or other in-cluster collection.

### `acr`

Extend ACR proof with automation and governance depth:

- webhook counts, enabled-webhook counts, and broad-scope cues
- replication counts and region context
- quarantine, retention, and trust-policy posture when readable

Do not widen this into repository, tag, or image enumeration.

### `databases`

Keep Azure SQL proof in place, but treat grounded parity as cross-engine relational triage:

- Azure SQL remains part of the proof base
- PostgreSQL Flexible Server and MySQL Flexible Server should be included if the live lab shape
  actually exposes them
- if the current lab does not deploy those engines yet, record that honestly as a gap to close in a
  separate infra slice rather than claiming full parity early

## What The Lab Needs To Add

### Shared Network / Workload Proof

- keep the existing public VM, VMSS, App Services, and Function App as the deployed workload base
- add one explicit NSG allow rule on the workload subnet so `network-ports` has narrow, readable ingress evidence for the public VM
- validate:
  `nics` attachment plus public-IP reference
  `endpoints` public IP plus Azure-managed hostname visibility
  `network-ports` NSG-backed public port evidence
  `workloads` joined VM plus web census without overstating current VMSS coverage

### Web / App Proof

- reuse the existing App Service and Function App proof workloads from Phase 2
- make public-network and TLS posture explicit in OpenTofu so `app-services` and `functions` stay deterministic
- keep Azure-managed hostname output evidence-based rather than treating it as proven live ingress

### Service-Specific Resource Proof

- one API Management service with management-plane inventory counts, subscription cues, named-value
  depth, and backend-host visibility
- one AKS cluster with a visible control-plane FQDN, cluster identity, and readable OIDC,
  workload-identity, or addon cues
- one ACR registry with a visible login server, public auth posture, and readable webhook,
  replication, and policy cues
- one Azure SQL server with at least one visible user database
- separate relational-engine proof only if live discovery shows PostgreSQL or MySQL parity needs new
  OpenTofu objects

### DNS Phase 3.5 Proof

- one public DNS zone with visible Azure name servers
- one private DNS zone with a registration-enabled virtual-network link
- keep DNS proof at zone and namespace-usage metadata only:
  record-set totals from zone metadata
  public-zone delegation count
  private-zone linked-VNet and registration-link counts
  private-endpoint reference counts when the zone-group path is readable

## What AzureFox Can Prove Directly

- NIC attachment, IP context, and public-IP references from control-plane network metadata
- public IP visibility and Azure-managed default hostnames as visible endpoint paths
- NSG allow-rule evidence for NIC-backed public exposure
- joined workload identity and endpoint context across compute and web assets
- App Service and Function App runtime, hostname, identity, and posture metadata
- API Management, AKS, ACR, and relational-database inventory and posture metadata
- DNS zone inventory, public delegation counts, private-zone VNet-link counts, and private-endpoint
  reference counts when readable

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
- storage object names, data-plane ACLs, SAS material, or key retrieval

## Validator / Manifest Follow-Up

- extend `validation_manifest` with Phase 3.5 expectations rather than only the original
  breadth checkpoint
- include explicit Phase 3 command coverage for:
  `storage`
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

## Live Discovery Checklist

Use the first Azure run to answer these questions before adding infrastructure:

- does `storage` already expose the public/private split plus shared-key, TLS, and service-shape
  cues in the current lab deployment?
- does `dns` already surface private-endpoint reference counts for the current private zone?
- does `api-mgmt` already surface subscription counts, named-value secret counts, Key Vault-backed
  named values, and backend hostnames from the current service shape?
- does `aks` already surface OIDC, workload-identity, or addon cues from the current cluster?
- does `acr` already surface webhook, replication, retention, and trust-policy posture from the
  current registry?
- does `databases` still prove only Azure SQL, or do we need a separate infra slice for PostgreSQL
  Flexible Server and MySQL Flexible Server parity?

## Known Live-Proof Gaps To Track

- local AzureFox checkout drift can invalidate Phase 3 validation if it is behind `main`, especially for `dns`
- sibling-repo proof should stay narrow if Azure control-plane defaults differ from the intended posture
- any live drift between manifest claims and actual Azure output should be treated as a sister-repo fix item, not silently accepted
