# Video Sorter

This repository contains a Python utility that sorts classroom recording files into semester/course folders and can optionally upload them to Kaltura before moving them.

If you are taking the project over, start here:

- [AGENTS.md](AGENTS.md)
- [docs/DEEP_DIVE.md](docs/DEEP_DIVE.md)

## What The App Expects

The sorter depends on three local inputs:

1. `config.ini` in the repo root
2. a schedule spreadsheet matching the expected column names
3. recording filenames that match one of the supported parser formats

For `Upload` mode it also needs a repo-root `.env` file with Kaltura credentials.

A sanitized schedule workbook example is available at [docs/examples/course_schedule_example.xlsx](docs/examples/course_schedule_example.xlsx), with field notes in [docs/COURSE_SHEET_INPUT.md](docs/COURSE_SHEET_INPUT.md).

## Setup

### 1. Create a virtual environment

Use Python 3.11 for the current pinned dependency set and executable builds.

```bash
python3.11 -m venv .venv
```

### 2. Install dependencies

```bash
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -r requirements.txt
```

`requirements.txt` is UTF-8. It pins `setuptools==79.0.1` because the current PyInstaller and altgraph versions still import `pkg_resources`, which newer setuptools releases removed.

### 3. Create `config.ini`

Use `config-EXAMPLE.ini` as a reference. The app now supports inline config comments, but the example keeps explanatory comments on their own lines to stay easy to copy and audit.

### 4. Add `.env` if using upload mode

`kaltura_uploader.py` expects:

- `PARTNER_ID`
- `TOKEN`
- `TOKEN_ID`

These values should stay local and never be committed.

### 5. Run the app

```bash
.venv/bin/python video_sorter.py
```

The app processes immediately on first launch, then continues running and checks again when the local time reaches 3 AM.

For a controlled one-pass test, run:

```bash
.venv/bin/python video_sorter.py --run-once
```

This uses the mode and folders in `config.ini`, processes one batch, runs retention cleanup, and exits.

## Running Tests

Run:

```bash
.venv/bin/python -m pytest -q
```

The tests depend on:

- `test_courses.xlsx`
- the folder structure configured by `[Paths].test_folder`

Status verified locally on August 23, 2026:

- 45 tests passed

## Build To Executable

The repo includes `video_sorter.spec`.

Build with:

```bash
.venv/bin/python -m PyInstaller --clean --noconfirm video_sorter.spec
```

PyInstaller produces `dist/video_sorter/`. Keep that whole directory together; the executable depends on its `_internal` contents.

Builds are platform-specific. The macOS arm64 build runs only on Apple silicon Macs. For Windows, either build on a Windows machine or run the repository's **Windows build** GitHub Actions workflow. The workflow tests the release, builds it with Python 3.11, and publishes `video-sorter-windows-x64`, containing the complete zipped bundle and a SHA-256 checksum.

`config.ini`, `.env`, and the schedule workbook are intentionally not bundled. Start the executable with its working directory set to the folder containing those files.

## Schedule spreadsheet expectations

The importer accepts extra columns and any column order. It ignores capitalization and extra whitespace in known headers. These columns are required:

- `Course`
- `Section #`
- `Course Title`
- `Instructor LAST`
- `Instructor`

The workbook also needs at least one meeting column, `Meetings` or `Meeting Pattern`, and at least one room column, `Room (cleaned)` or `Room`.

Operational notes:

- Room values may be bare numbers or building-prefixed values such as `LAW 2100` and `GC 3700`.
- `ONLINE`, `CANVAS`, `No Meeting Pattern`, and other nonphysical values do not participate in room/time matching.
- Semicolon-delimited meeting segments may have different days, times, rooms, and date limits.
- If one room value is listed, the importer applies it to every meeting segment. If the number of room values equals the number of meeting segments, it maps them by order, including mixed physical and nonphysical meetings. Other multi-room layouts or partly malformed room lists generate an error and disable timed matching for the whole row.
- `Instructor` uses `LAST, FIRST (00123456)`. Bracketed role labels such as `[Primary Instructor]` are allowed. Separate multiple instructors with semicolons.
- When more than one start time falls inside the tolerance window, the matcher only considers the nearest one. Equal-distance rows with the same upload hosts use stable course and section order. Equal-distance rows with different hosts leave recordings in the watch folder for review.

Check a workbook without moving or uploading anything:

```bash
.venv/bin/python video_sorter.py --validate-schedule /path/to/course_schedule.xlsx
```

Operational startup also stops before moving or uploading files when the schedule has an invalid room mapping. Upload mode additionally stops when a physical timed course has no valid upload host.

## Supported Recording Sources

The active parser pipeline supports:

- Extron filenames with room/date/time information
- Extron 2100 filenames
- CaptureCast filenames with course/section/date information

Details and examples live in [docs/DEEP_DIVE.md](docs/DEEP_DIVE.md).

## Roadmap / Future Cleanup Ideas

- Support unscheduled/manual recordings that start with one or more uNIDs
- Make config examples safer and more copy-pasteable
- Reduce Windows-only assumptions in tests and docs
