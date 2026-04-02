# Release Readiness Checklist

Use this before tagging a lab release candidate.

## Repository Readiness

- `VERSION` matches the current AzureFox release number exactly.
- `CHANGELOG.md` summarizes the intended release accurately.
- `README.md` matches the current lab shape, prerequisites, deploy flow, validation flow, and
  destroy flow.
- the docs make it clear that this is a manual, operator-driven test repo rather than a turnkey
  product workflow.
- the current checkpoint docs still describe the real AzureFox coverage boundary.
- `tofu.tfvars.example` remains usable for a fresh operator setup.

## Infrastructure Readiness

- the default location and SKU guidance is still deployable for the team's disposable subscription
  path.
- the lab remains intentionally disposable and does not require production-adjacent exceptions.
- the risky proof posture is still intentional, documented, and narrow:
  public exposure, public blob access, and elevated RBAC are present only for the lab purpose.
- no new tenant-wide Entra mutations were introduced without explicit rollout and rollback notes.

## Validation Readiness

- `validation_manifest` still matches the Terraform-produced lab shape.
- `scripts/validate_azurefox_lab.py` still validates the intended AzureFox command set.
- `--mode full`, `--mode commands-only`, and `--mode all-checks-only` all behave as documented.
- proof artifacts are written deterministically enough for operator review.
- mismatch and follow-up reports stay evidence-based instead of normalizing live drift.

## Live Run Readiness

- `tofu init`, `tofu plan`, and `tofu apply` succeed in a disposable subscription.
- `python3 scripts/validate_azurefox_lab.py --mode full` completes successfully against the applied
  environment.
- proof artifacts were reviewed after the live run and do not show unexplained drift.
- `tofu destroy` succeeds cleanly after validation.

## Release Notes Readiness

- the release notes call out lab-shape changes, validator changes, and any operator-visible caveats.
- cost, quota, region, and runtime expectations are current.
- the release notes state where operator judgment and manual inspection are still expected.
- known live-proof gaps are documented rather than silently accepted.

## Ship / No-Ship Rule

If any item above is unclear, treat that as a release-prep task, not as a release-time judgment
call.
