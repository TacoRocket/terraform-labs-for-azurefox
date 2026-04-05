# Phase 4 Command Discovery Checkpoint

Date: 2026-04-05

This note records the separate Phase 4 / AzureFox `v1.2.0` live capture that was taken while the
lab was already deployed for the Phase 3.5 parity run.

Artifact root:

- `/tmp/terraform-labs-phase4-discovery-20260405`

Commands captured:

- `snapshots-disks`
- `lighthouse`
- `cross-tenant`
- `automation`
- `devops`

## What The Current Live Lab Already Shows

### `snapshots-disks`

- current lab exposes one attached managed OS disk for `vm-web-01`
- live output surfaced readable disk posture including:
  `attachment_state=attached`
  `network_access_policy=AllowAll`
  `public_network_access=Enabled`
  `encryption_type=EncryptionAtRestWithPlatformKey`

### `cross-tenant`

- current tenant produced 238 `cross_tenant_paths`
- the output includes tenant-level policy posture plus readable external service-principal paths
- one partial-read issue appeared for `auth_policies.security_defaults` with `403 Forbidden`

### `lighthouse`

- live command completed cleanly with zero delegations

### `automation`

- live command completed cleanly with zero automation accounts

### `devops`

- live command completed with zero pipelines because no Azure DevOps organization was configured
- issue surfaced as:
  `Azure DevOps organization not configured; rerun with --devops-organization or set AZUREFOX_DEVOPS_ORG.`

## What This Means For The Sister Repo

- `snapshots-disks` is the cleanest current Phase 4 proof surface because the lab already deploys a
  VM-backed managed disk that AzureFox can read deterministically
- that makes `snapshots-disks` the first Phase 4 command worth promoting into the sister-repo
  validator boundary
- `cross-tenant` can be captured from the live tenant today, but its shape depends on tenant
  posture and Graph permissions, so it should stay evidence-led rather than release-blocking until
  the desired assertion boundary is defined
- `lighthouse`, `automation`, and `devops` currently prove command execution paths, not resource
  depth, because the lab does not yet deploy deterministic objects for them

## Next Promotion Rule

Only move a Phase 4 command into the sister-repo validator boundary when at least one of these is
true:

- the current lab already exposes a stable, deterministic proof object for that command
- or a separate infra slice deliberately adds that proof object without expanding unrelated scope

For the current live run, keep most of Phase 4 as a captured reference lane. Promote only
`snapshots-disks` into the validator boundary for now, and leave the rest outside the Phase 3.5
release gate until the lab owns deterministic proof for them.
