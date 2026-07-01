#!/usr/bin/env python3
"""
Compact a K8NTEXT audit log by collapsing large temporal gaps.

Reads a JSONL log file and, whenever the gap between two consecutive lines
exceeds a threshold, shifts all subsequent timestamps backwards so that the
gap becomes approximately the target gap.  Shifts are cumulative, so multiple
large gaps in the original log are all compressed.

Both `requestReceivedTimestamp` and `stageTimestamp` are shifted by the same
amount so that their relative offset is preserved.

NOTE: This script is purely meant to make logs more compact for easier viewing.
It SHOULD NOT be used when actual logs need to be preserved for auditing purposes,
or when the original timestamps are important for analysis.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

DEFAULT_TIMESTAMP_KEY = "requestReceivedTimestamp"
DEFAULT_STAGE_TIMESTAMP_KEY = "stageTimestamp"
DEFAULT_THRESHOLD_SECONDS = 300  # 5 minutes
DEFAULT_TARGET_GAP_SECONDS = 60  # 1 minute


def _parse_timestamp(ts: str) -> float:
    """Parse an ISO timestamp to seconds since epoch."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(ts).timestamp()


def _format_timestamp(ts: float, original_uses_z: bool) -> str:
    """Format seconds since epoch back to the original timestamp style."""
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    if original_uses_z:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return dt.isoformat()


def compact_log(
    input_path: str,
    output_path: str,
    threshold_seconds: float = DEFAULT_THRESHOLD_SECONDS,
    target_gap_seconds: float = DEFAULT_TARGET_GAP_SECONDS,
    timestamp_key: str = DEFAULT_TIMESTAMP_KEY,
    stage_timestamp_key: str = DEFAULT_STAGE_TIMESTAMP_KEY,
) -> None:
    """
    Compact the log file.

    Args:
        input_path: Path to the input JSONL log.
        output_path: Path to write the compacted JSONL log.
        threshold_seconds: Gaps larger than this trigger a shift.
        target_gap_seconds: Desired gap after shifting.
        timestamp_key: Key for the primary timestamp.
        stage_timestamp_key: Key for the stage timestamp (also shifted).
    """
    if not Path(input_path).exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    cumulative_shift = 0.0
    previous_original_ts: float | None = None
    shifts_applied = 0
    lines_written = 0

    with open(input_path, "r", encoding="utf-8") as infile, \
            open(output_path, "w", encoding="utf-8") as outfile:
        for line_number, raw_line in enumerate(infile, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as e:
                print(f"Warning: skipping malformed line {line_number}: {e}", file=sys.stderr)
                continue

            ts_raw = record.get(timestamp_key)
            if not ts_raw:
                print(f"Warning: line {line_number} missing '{timestamp_key}', skipping", file=sys.stderr)
                continue

            try:
                current_ts = _parse_timestamp(ts_raw)
            except Exception as e:
                print(f"Warning: cannot parse timestamp on line {line_number}: {e}", file=sys.stderr)
                continue

            if previous_original_ts is not None:
                gap = current_ts - previous_original_ts
                if gap > threshold_seconds:
                    shift = gap - target_gap_seconds
                    cumulative_shift += shift
                    shifts_applied += 1

            new_ts = current_ts - cumulative_shift
            record[timestamp_key] = _format_timestamp(new_ts, str(ts_raw).endswith("Z"))

            stage_ts_raw = record.get(stage_timestamp_key)
            if stage_ts_raw:
                try:
                    stage_ts = _parse_timestamp(stage_ts_raw)
                    new_stage_ts = stage_ts - cumulative_shift
                    record[stage_timestamp_key] = _format_timestamp(
                        new_stage_ts, str(stage_ts_raw).endswith("Z")
                    )
                except Exception as e:
                    print(f"Warning: cannot parse stage timestamp on line {line_number}: {e}", file=sys.stderr)

            outfile.write(json.dumps(record, separators=(",", ":")) + "\n")
            lines_written += 1
            previous_original_ts = current_ts

    print(
        f"Compacted {lines_written} lines. "
        f"Applied {shifts_applied} shifts, total cumulative shift: {cumulative_shift:.3f}s "
        f"({cumulative_shift/60:.2f} min)."
    )
    print(f"Output written to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compact a K8NTEXT audit log by collapsing large temporal gaps."
    )
    parser.add_argument("-f", "--file", required=True, help="Input JSONL log file.")
    parser.add_argument("-o", "--output", required=True, help="Output JSONL log file.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD_SECONDS,
        help=f"Gap threshold in seconds that triggers compaction (default: {DEFAULT_THRESHOLD_SECONDS}).",
    )
    parser.add_argument(
        "--target-gap",
        type=float,
        default=DEFAULT_TARGET_GAP_SECONDS,
        help=f"Target gap in seconds after compaction (default: {DEFAULT_TARGET_GAP_SECONDS}).",
    )
    parser.add_argument(
        "--timestamp-key",
        default=DEFAULT_TIMESTAMP_KEY,
        help=f"Key for the primary timestamp (default: {DEFAULT_TIMESTAMP_KEY}).",
    )
    args = parser.parse_args()

    compact_log(
        input_path=args.file,
        output_path=args.output,
        threshold_seconds=args.threshold,
        target_gap_seconds=args.target_gap,
        timestamp_key=args.timestamp_key,
    )


if __name__ == "__main__":
    main()
