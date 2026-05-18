# macOS-System-Data-Scanner

Read-only Python CLI for scanning common macOS "System Data" hotspots and generating reports you can review yourself or hand to an AI for cleanup advice.

## What it does

- Scans a documented set of macOS paths that often contribute to large "System Data" usage
- Ranks the largest directories and files it can observe
- Classifies findings into categories such as caches, application support data, developer tooling, device backups, communication attachments, and unknown items
- Generates both JSON and Markdown reports from the same aggregated results
- Marks findings with conservative review guidance instead of deleting anything

## Safety boundaries

- The scanner is **read-only**. It never deletes files.
- It does **not** claim to reproduce the exact System Data total shown by macOS Settings.
- Some storage classes, such as APFS local snapshots and purgeable space, are reported as limitations because they are not fully visible through normal filesystem traversal.
- Findings marked `safe-review` are only good candidates for **manual inspection**, not automatic deletion.

## Default scan scope

The CLI scans these locations when they exist:

- `~/Library/Caches`
- `~/Library/Logs`
- `~/Library/Application Support`
- `~/Library/Developer`
- `~/Library/Containers`
- `~/Library/Group Containers`
- `~/Library/Messages`
- `~/Library/Mail`
- `/Library/Caches`
- `/Library/Logs`
- `/private/var/log`

Missing paths are recorded in the report instead of failing the scan.

## Installation

```bash
python3 -m pip install -e .
```

## Usage

```bash
macos-system-data-scanner
```

Or without installing the console script:

```bash
PYTHONPATH=src python3 -m macos_system_data_scanner
```

During the scan, progress is printed for each target in real time:

```
Starting macOS System Data scan...
  Scanning  [user-caches] /Users/you/Library/Caches ...
  ✓ Done     [user-caches]
  Scanning  [app-support] /Users/you/Library/Application Support ...
  ✓ Done     [app-support]
  ...
Generating report...
Scan complete.
JSON report: .../system_scan_report/system-data-report.json
Markdown report: .../system_scan_report/system-data-report.md
```

### Report output location

By default, reports are written to a `system_scan_report/` folder in the **current working directory**:

```
system_scan_report/
├── system-data-report.json
└── system-data-report.md
```

The folder is created automatically if it does not exist.

### Useful options

```bash
PYTHONPATH=src python3 -m macos_system_data_scanner \
  --json-output reports/system-data.json \
  --markdown-output reports/system-data.md \
  --top-directories 15 \
  --top-files 30 \
  --min-size-mb 25
```

- `--json-output`: path for the structured JSON report (overrides the default location)
- `--markdown-output`: path for the human-readable Markdown report (overrides the default location)
- `--top-directories`: number of directories to include in the ranked summary
- `--top-files`: number of files to include in the ranked summary
- `--min-size-mb`: minimum size threshold for ranked report sections

## Report interpretation

The generated JSON report includes:

- scan metadata and included targets
- category summaries
- top directories
- top files
- unknown large items
- scan limitations

The Markdown report contains the same underlying data in a review-friendly summary.

### Review guidance levels

| Guidance | Meaning |
| --- | --- |
| `safe-review` | Commonly reviewed locations such as caches or logs. Inspect manually before removing anything. |
| `needs-care` | Data that may still be important, such as backups, app state, mail, messages, or virtual machine images. |

### Good cleanup workflow

1. Run the scanner.
2. Review the largest categories and paths.
3. Inspect anything labeled `safe-review` first.
4. Be cautious with `needs-care` items such as backups, containers, and application support data.
5. If you're unsure, share the JSON report with an AI or ask for human review before deleting anything.

## Development

Run the test suite with:

```bash
python3 -m unittest discover -s tests
```
