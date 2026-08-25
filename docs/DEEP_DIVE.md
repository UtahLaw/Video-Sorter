# Video Sorter Deep Dive

## What This App Does

The app watches a folder full of `.mp4` lecture captures, tries to determine which class each video belongs to, then either:

- moves the file into a semester/course folder structure, or
- uploads it to Kaltura and then moves it into that same folder structure.

It also reaps old files from the destination tree based on a retention window.

This is not a generic media pipeline. It is a narrow operational script built around:

- specific schedule spreadsheet exports,
- specific recording filename formats,
- a Kaltura app-token workflow,
- and a local config file that points at real folders.

## Runtime Flow

The main runtime lives in `video_sorter.py`.

1. Read `config.ini` from the repo root at import/runtime.
2. Build `RECORDING_START_TOLERANCE` from `[Settings].start_time_tolerance`.
3. Read the course spreadsheet into `Course` objects.
4. Enter an infinite loop.
5. Process immediately on first launch, then process again whenever `datetime.now().time().hour == 3`.
6. For every `.mp4` in the watch folder:
   - parse the filename into a `LectureRecording`
   - try to match that recording to a `Course`
   - move or upload+move depending on mode
7. Reap old files from the destination folder based on `weeks_before_deletion`.
8. Sleep until the next polling interval.

Important operational detail: there is no filesystem watcher. This is a polling/scheduled batch job.

For a controlled batch that exits after processing and retention cleanup, run `video_sorter.py --run-once`.

## Input Contracts

### 1. `config.ini`

The app expects a real `config.ini` at the repo root. The example file shows the required keys:

- `[Paths]`
  - `watch_folder`
  - `destination_folder`
  - `excel_file`
  - `test_folder`
- `[Settings]`
  - `mode`
  - `log_level`
  - `start_time_tolerance`
  - `weeks_before_deletion`
  - `log_file`
- `[LoggingEmails]`
  - `level`
  - `subject`
  - `outbound_server`
  - `from_address`
  - `to_count`
  - `to_email_0...n`

The runtime config parser now supports inline comments, but the example file keeps comments on their own lines so it stays easy to copy and audit.

### 2. `.env`

Only needed for `Upload` mode. `kaltura_uploader.py` expects:

- `PARTNER_ID`
- `TOKEN`
- `TOKEN_ID`

These are loaded via `python-dotenv`.

### 3. Schedule spreadsheet

`read_courses()` uses `pandas.read_excel()`. It accepts extra columns and any column order. Known headers are matched without regard to capitalization or extra whitespace.

Required columns:

- `Course`
- `Section #`
- `Course Title`
- `Instructor LAST`
- `Instructor`

The sheet also needs at least one of `Meetings` or `Meeting Pattern`, plus at least one of `Room (cleaned)` or `Room`.

The code directly depends on:

- `Meetings`, when present, for weekday, start-time, and date-limit parsing
- `Meeting Pattern` as the meeting fallback
- `Instructor LAST` for output folder/file naming
- `Room (cleaned)`, with `Room` as a fallback, for room-based matching
- `Instructor` for parsing people and uNIDs
- `Course` plus `Section #` for CaptureCast matching

See [COURSE_SHEET_INPUT.md](COURSE_SHEET_INPUT.md) and [examples/course_schedule_example.xlsx](examples/course_schedule_example.xlsx) for a sanitized workbook that mirrors the current export shape.

The importer handles the current registrar variations:

- building-prefixed rooms such as `LAW 2100` and `GC 3700` normalize to bare room numbers
- nonphysical values such as `CANVAS`, `ONLINE`, and `No Meeting Pattern` skip room/time matching
- instructor role suffixes such as `[Primary Instructor]` are removed before parsing
- semicolon-delimited meeting segments keep separate days, times, rooms, and optional date limits
- one room applies to all meeting segments; equal room and segment counts map by order
- unequal multi-room and segment counts generate an error and skip timed matching for the row
- rows such as `Does Not Meet` import but skip room/time matching

If the registrar/export format changes, this function is one of the first places to inspect.

## Supported Filename Formats

Filename parsing lives in `format_parser.py`.

### Extron

Pattern:

```text
(\d+)_.*?_(\d{8})-(\d{6})_[sS]1[rR]1.mp4
```

Extracts:

- room number
- recording date
- recording time

Matching path:

- room number
- weekday
- start time within tolerance

### Legacy Extron

There is also an older unused parser for filenames containing `Rec\d+`.

### Extron 2100

Pattern:

```text
SMP-2100_(\d{8})-(\d{6})_[sS]1[rR]1.mp4
```

This hard-codes room `2100`.

### CaptureCast

Pattern:

```text
(\w+)-(\d+)-(\d+)---(\d{1,2})-(\d{1,2})-(\d{4}).mp4
```

Extracts:

- course code
- course number
- section number
- date

Matching path:

- course number + section

Because CaptureCast filenames do not include a meeting time, they skip the room/time tolerance path.

### Manual recordings

There is a stub for `manual_format_parser()` representing filenames prefixed with one or more uNIDs, but it is currently unused and not part of the active parser list.

## Domain Model

### `EventHost`

- stores first name, last name, and a normalized `u########` style identifier

### `Course`

- number
- section number
- course name
- instructor last-name display string
- list of meeting segments
- list of instructor hosts

Each `CourseMeeting` stores its room number, days, start time, optional inclusive start and end dates, and original source text. The legacy `Course.room_number`, `Course.days`, and `Course.start_time` attributes remain for older callers, but matching uses the meeting list.

It also chooses a default host alphabetically for upload ownership if an explicit instructor index is not supplied.

### `LectureRecording`

- filepath
- recording device label
- date
- time
- room number
- optional course number/section/code

This class is the boundary object produced by the filename parsers.

## Matching Logic

The matching engine is small but opinionated.

### Timed recordings

Timed recordings are matched by:

1. room equality
2. weekday membership
3. start time within `RECORDING_START_TOLERANCE`
4. an optional single-date or date-range limit from `Meetings`

The time tolerance comparison ignores the calendar date for its arithmetic. The meeting date check uses the actual recording date.

The matcher ranks candidates by absolute minute distance from the recording time and only considers the nearest scheduled start inside the tolerance window. Equally near candidates with the same nonempty upload-host set use stable course and section order and log a warning. Candidates with different or missing hosts are ambiguous. The app leaves those files in the watch folder instead of moving or uploading them.

### Untimed recordings

Untimed recordings are matched by:

1. `course_code + " " + course_number`
2. section number
3. explicit meeting date limits, when the course has them

This is mainly for CaptureCast.

### Unmatched recordings

Anything that does not match ends up in:

```text
<destination>/Unmatched_Videos/
```

## Output Layout

Destination paths are built from:

```text
<destination>/<semester>/<course number>_<course title>_<instructor last>/<course title>_<instructor last>_<mm-dd-yy>.mp4
```

Examples:

- `Fall23/LAW 1230_Course1 The Sequel_BEEKHUIZEN/...`
- `Spring26/...`

Unsafe characters are stripped by `get_folder_safe_name()`. That means punctuation is removed, not replaced.

If the destination filename already exists, the app appends `_1`, `_2`, and so on.

## Upload Mode

Upload behavior lives in `kaltura_uploader.py` and `mock_kaltura_client.py`.

Flow:

1. start widget session
2. hash token with SHA-256
3. start app-token session
4. request upload token
5. upload file bytes
6. create media entry
7. attach uploaded bytes to the media entry

The repository includes a minimal custom client because the author notes that the official Kaltura Python library was not reliable for this workflow.

Operational nuance: upload ownership is assigned per host. In `upload_files()`, the script loops through each course host and performs an upload before moving the file.

The custom client forces `format=1` on both API and file-upload URLs, including upload URLs returned by Kaltura. Kaltura's upload endpoint can acknowledge accepted bytes with HTTP 202 and an empty body; in that case the client polls `uploadToken.get` and continues only after the token reaches full-upload status. It URL-encodes query values and applies bounded connect/read timeouts. Failures identify the upload stage, HTTP status, content type, sanitized endpoint, and response size without logging session tokens or query parameters.

## Retention / Reaper

`file_reaper.py` recursively deletes files older than the cutoff and removes directories once they become empty.

Important detail: reaping happens against the destination tree after each processing pass, not as a separate command.

## Tests

The repo has a meaningful pytest suite in `unit_test.py`. It covers:

- spreadsheet import
- instructor parsing
- parser-based matching
- move operations
- full `process_existing_files()` behavior
- reaper behavior

Local verification on August 25, 2026:

- command run: `.venv/bin/python -m pytest -q`
- result: `49 passed`

The suite includes the current header, room, instructor-role, multi-meeting, date-limit, and duplicate-slot cases.

## Schedule preflight

Run this read-only check before changing the configured workbook:

```bash
.venv/bin/python video_sorter.py --validate-schedule /path/to/course_schedule.xlsx
```

It prints course, physical timed-meeting, missing-host, invalid room-mapping, and duplicate-slot counts. Unreadable workbooks, bad schemas, and empty schedules return exit code 2. Invalid room-to-meeting mappings and active physical courses without valid upload hosts return exit code 1. Duplicate slots remain warnings because the matcher handles them safely.

Normal processing enforces the same row blockers before touching a recording. Invalid room mappings stop Move and Upload modes. A physical timed course without a valid host stops Upload mode.

## Packaging

Use Python 3.11 for the current dependency set. `requirements.txt` is UTF-8 and pins `setuptools==79.0.1`; PyInstaller 6.2.0 and altgraph 0.17.4 still import `pkg_resources`, which newer setuptools releases removed.

Build with:

```bash
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m PyInstaller --clean --noconfirm video_sorter.spec
```

The spec creates a one-directory bundle at `dist/video_sorter/`. Copy the whole directory, including `_internal`. PyInstaller builds for the current operating system and CPU architecture, so create the production Windows executable on Windows rather than copying a macOS build. The repository's **Windows build** GitHub Actions workflow is the supported fallback when the deployment PC does not have a build toolchain; it runs the test suite and a packaged executable smoke test before publishing a zipped Windows bundle and SHA-256 checksum.

The CI-built executable is unsigned and intended for controlled internal deployment. Verify both the workflow commit and ZIP checksum before extraction. SmartScreen or endpoint security may flag it until an Authenticode signing process is configured.

The build does not contain `config.ini`, `.env`, or a schedule workbook. The executable reads those files relative to its working directory. A Windows service or scheduled task therefore needs its working directory set to the deployment folder.

## Current Sharp Edges

These are not necessarily production bugs, but they are the main maintenance hotspots.

- The build stack currently depends on the `setuptools==79.0.1` compatibility pin for `pkg_resources`.
- `config-EXAMPLE.ini` is not safely copy-pasteable because of inline value comments.
- The app reads config at import time, which makes code reuse and isolated testing more awkward.
- Instructor names still need the `LAST, FIRST (00123456)` core format after optional bracketed role suffixes.
- The default process is a forever loop with time-based polling. The CLI has validation and one-pass modes but no service wrapper.
- The repo still reflects a Windows-first operational history even though development can happen on macOS/Linux.

## Recommended Mental Model For Future Work

If you need to change this app later, think in this order:

1. Is the input contract changing?
   - spreadsheet export
   - filename format
   - config keys
   - Kaltura auth shape
2. Does the change affect matching correctness?
3. Does it affect downstream folder naming or retention?
4. Can it be covered by extending `unit_test.py` without rewriting the architecture?

This is a pragmatic operations script. The best improvements will usually come from making input parsing safer, config/setup clearer, and tests less platform-specific before attempting a large refactor.
