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

- `validation_manifest` still matches the OpenTofu-produced lab shape.
- `scripts/validate_azurefox_lab.py` still validates the intended AzureFox command set.
- `--mode full`, `--mode commands-only`, and `--viewpoint admin|dev|lower-privilege|all` all behave as documented.
- `--mode full` remains the single end-to-end validation gate for release readiness.
- `--mode commands-only` is only an explicit standalone rerun alias rather than a separate release gate.
- reduced viewpoints still prove honest partial visibility from the same shared lab instead of being treated as empty-state failures.
- proof artifacts are written deterministically enough for operator review.
- mismatch and follow-up reports stay evidence-based instead of normalizing live drift.
- tenant-shaped or external-config-shaped commands stay honest about their limits:
  `cross-tenant` and `lighthouse` remain evidence-led, while `devops` either uses a real Azure DevOps organization or records the expected missing-organization issue clearly.
- the docs do not claim current AzureFox still supports `all-checks`; grouped follow-up is described truthfully through `chains` instead.

## Live Run Readiness

- `tofu init`, `tofu plan`, and `tofu apply` succeed in a disposable subscription.
- `python3 scripts/validate_azurefox_lab.py --mode full` completes successfully against the applied
  environment.
- `python3 scripts/validate_azurefox_lab.py --mode commands-only --viewpoint all` completes successfully against the applied environment and writes separate `admin`, `dev`, and `lower-privilege` artifact folders.
- the operator followed [live-run-strategy.md](/Users/cfarley/Documents/Terraform Labs for AzureFox/docs/live-run-strategy.md)
  so Key Vault replacement and `role-trusts` waits were treated as known slow paths instead of ad
  hoc failures.
- proof artifacts were reviewed after the live run and do not show unexplained drift.
- `tofu destroy` succeeds cleanly after validation.
- Azure API checks confirm that tagged lab resource groups and resources are actually gone after
  destroy; do not infer teardown success from local OpenTofu output alone.

## Release Notes Readiness

- the release notes call out lab-shape changes, validator changes, and any operator-visible caveats.
- cost, quota, region, and runtime expectations are current.
- the release notes state where operator judgment and manual inspection are still expected.
- known live-proof gaps are documented rather than silently accepted.

## Ship / No-Ship Rule

If any item above is unclear, treat that as a release-prep task, not as a release-time judgment
call.
