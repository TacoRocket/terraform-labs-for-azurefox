# Activity Log Bundles

Use this when you want a local Azure Activity Log bundle for SOC or detection work without sending
anything into a separate Azure logging backend.

The bundle script lives at:

- `scripts/export_activity_log_bundle.py`

It writes a local bundle directory with:

- `run-window.json`
- `metadata.json`
- `timeline.md`
- `azure-activity-log.json`
- `command-timeline.json` if you pass the validator artifact into the exporter
- `<run-id>.zip` unless you pass `--no-zip`

## Minimal Flow

Record UTC timestamps for the infrastructure phases as you move through the lab run:

```bash
START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
APPLY_START_UTC="$START_UTC"
tofu apply
APPLY_END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

VALIDATE_START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 scripts/validate_azurefox_lab.py --mode full
VALIDATE_END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

DESTROY_START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
tofu destroy
DESTROY_END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

The validator now writes `proof-artifacts/latest/command-timeline.json` automatically. That file
captures per-command UTC start and finish markers plus elapsed duration for the AzureFox command
lane, so you no longer need to hand-build those validator markers yourself.

Then export the bundle:

```bash
python3 scripts/export_activity_log_bundle.py \
  --run-id live-20260408 \
  --start-time "$START_UTC" \
  --end-time "$DESTROY_END_UTC" \
  --command-timeline-file proof-artifacts/latest/command-timeline.json \
  --phase apply_start="$APPLY_START_UTC" \
  --phase apply_end="$APPLY_END_UTC" \
  --phase validate_start="$VALIDATE_START_UTC" \
  --phase validate_end="$VALIDATE_END_UTC" \
  --phase destroy_start="$DESTROY_START_UTC" \
  --phase destroy_end="$DESTROY_END_UTC"
```

By default this writes to:

- `proof-artifacts/activity-log/<run-id>/`
- `proof-artifacts/activity-log/<run-id>.zip`

## Notes

- This is local pull-only. It does not require Log Analytics, Event Hub, or Storage export.
- The script uses `az monitor activity-log list`, so it needs a working Azure CLI login.
- The default `--max-events` is `5000`. Raise it if you expect a busier subscription window.
- `scripts/validate_azurefox_lab.py` now writes `proof-artifacts/latest/command-timeline.json`
  automatically so you can hand the exporter a per-command start and finish timeline from the same run.
- `command-timeline.json` only covers the AzureFox validator commands. You still need manual
  `date -u` markers or another wrapper for `tofu apply`, `tofu destroy`, and any other external
  steps you want represented in the bundle window.
- The timeline file is there to help analysts line phase markers and AzureFox command markers up
  with Azure event timestamps and operation names.
