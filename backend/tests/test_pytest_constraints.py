import pytest
from apps.timetable.models import (
    ScheduledMeeting,
    ProfessorSlotReservation,
    RoomSlotReservation,
    GroupSlotReservation,
    ScheduleChangeAudit,
)
from apps.timetable.services.validator import TimetableValidator
from apps.timetable.services.reservation_service import TimetableReservationService


@pytest.mark.django_db
class TestTimetableHardConstraints:

    def test_validate_free_slot_allowed(self, timetable_environment, facilities):
        """A clean, unreserved slot must return allowed=True with zero conflicts."""
        version = timetable_environment['version']
        asgn = timetable_environment['asgn_dbms']
        room = facilities['classroom1']

        result = TimetableValidator.validate_meeting_placement(
            schedule_version=version,
            teaching_assignment=asgn,
            weekday=1,
            start_slot=1,
            duration_slots=1,
            room=room,
        )
        assert result['allowed'] is True
        assert len(result['conflicts']) == 0

    def test_professor_conflict_detected_when_double_booked(
        self, timetable_environment, facilities, admin_user
    ):
        """Hard Constraint 1: A professor cannot be booked in two distinct places at the same time."""
        version = timetable_environment['version']
        asgn = timetable_environment['asgn_dbms']  # Assigned to Dr. Sharma
        room1 = facilities['classroom1']
        room2 = facilities['classroom2']

        # Book first meeting on Monday Slot 1
        TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn,
            weekday=1,
            start_slot=1,
            duration_slots=1,
            room=room1,
            user=admin_user,
        )

        # Validate second placement for same professor on Monday Slot 1
        result = TimetableValidator.validate_meeting_placement(
            schedule_version=version,
            teaching_assignment=asgn,
            weekday=1,
            start_slot=1,
            duration_slots=1,
            room=room2,
        )
        assert result['allowed'] is False
        conflict_types = [c['type'] for c in result['conflicts']]
        assert 'PROFESSOR_BUSY' in conflict_types

    def test_room_conflict_detected_when_double_booked(
        self, timetable_environment, facilities, admin_user
    ):
        """Hard Constraint 2: A room cannot be occupied by two different classes at the same time."""
        version = timetable_environment['version']
        asgn1 = timetable_environment['asgn_dbms']  # Prof 1
        asgn2 = timetable_environment['asgn_os']    # Prof 2
        room = facilities['classroom1']

        # Prof 1 books Room 101 on Monday Slot 2
        TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn1,
            weekday=1,
            start_slot=2,
            duration_slots=1,
            room=room,
            user=admin_user,
        )

        # Prof 2 attempts to book the same Room 101 on Monday Slot 2
        result = TimetableValidator.validate_meeting_placement(
            schedule_version=version,
            teaching_assignment=asgn2,
            weekday=1,
            start_slot=2,
            duration_slots=1,
            room=room,
        )
        assert result['allowed'] is False
        conflict_types = [c['type'] for c in result['conflicts']]
        assert 'ROOM_BUSY' in conflict_types

    def test_student_cohort_conflict_detected_when_double_booked(
        self, timetable_environment, facilities, admin_user
    ):
        """Hard Constraint 3: A student cohort cannot attend two classes at the same time."""
        version = timetable_environment['version']
        asgn1 = timetable_environment['asgn_dbms']
        asgn2 = timetable_environment['asgn_os']
        room1 = facilities['classroom1']
        room2 = facilities['classroom2']

        # First class for Cohort 5A on Tuesday Slot 3
        TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn1,
            weekday=2,
            start_slot=3,
            duration_slots=1,
            room=room1,
            user=admin_user,
        )

        # Second class for Cohort 5A on Tuesday Slot 3
        result = TimetableValidator.validate_meeting_placement(
            schedule_version=version,
            teaching_assignment=asgn2,
            weekday=2,
            start_slot=3,
            duration_slots=1,
            room=room2,
        )
        assert result['allowed'] is False
        conflict_types = [c['type'] for c in result['conflicts']]
        assert 'GROUP_BUSY' in conflict_types

    @pytest.mark.parametrize(
        "start_slot,duration_slots,expected_error",
        [
            (4, 2, 'LUNCH_CROSSING'),  # Slot 4 (11:30) with 2 hours crosses 12:30-14:00 lunch
            (3, 3, 'LUNCH_CROSSING'),  # Slot 3 (10:30) with 3 hours crosses lunch
            (8, 2, 'OUT_OF_BOUNDS'),   # Exceeds university operating hours (slot 8 is end of day)
            (7, 3, 'OUT_OF_BOUNDS'),   # Slot 7 + 3 exceeds slot 8
        ],
    )
    def test_lunch_and_bounds_violations_rejected(
        self, timetable_environment, facilities, start_slot, duration_slots, expected_error
    ):
        """Hard Constraints 5 & 6: Classes cannot cross lunch break or exceed operational hours."""
        version = timetable_environment['version']
        asgn = timetable_environment['asgn_dbms']
        room = facilities['classroom1']

        result = TimetableValidator.validate_meeting_placement(
            schedule_version=version,
            teaching_assignment=asgn,
            weekday=1,
            start_slot=start_slot,
            duration_slots=duration_slots,
            room=room,
        )
        assert result['allowed'] is False
        conflict_types = [c['type'] for c in result['conflicts']]
        assert expected_error in conflict_types

    def test_multi_hour_lab_creates_exact_atomic_reservations(
        self, timetable_environment, facilities, admin_user
    ):
        """Hard Constraint 4: A 3-hour lab creates 3 discrete atomic reservations across all 3 tables."""
        version = timetable_environment['version']
        asgn_lab = timetable_environment['asgn_lab']
        comp_lab = facilities['comp_lab']

        # Save 3-hour lab on Wednesday Slot 1 (Slots 1, 2, 3)
        meeting = TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn_lab,
            weekday=3,
            start_slot=1,
            duration_slots=3,
            room=comp_lab,
            user=admin_user,
        )

        assert meeting.id is not None
        assert meeting.duration_slots == 3

        # Exactly 3 atomic reservation rows per dimension
        prof_res = ProfessorSlotReservation.objects.filter(scheduled_meeting=meeting)
        room_res = RoomSlotReservation.objects.filter(scheduled_meeting=meeting)
        grp_res = GroupSlotReservation.objects.filter(scheduled_meeting=meeting)

        assert prof_res.count() == 3
        assert room_res.count() == 3
        assert grp_res.count() == 3

        # All 3 slots (1, 2, 3) are tracked
        reserved_slots = set(prof_res.values_list('slot_no', flat=True))
        assert reserved_slots == {1, 2, 3}

        # Audit log was created
        audit = ScheduleChangeAudit.objects.filter(schedule_version=version, meeting_id=meeting.id).first()
        assert audit is not None
        assert audit.action == 'CREATE'

    def test_delete_meeting_cleans_up_all_reservations(
        self, timetable_environment, facilities, admin_user
    ):
        """Deleting a meeting removes all corresponding atomic reservations atomically."""
        version = timetable_environment['version']
        asgn = timetable_environment['asgn_dbms']
        room = facilities['classroom1']

        meeting = TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn,
            weekday=4,
            start_slot=1,
            duration_slots=1,
            room=room,
            user=admin_user,
        )
        meeting_id = meeting.id

        # Delete meeting
        TimetableReservationService.delete_meeting(
            schedule_version=version,
            meeting_id=meeting_id,
            user=admin_user,
        )

        assert not ScheduledMeeting.objects.filter(id=meeting_id).exists()
        assert not ProfessorSlotReservation.objects.filter(scheduled_meeting_id=meeting_id).exists()
        assert not RoomSlotReservation.objects.filter(scheduled_meeting_id=meeting_id).exists()
        assert not GroupSlotReservation.objects.filter(scheduled_meeting_id=meeting_id).exists()
