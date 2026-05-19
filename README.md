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

| Option | Default | Description |
| --- | --- | --- |
| `--json-output` | `system_scan_report/system-data-report.json` | Path for the structured JSON report |
| `--markdown-output` | `system_scan_report/system-data-report.md` | Path for the human-readable Markdown report |
| `--top-directories` | `10` | Number of directories to include in the ranked summary |
| `--top-files` | `20` | Number of files to include in the ranked summary |
| `--min-size-mb` | `50` | Minimum size threshold (MB) for ranked report sections |
| `--stale-days` | `365` | Days since last modification before an item is flagged as stale |

### Example: quick default scan

Just run the scanner with no arguments to get started:

```bash
macos-system-data-scanner
```

This writes JSON + Markdown reports to `system_scan_report/` in the current directory, using all defaults.

### Example: find items untouched for 2+ years

Identify large directories and files that have not been modified in over two years — strong candidates for cleanup:

```bash
macos-system-data-scanner --stale-days 730
```

The report will include a **"Stale Large Items"** section sorted oldest-first, showing the last-modified age of each item.

### Example: raise the ranking threshold to focus on big offenders

Skip items smaller than 500 MB and expand the directory / file lists to surface more detail:

```bash
macos-system-data-scanner \
  --min-size-mb 500 \
  --top-directories 20 \
  --top-files 40
```

### Example: save reports to a custom location

Redirect output to a dedicated folder for versioned comparisons:

```bash
macos-system-data-scanner \
  --json-output ~/Desktop/scan-2026-05/report.json \
  --markdown-output ~/Desktop/scan-2026-05/report.md
```

### Example: comprehensive deep scan

Combine all options for a thorough analysis — low size threshold, large item lists, and 180-day staleness window:

```bash
macos-system-data-scanner \
  --min-size-mb 10 \
  --top-directories 30 \
  --top-files 50 \
  --stale-days 180 \
  --json-output ~/Desktop/deep-scan.json \
  --markdown-output ~/Desktop/deep-scan.md
```

## Report interpretation

The generated JSON report includes:

- scan metadata and included targets
- category summaries
- top directories
- top files
- unknown large items
- **stale large items** (items not modified within the configured threshold)
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
4. Check the **Stale Large Items** section — anything not modified in over a year is a good starting point for cleanup.
5. Be cautious with `needs-care` items such as backups, containers, and application support data.
6. If you're unsure, share the JSON report with an AI or ask for human review before deleting anything.

## Development

Run the test suite with:

```bash
python3 -m unittest discover -s tests
```

### CI (Pull Request checks)

This project includes a GitHub Actions workflow at `.github/workflows/ci.yml`.

- On every pull request (and pushes to `main`/`master`), CI runs:
  - test matrix: Python `3.10`, `3.11`, `3.12` on `ubuntu-latest` and `macos-latest`
  - quality gates: `ruff` (lint), `mypy` (type checks), `bandit` (security scan)

Local equivalents:

```bash
python3 -m pip install -e .
python3 -m pip install ruff mypy bandit
ruff check src
mypy src
bandit -q -r src
PYTHONPATH=src python3 -m unittest discover -s tests
```
