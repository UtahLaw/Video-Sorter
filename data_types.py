from datetime import date, time, datetime
import os


WEEKDAYS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')

class EventHost:
    def __init__(self, first, last, unid_zero_prefix):
        self.first = first
        self.last = last
        self.unid = f'u{unid_zero_prefix[1:]}'

    def full (self):
        return f'{self.first} {self.last}'

    def __str__(self) -> str:
        return f'Host(name={self.full()}, unid={self.unid})'

class Event:
    def __init__(self, start_time: time, hosts: list[EventHost]):
        self.start_time = start_time
        self.hosts = hosts


class CourseMeeting:
    """One recurring or date-limited meeting for a course section."""

    def __init__(
        self,
        days: set[str],
        start_time: time | None,
        room_number: str | None,
        start_date: date | None = None,
        end_date: date | None = None,
        source: str = '',
    ):
        self.days = days
        self.start_time = start_time
        self.room_number = room_number
        self.start_date = start_date
        self.end_date = end_date
        self.source = source

    @property
    def has_date_limit(self) -> bool:
        return self.start_date is not None or self.end_date is not None

    def occurs_on(self, meeting_date: date) -> bool:
        if WEEKDAYS[meeting_date.weekday()] not in self.days:
            return False
        if self.start_date is not None and meeting_date < self.start_date:
            return False
        if self.end_date is not None and meeting_date > self.end_date:
            return False
        return True

    def __str__(self) -> str:
        date_text = ''
        if self.start_date is not None:
            date_text = f', dates={self.start_date} to {self.end_date or self.start_date}'
        return f"CourseMeeting(room={self.room_number}, days={self.days}, time={self.start_time}{date_text})"

class Course(Event):
    def __init__(
        self,
        number: str,
        section: str,
        name: str,
        instructor_last: str,
        room_number: str | None,
        days: set[str],
        start_time: time | None,
        instructors: list[EventHost],
        meetings: list[CourseMeeting] | None = None,
    ):
        if meetings is None:
            meetings = [CourseMeeting(days, start_time, room_number)]

        first_meeting = meetings[0] if meetings else None
        legacy_start_time = first_meeting.start_time if first_meeting is not None else start_time
        super().__init__(legacy_start_time, instructors)
        self.number = number
        self.section_number = section
        self.name = name
        self.instructor_last = instructor_last
        self.meetings = meetings
        self.validation_errors: list[str] = []

        # These fields remain for callers written before courses could have more
        # than one meeting. Matching code uses ``meetings`` directly.
        self.room_number = first_meeting.room_number if first_meeting is not None else room_number
        self.days = set().union(*(meeting.days for meeting in meetings)) if meetings else days

    def get_first_host_alphabetically (self) -> EventHost:
        return sorted(self.hosts, key=lambda x : x.last + x.first)[0]

    def __str__(self) -> str:
        return f"Course(title={self.number}-{self.section_number} {self.name}, meetings={len(self.meetings)})"

class Recording:
    def __init__(self, filepath: str, rec_device: str, date: date, time: time):
        self.filepath = filepath
        self.rec_device = rec_device
        self.date = date
        self.time = time

    @property
    def filename (self):
        return os.path.basename(self.filepath) if self.filepath else None

    def get_datetime(self):
        if self.time is None:
            return None
        return datetime(self.date.year, self.date.month, self.date.day, self.time.hour, self.time.minute, 0, 0)
    
class ManualRecording(Recording):
    '''
    Currently Unused. Intended to represent a generic recording 
    which is not strictly for a lecture. Could be a recording 
    of any kind of event.
    '''
    def __init__(self, filepath: str, rec_device: str, date: date, time: time, metadata: str, unids: list[str]):
        super().__init__(filepath, rec_device, date, time)
        self.metadata = metadata
        self.unids = unids

class LectureRecording(Recording):
    '''
    A wrapper for information extracted from a filename
    '''
    def __init__(self, filepath: str, date: date, time: time, room_number: str, rec_device: str, course_number: str=None, section_number: str=None, course_code: str=None):
        super().__init__(filepath, rec_device, date, time)
        self.room_number = room_number
        self.course_number = course_number
        self.section_number = section_number
        self.course_code = course_code
        self.matching_error = None
        
    def was_scheduled (self):
        return not ((self.room_number is None) and (self.date is None) and (self.time is None))
    
    def course_number_full(self):
        if self.course_code is None or self.course_number is None:
            return ''
        return self.course_code + ' ' + self.course_number

    def __str__ (self):
        return f"Recording(room_number={self.room_number}, date={self.date}, time={self.time}, course_number_full={self.course_number_full()}, section_number={self.section_number}, path={self.filepath})"
