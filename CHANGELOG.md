# Changelog

All notable changes to this lab repo should be recorded here.

The format is intentionally lightweight and release-oriented. Keep entries focused on what changed
for operators, validation coverage, and release risk rather than commit-by-commit history.

Lab releases should mirror AzureFox's exact release number. The current lab version of record is
stored in `VERSION`.

## [Unreleased]

### Added

- initial OpenTofu proof lab for AzureFox live-tenant validation
- validator-driven proof-artifact generation for standalone AzureFox commands and `all-checks`
  section runs
- release preparation docs for the lab environment:
  `docs/release-process.md`
  `docs/release-readiness-checklist.md`

### Changed

- expanded validator execution modes to support `full`, `commands-only`, and
  `all-checks-only`
- documented longer-running validation paths and artifact expectations in the README

## [1.0.0] - TBD

Initial public release of the AzureFox OpenTofu proof lab.
