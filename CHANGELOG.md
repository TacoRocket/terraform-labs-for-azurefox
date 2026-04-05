# Changelog

All notable changes to this lab repo should be recorded here.

The format is intentionally lightweight and release-oriented. Keep entries focused on what changed
for operators, validation coverage, and release risk rather than commit-by-commit history.

Lab releases should mirror AzureFox's exact release number. The current lab version of record is
stored in `VERSION`.

## [Unreleased]

No unreleased entries yet.

## [1.1.0] - 2026-04-05

### Added

- Phase 3.5 checkpoint note for the AzureFox `1.1.0` release boundary:
  `docs/phase3-compute-apps-network-checkpoint.md`
- Phase 4 live-capture note for the AzureFox `1.2.0` command lane:
  `docs/phase4-command-discovery-checkpoint.md`

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
