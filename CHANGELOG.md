# Changelog

All notable changes to this lab repo should be recorded here.

The format is intentionally lightweight and release-oriented. Keep entries focused on what changed
for operators, validation coverage, and release risk rather than commit-by-commit history.

Lab releases should mirror AzureFox's exact release number. The current lab version of record is
stored in `VERSION`.

## [Unreleased]

### Changed

- retired the removed AzureFox `all-checks` path from the lab validator and current operator docs
  so live runs no longer assume a grouped command that AzureFox `main` rejects as of April 8, 2026
- documented an explicit live-run strategy for known slow paths, including Key Vault soft-delete
  waits during OpenTofu apply and `role-trusts` latency during AzureFox validation
- added a lab-side Azure Activity Log bundle script and doc so SOC-style local log pulls can be
  packaged with run-window phase markers without introducing a separate Azure logging backend
- added validator-emitted `command-timeline.json` artifacts plus bundle-export support so SOC
  analysts can line AzureFox command start and finish times up with raw Azure Activity Log windows

## [1.2.0] - 2026-04-05

### Added

- one Azure Automation account with a system-assigned identity so the lab now owns a deterministic
  Phase 4 `automation` proof surface instead of only validating zero-account execution

### Changed

- promoted `automation`, `devops`, `lighthouse`, and `cross-tenant` into the standalone validator
  path with truth-preserving checks that distinguish deterministic proof from tenant-shaped or
  external-config-shaped command behavior
- promoted `vmss` into the standalone validator path because the current lab already deploys a
  stable internal VM scale set that AzureFox can read deterministically
- expanded `all-checks` validator coverage to include the current `storage` section and the newer
  `lighthouse`, `automation`, `devops`, `vmss`, and `snapshots-disks` command membership reflected
  in the main AzureFox repo
- updated repo docs and release language to target AzureFox `1.2.0` / Phase 4 parity instead of
  leaving Phase 4 described as mostly discovery-only work
- tightened the documented truth boundary for external or tenant-shaped surfaces:
  `cross-tenant` and `lighthouse` stay evidence-led, while `devops` requires a real Azure DevOps
  organization for pipeline proof and otherwise should surface the expected configuration issue

## [1.1.0] - 2026-04-05

### Added

- Phase 3.5 checkpoint note for the AzureFox `1.1.0` release boundary:
  [phase3-compute-apps-network-checkpoint-2026-04-08.md](/Users/cfarley/Documents/AzureFox-reference/terraform-labs/phase3-compute-apps-network-checkpoint-2026-04-08.md)
- Phase 4 live-capture note for the AzureFox `1.2.0` command lane:
  [phase4-command-discovery-checkpoint-2026-04-08.md](/Users/cfarley/Documents/AzureFox-reference/terraform-labs/phase4-command-discovery-checkpoint-2026-04-08.md)

### Changed

- expanded the validation manifest and validator assertions for the current live AzureFox Phase 3.5
  depth now surfaced by `storage`, `dns`, `api-mgmt`, `aks`, `acr`, and `databases`
- promoted `snapshots-disks` as the first deterministic Phase 4 validator surface because the
  current lab already deploys a readable VM-backed managed disk
- updated release-process and README wording to describe the current catch-up boundary truthfully
- changed validator `full` mode so it no longer bundles `all-checks`; wrapper coverage now remains
  a separate `all-checks-only` decision
- added heartbeat progress output for slow validator subprocesses so known long Azure API paths such
  as `role-trusts` no longer look hung during live runs
- added `--skip-command role-trusts` for reruns after the initial baseline validation of that slow
  command
- documented that known slow validation paths should be rerun only when the changed slice or a live
  blocker justifies the extra runtime
- documented the `tofu apply -refresh-only` rerun path for output-only manifest changes on an
  already-deployed lab
- documented that teardown is not complete until Azure API checks confirm the tagged lab footprint
  is actually gone
- recorded the current release caveat honestly: Azure SQL-backed `databases` proof is release-ready
  here, while broader PostgreSQL parity still depends on an AzureFox main-repo collector fix

## [1.0.0] - TBD

Initial public release of the AzureFox OpenTofu proof lab.
