# Course Sheet Input

The sorter expects a registrar-style Excel workbook with one row per course section. A sanitized example lives at:

- [examples/course_schedule_example.xlsx](examples/course_schedule_example.xlsx)

The example mirrors the shape of the Spring 2026 export without committing live schedule data or real instructor identifiers.

## Required columns

The importer accepts extra columns and any column order. For known headers, it ignores capitalization, leading or trailing whitespace, and repeated spaces. It reports missing or duplicate normalized headers with the exact source column names.

These columns are required:

- `Course`
- `Section #`
- `Course Title`
- `Instructor LAST`
- `Instructor`

At least one of these meeting columns is required:

- `Meetings`
- `Meeting Pattern`

At least one of these room columns is required:

- `Room (cleaned)`
- `Room`

When both meeting columns exist, the importer prefers `Meetings` because it may include date limits. When both room columns exist, it prefers `Room (cleaned)` and falls back to `Room` if the cleaned value cannot be parsed. Columns such as `Schedule Print`, `Inst. Method`, and enrollment counts are ignored.

## Formatting rules

- `Course` should include the subject and number, such as `LAW 1010`.
- `Section #` may be numeric in Excel. The importer converts it to a string for matching.
- `Meetings` drives room/time matching when present. Supported day tokens include `M`, `T`, `W`, `Th`, `F`, `Sa`, `Su`, plus combined patterns such as `MW`, `TTh`, `MTTh`, `MWF`, `WF`, and `FSa`.
- Meeting start times should look like `7:30am`, `6pm`, or another `am`/`pm` time at the start of the time range.
- Separate distinct meeting segments with semicolons. Each segment keeps its own day set, start time, and optional date limit.
- Date limits may be a single date, such as `(01/04/2030)`, or an inclusive range, such as `(01/04/2030 to 05/31/2030)`. A timed recording must fall on the listed weekday and inside the date limit.
- Rows with `Does Not Meet` import successfully but do not participate in room/time matching.
- Physical room values may be bare numbers such as `2100`, or building-prefixed values such as `LAW 2100` and `GC 3700`. The importer normalizes these to the numeric value found in recording filenames.
- `ONLINE`, `CANVAS`, `No Meeting Pattern`, `Does Not Meet`, `No Room`, `TBA`, and `TBD` are treated as nonphysical rooms.
- `Instructor` should use `LAST, FIRST (00123456)`. Bracketed suffixes such as `[Primary Instructor]` and `[Secondary Instructor]` are allowed.
- Separate multiple instructors with semicolons, for example `SMITH, CASEY (00100003) [Primary Instructor]; JONES, RILEY (00100004) [Secondary Instructor]`.
- If an export repeats the same instructor for multiple meeting segments, the importer keeps one upload host per uNID.
- `Instructor LAST` is used for destination folder and filename labels.

## Multiple meetings and rooms

The importer uses these rules:

1. One room value applies to every meeting segment.
2. When the number of room values equals the number of meeting segments, rooms map to segments in source order. Nonphysical values such as `CANVAS` retain their position but do not participate in timed matching.
3. If more than one room is present and the counts do not match, the importer reports an error and disables timed matching for that row.
4. If any room token remains malformed after the raw-room fallback is checked, the importer disables timed matching for the entire row rather than guessing from the valid subset.

For example, this synthetic pair maps the Wednesday and Thursday segment to room 4100, then the Friday segment to room 4200:

```text
Meetings: WTh 9am-12pm (01/02/2030 to 01/03/2030); F 10am-11am (01/04/2030 to 05/31/2030)
Room (cleaned): LAW 4100
                LAW 4200
```

## Matching Notes

Timed recordings match by:

1. normalized physical room
2. weekday from the meeting segment
3. start time within `[Settings].start_time_tolerance`
4. optional date limit from `Meetings`

CaptureCast recordings do not include a meeting time, so they match by `Course` plus `Section #`.

The matcher ranks candidates by absolute minute distance from the recording time and only considers the nearest start. If equally near candidates have the same nonempty upload-host set, it chooses by stable course and section order and logs a warning. If their hosts differ or are missing, it leaves the recording in the watch folder for review.

## Read-only validation

Run this before switching to a new workbook:

```bash
.venv/bin/python video_sorter.py --validate-schedule /path/to/course_schedule.xlsx
```

The command prints course, timed-meeting, host, invalid room-mapping, and duplicate-slot counts. It does not move or upload files. Schema and workbook-read failures return exit code 2. Invalid room-to-meeting mappings and physical timed courses without upload hosts return exit code 1. Safe duplicate handling remains a warning.

Normal startup enforces those blockers before processing. Invalid room mappings stop both modes; physical timed courses without valid hosts stop Upload mode.

## Current export check

A Fall 2026 registrar workbook was checked against the importer on August 23, 2026. It had:

- 135 non-empty rows
- all required columns present
- `Schedule Print`, `Inst. Method`, and enrollment as ignored extra columns
- 107 physical timed meeting segments after multi-segment expansion
- no courses without a valid upload host after instructor-role cleanup
- six duplicate physical slots with explicit safe-handling warnings

The sanitized example workbook is covered by the pytest suite so future parsing changes are checked against this input style.
