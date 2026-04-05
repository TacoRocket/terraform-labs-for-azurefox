# Release Process

## Versioning

Use the exact same semantic version (`MAJOR.MINOR.PATCH`) as AzureFox for repository releases and
Git tags.

This repo is infrastructure and validation content rather than an installable package, so the lab's
`VERSION` file and Git tag are the release version of record.

Version alignment rule:

- if AzureFox releases as `X.Y.Z`, the matching lab release should also be `X.Y.Z`
- mirror AzureFox's exact version number, not just its versioning scheme
- do not invent a separate lab-only semver track unless the team explicitly changes that policy
- if the lab is not ready for the matching AzureFox release, leave it unreleased rather than
  drifting to a different version number

Current release boundary:

- the current lab release candidate aligns to AzureFox `1.1.0` Phase 3.5 parity
- the repo's `full` validator now matches that standalone release gate directly
- Phase 4 / `1.2.0` outputs can be captured during the same live run, but they remain discovery
  work here unless the lab shape, validator assertions, and docs are deliberately promoted
- broader PostgreSQL relational parity remains an AzureFox main-repo fix item rather than a reason
  to overclaim this lab release
- treat this lab as a v1 artifact, not a `0.x` preview line

## Release Goals

A release should give AzureFox operators a repeatable way to:

- deploy the lab into a disposable subscription
- validate the intended AzureFox command coverage against live infrastructure
- collect proof artifacts with wording that stays evidence-based
- tear the environment down without leaving confusing workflow gaps

The repo is intentionally manual. A good release should make that manual workflow understandable and
reliable, not try to hide it behind thin automation that obscures what is being validated.

## Steps

1. Update `VERSION` and `CHANGELOG.md`.
   Set `VERSION` to the AzureFox release version this lab release is meant to track.
   Capture the operator-visible changes since the last tag:
   lab shape changes, validator behavior, manifest changes, proof-artifact changes, cost or quota
   notes, and any known release caveats.
2. Confirm documentation matches reality.
   Re-read `README.md`, `docs/release-readiness-checklist.md`, and the current checkpoint docs so the
   repo does not ship with stale coverage claims.
3. Run repo-local checks.
   At minimum:
   ```bash
   tofu fmt -check
   python3 -c "from pathlib import Path; compile(Path('scripts/validate_azurefox_lab.py').read_text(encoding='utf-8'), 'scripts/validate_azurefox_lab.py', 'exec')"
   python3 scripts/validate_azurefox_lab.py --help
   ```
4. Run deployment validation against a disposable subscription.
   The release candidate should be exercised with:
   ```bash
   tofu init
   tofu plan
   tofu apply
   python3 scripts/validate_azurefox_lab.py --mode full
   tofu destroy
   ```
   After `tofu destroy`, verify in Azure that the tagged lab footprint is actually gone before you
   call teardown complete:
   ```bash
   az group list --query "[?tags.project=='azurefox-proof-lab'].{name:name,location:location,provisioningState:properties.provisioningState}" -o json
   az resource list --tag project=azurefox-proof-lab --query "[].{name:name,type:type,group:resourceGroup,location:location}" -o json
   ```
   Do not rely on local destroy output alone when deciding that the subscription is clean.
   If the lab is already deployed and you only changed outputs, manifest assumptions, or validator
   logic, run `tofu apply -refresh-only` before rerunning validation so the current
   `validation_manifest` output is recorded in state.
   If `role-trusts` has already been baseline-validated for the current phase and you did not touch
   that slice, reruns may use `--skip-command role-trusts` to avoid paying the known slow Azure API
   cost again.
   Apply the same judgment to any other known slow path: do not rerun it automatically unless the
   changed slice touches that surface, a blocker points back to it, or the team explicitly agrees
   the extra proof is worth the runtime.
5. Review proof artifacts before release.
   Check the generated `summary.json`, `summary.txt`, mismatch reports, follow-up items, and command
   payloads for wording drift or unexpected live-tenant behavior.
6. Reconfirm quota and cost assumptions.
   Validate that the documented fallback SKUs and region guidance still reflect what the team
   actually needed for deployment.
7. Tag the release.
   ```bash
   test "$(cat VERSION)" = "<version>"
   git tag v<version>
   git push origin v<version>
   ```

## Release Notes Guidance

Release notes should answer:

- what AzureFox coverage this lab release validates
- what changed in the infrastructure shape or manifest assumptions
- what changed in the validator or artifact layout
- what operators should watch for around subscription quotas, regions, and runtime length
- how teardown was verified from Azure rather than inferred from local OpenTofu output alone
- where the workflow is intentionally manual and what judgment the operator is still expected to apply
- what known gaps still remain intentionally out of scope

## What Should Block A Release

Do not cut a release if:

- `README.md` makes claims the current OpenTofu lab or validator no longer supports
- the validator only passes because assertions were weakened instead of evidence being corrected
- quota workarounds are required but undocumented
- the live proof run produces unexplained mismatches or unstable artifact paths
- AzureFox command coverage in the repo docs no longer matches the actual lab footprint
