# Live Run Strategy

Use this when you are running the lab against a real Azure subscription and want a practical rule
set instead of rediscovering the same slow paths each time.

## Known Slow Paths

- `azurerm_key_vault.open` replacement is a normal Azure slow path.
- Azure Key Vault deletes move through soft-delete before the name is fully reusable, so OpenTofu
  can spend several minutes waiting even after the vault disappears from the active subscription
  view.
- `role-trusts` is a known slow Azure API path during AzureFox validation and can take several
  minutes before JSON returns.

## Release-Candidate Pass

Pay the full slow-path cost once when the goal is a fresh release-candidate baseline:

```bash
tofu init
tofu plan
tofu apply
python3 scripts/validate_azurefox_lab.py --mode full
tofu destroy
```

Keep `proof-artifacts/latest/command-timeline.json` from that validator pass so the same release
candidate run has per-command UTC markers if the SOC later wants the Azure Activity Log window.

Use this full pass when:

- the lab shape changed
- the validator expectations changed in a way that touches the slow slices
- AzureFox changed its output for `keyvault` or `role-trusts`
- you need a new clean baseline for release notes or proof artifacts

## Fast Rerun Strategy

Do not pay every slow-path cost on every rerun.

If the infrastructure is already up and the change did not touch the lab shape:

```bash
tofu apply -refresh-only
python3 scripts/validate_azurefox_lab.py --mode full --skip-command role-trusts
```

Keep the refreshed run's `command-timeline.json` too. It is the quickest way to tell the difference
between a known slow validator command and a run that truly drifted or hung.

Use this faster rerun when:

- you changed validator wording, docs, or artifact handling
- you are rechecking a live mismatch that does not point back to `role-trusts`
- the current state only needs a manifest refresh before validation

## Operational Rules

- Treat Key Vault replacement waits as expected unless they exceed the normal Azure delete/recreate
  window by a wide margin.
- Treat `role-trusts` as skippable on reruns once it has already been validated for the current
  phase.
- Keep the validator's `command-timeline.json` with the same proof artifacts as `summary.json` so
  later SOC bundle exports can show when each AzureFox command actually ran.
- Do not keep stale `all-checks` assumptions in the live-run workflow. Current AzureFox `main`
  removed that grouped command on April 8, 2026; use standalone command validation here and treat
  `chains` as optional grouped follow-up instead.
- If a rerun does not need new Azure infrastructure truth, prefer refresh-only plus validator rerun
  over a full destroy/reapply cycle.
- If the SOC wants a local starter pack for detections, use
  [activity-log-bundles.md](/Users/cfarley/Documents/Terraform Labs for AzureFox/docs/activity-log-bundles.md)
  to package Azure Activity Log plus phase markers and per-command AzureFox markers after the run
  window closes.
