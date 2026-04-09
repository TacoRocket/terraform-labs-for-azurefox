#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull Azure Activity Log events for a lab run window and package them locally."
    )
    parser.add_argument(
        "--subscription",
        default=None,
        help="Subscription ID to query. Defaults to the current Azure CLI subscription.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Stable label for this bundle. Defaults to a UTC timestamp-based ID.",
    )
    parser.add_argument(
        "--start-time",
        default=None,
        help="Run window start in ISO 8601 / Azure CLI time format.",
    )
    parser.add_argument(
        "--end-time",
        default=None,
        help="Run window end in ISO 8601 / Azure CLI time format.",
    )
    parser.add_argument(
        "--phase",
        action="append",
        default=[],
        metavar="NAME=TIMESTAMP",
        help="Optional phase marker to store in the timeline, for example apply_start=2026-04-09T01:00:00Z.",
    )
    parser.add_argument(
        "--window-file",
        type=Path,
        default=None,
        help="Optional JSON file containing run-window fields. If supplied, start/end come from the file unless explicitly overridden.",
    )
    parser.add_argument(
        "--command-timeline-file",
        type=Path,
        default=None,
        help="Optional command-timeline.json emitted by validate_azurefox_lab.py. If supplied, it will be copied into the bundle and rendered in timeline.md.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("proof-artifacts") / "activity-log",
        help="Directory where the bundle directory will be created.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=5000,
        help="Maximum number of Activity Log events to request from Azure CLI.",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Leave the bundle as a directory only and skip writing a zip archive.",
    )
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(UTC)


def default_run_id() -> str:
    return utc_now().strftime("activity-%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Window file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Window file is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Window file must contain a JSON object: {path}")
    return value


def load_command_timeline(path: Path) -> dict[str, Any]:
    value = load_json(path)
    command_runs = value.get("command_runs")
    if not isinstance(command_runs, list):
        raise SystemExit(f"Command timeline file is missing a command_runs list: {path}")
    return value


def parse_phase_markers(items: list[str]) -> dict[str, str]:
    markers: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"Invalid --phase value '{item}'. Use NAME=TIMESTAMP.")
        name, value = item.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or not value:
            raise SystemExit(f"Invalid --phase value '{item}'. Use NAME=TIMESTAMP.")
        markers[name] = value
    return markers


def normalize_window(args: argparse.Namespace) -> dict[str, Any]:
    window = load_json(args.window_file) if args.window_file else {}
    run_id = args.run_id or str(window.get("run_id") or default_run_id())
    start_time = args.start_time or window.get("start_utc") or window.get("start_time")
    end_time = args.end_time or window.get("end_utc") or window.get("end_time")
    if not start_time or not end_time:
        raise SystemExit("Provide --start-time and --end-time, or a --window-file with start/end fields.")

    phases = parse_phase_markers(args.phase)
    if not phases:
        for key, value in window.items():
            if key in {"run_id", "start_utc", "start_time", "end_utc", "end_time"}:
                continue
            if key.endswith("_utc") and isinstance(value, str):
                phases[key.removesuffix("_utc")] = value

    normalized = {
        "run_id": run_id,
        "start_utc": start_time,
        "end_utc": end_time,
    }
    for name, value in sorted(phases.items()):
        normalized[f"{name}_utc"] = value
    return normalized


def run_json(cmd: list[str]) -> Any:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Command did not return JSON: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}"
        ) from exc


def current_subscription_id() -> str:
    payload = run_json(["az", "account", "show", "--output", "json", "--only-show-errors"])
    subscription_id = payload.get("id")
    if not subscription_id:
        raise SystemExit("Azure CLI did not return a current subscription id.")
    return str(subscription_id)


def fetch_activity_log(
    *,
    subscription_id: str,
    start_time: str,
    end_time: str,
    max_events: int,
) -> list[dict[str, Any]]:
    payload = run_json(
        [
            "az",
            "monitor",
            "activity-log",
            "list",
            "--subscription",
            subscription_id,
            "--start-time",
            start_time,
            "--end-time",
            end_time,
            "--max-events",
            str(max_events),
            "--output",
            "json",
            "--only-show-errors",
        ]
    )
    if not isinstance(payload, list):
        raise SystemExit("Azure CLI returned a non-list payload for Activity Log query.")
    return payload


def parse_timestamp(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def build_timeline(
    window: dict[str, Any],
    *,
    event_count: int,
    max_events: int,
    subscription_id: str,
    command_timeline: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# Azure Activity Log Timeline",
        "",
        f"- run_id: `{window['run_id']}`",
        f"- subscription_id: `{subscription_id}`",
        f"- start_utc: `{window['start_utc']}`",
        f"- end_utc: `{window['end_utc']}`",
        f"- activity_log_event_count: `{event_count}`",
        f"- activity_log_max_events: `{max_events}`",
        "",
        "## Phase Markers",
        "",
    ]

    marker_items: list[tuple[str, str]] = []
    for key, value in window.items():
        if key in {"run_id", "start_utc", "end_utc"}:
            continue
        if key.endswith("_utc") and isinstance(value, str):
            marker_items.append((key.removesuffix("_utc"), value))
    marker_items.sort(key=lambda item: (parse_timestamp(item[1]) or datetime.max, item[0]))

    if marker_items:
        for name, value in marker_items:
            lines.append(f"- `{name}` at `{value}`")
    else:
        lines.append("- No additional phase markers were provided.")

    lines.extend(
        [
            "",
            "## AzureFox Command Markers",
            "",
        ]
    )

    if command_timeline:
        command_runs = command_timeline.get("command_runs", [])
        if command_runs:
            for item in command_runs:
                command = item.get("command", "unknown")
                sequence = item.get("sequence")
                started_at = item.get("started_at_utc", "unknown")
                finished_at = item.get("finished_at_utc", "unknown")
                duration = item.get("duration_seconds")
                status = item.get("status", "unknown")
                duration_text = (
                    f"{duration:.3f}s"
                    if isinstance(duration, (int, float))
                    else str(duration or "unknown")
                )
                prefix = f"[{sequence:02d}] " if isinstance(sequence, int) else ""
                lines.append(
                    f"- {prefix}`{command}` started `{started_at}`, finished `{finished_at}`, "
                    f"duration `{duration_text}`, status `{status}`"
                )
        else:
            lines.append("- Command timeline file was supplied, but it did not contain any command runs.")
    else:
        lines.append("- No AzureFox command timeline was supplied for this bundle.")

    lines.extend(
        [
            "",
            "## Analyst Note",
            "",
            "Correlate the phase markers and command markers above with `eventTimestamp`,",
            "`operationName`, `resourceGroupName`, and `resourceId` fields in",
            "`azure-activity-log.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_bundle(
    *,
    bundle_dir: Path,
    window: dict[str, Any],
    subscription_id: str,
    activity_log: list[dict[str, Any]],
    max_events: int,
    command_timeline: dict[str, Any] | None,
    zip_bundle: bool,
) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "bundle_generated_at_utc": utc_now().isoformat().replace("+00:00", "Z"),
        "command_timeline_count": len((command_timeline or {}).get("command_runs", [])),
        "command_timeline_included": command_timeline is not None,
        "subscription_id": subscription_id,
        "activity_log_event_count": len(activity_log),
        "activity_log_max_events": max_events,
        "source": "az monitor activity-log list",
    }
    (bundle_dir / "run-window.json").write_text(
        json.dumps(window, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "azure-activity-log.json").write_text(
        json.dumps(activity_log, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if command_timeline is not None:
        (bundle_dir / "command-timeline.json").write_text(
            json.dumps(command_timeline, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (bundle_dir / "timeline.md").write_text(
        build_timeline(
            window,
            event_count=len(activity_log),
            max_events=max_events,
            subscription_id=subscription_id,
            command_timeline=command_timeline,
        )
        + "\n",
        encoding="utf-8",
    )

    if not zip_bundle:
        return

    zip_path = bundle_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(bundle_dir.iterdir()):
            archive.write(file_path, arcname=file_path.name)


def main() -> int:
    args = parse_args()
    window = normalize_window(args)
    subscription_id = args.subscription or current_subscription_id()
    bundle_dir = (args.output_root / window["run_id"]).resolve()
    command_timeline = (
        load_command_timeline(args.command_timeline_file.resolve())
        if args.command_timeline_file is not None
        else None
    )
    activity_log = fetch_activity_log(
        subscription_id=subscription_id,
        start_time=window["start_utc"],
        end_time=window["end_utc"],
        max_events=args.max_events,
    )
    write_bundle(
        bundle_dir=bundle_dir,
        window=window,
        subscription_id=subscription_id,
        activity_log=activity_log,
        max_events=args.max_events,
        command_timeline=command_timeline,
        zip_bundle=not args.no_zip,
    )
    print(f"Activity log bundle written to {bundle_dir}")
    if not args.no_zip:
        print(f"Zip archive written to {bundle_dir.with_suffix('.zip')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
