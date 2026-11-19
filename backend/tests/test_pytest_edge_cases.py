import pytest
from apps.academics.models import (
    Course,
    CourseDeliveryRule,
    CurriculumItem,
    CourseOffering,
    TeachingAssignment,
    Cohort,
)
from apps.facilities.models import Room
from apps.faculty.models import ProfessorUnavailability
from apps.scheduler.services.generator import TimetableGenerator
from apps.timetable.models import ScheduledMeeting
from apps.timetable.services.validator import TimetableValidator
from apps.timetable.services.reservation_service import TimetableReservationService


@pytest.mark.django_db
class TestSchedulerEdgeCasesAndInfeasibility:

    def test_overconstrained_curriculum_diagnosed_as_infeasible(
        self, timetable_environment, academic_setup, professor_user, facilities
    ):
        """
        Pigeonhole Principle Edge Case:
        If academic demand exceeds total weekly capacity (e.g., assigning courses
        requiring more hours than the 40 total slots available in a week),
        the CP-SAT solver must gracefully diagnose the bottleneck in `unscheduled_offerings`
        rather than hanging, crashing, or violating hard constraints.
        """
        version = timetable_environment['version']
        branch = academic_setup['branch_cse']
        term = academic_setup['term']
        dept = academic_setup['dept']
        cohort = timetable_environment['cohort']

        # Add 12 heavy 4-credit courses (12 * 4 = 48 lecture hours demanded > 40 weekly slots)
        for i in range(1, 13):
            c = Course.objects.create(
                department=dept,
                code=f'CS_HEAVY_{i}',
                name=f'Heavy Course {i}',
                credit=4,
                course_type=Course.CourseType.THEORY,
            )
            CourseDeliveryRule.objects.create(course=c, weekly_meetings=4, duration_slots=1)
            curr = CurriculumItem.objects.create(branch=branch, semester_no=5, course=c)
            off = CourseOffering.objects.create(term=term, cohort=cohort, curriculum_item=curr)
            TeachingAssignment.objects.create(course_offering=off, professor=professor_user)

        generator = TimetableGenerator(
            schedule_version=version,
            branch_ids=[branch.id],
            time_limit=10,
            replace_existing=True,
        )
        result = generator.generate()

        assert result['solver_status'] in ['OPTIMAL', 'FEASIBLE', 'INFEASIBLE']
        # The overconstrained courses cannot all be scheduled; solver must list unscheduled items
        assert len(result['unscheduled_offerings']) > 0
        reasons = [u['reason'].lower() for u in result['unscheduled_offerings']]
        assert any('slot' in r or 'capacity' in r or 'conflict' in r or 'infeasible' in r for r in reasons)

    def test_cohort_exceeding_all_room_capacities_fails_gracefully(
        self, timetable_environment, academic_setup
    ):
        """
        Capacity Mismatch Edge Case:
        When a cohort has 100 students but the maximum classroom capacity in the campus is 60,
        the optimizer must refuse placement in undersized rooms and report capacity mismatch.
        """
        version = timetable_environment['version']
        branch = academic_setup['branch_cse']
        cohort = timetable_environment['cohort']

        # Increase cohort size to 100 (exceeding all rooms in facilities: 60 max)
        cohort.student_count = 100
        cohort.save()

        generator = TimetableGenerator(
            schedule_version=version,
            branch_ids=[branch.id],
            time_limit=10,
            replace_existing=True,
        )
        result = generator.generate()

        # DBMS and OS offerings require CLASSROOM, but none can fit 100 students
        unscheduled_courses = [u.get('course_code') for u in result['unscheduled_offerings']]
        assert any(code in ['CS501', 'CS502'] for code in unscheduled_courses)

        matched_diag = next(u for u in result['unscheduled_offerings'] if u.get('course_code') in ['CS501', 'CS502'])
        assert 'capacity' in matched_diag['reason'].lower() or 'room' in matched_diag['reason'].lower()

    def test_faculty_fatigue_max_hours_per_day_enforced(
        self, timetable_environment, academic_setup, professor_user
    ):
        """
        Faculty Fatigue Edge Case:
        When a professor has max_hours_per_day = 2, the solver must not schedule more
        than 2 hours on any single weekday for that professor.
        """
        version = timetable_environment['version']
        branch = academic_setup['branch_cse']

        # Restrict professor to max 2 hours per day
        prof_profile = professor_user.professor_profile
        prof_profile.max_hours_per_day = 2
        prof_profile.save()

        generator = TimetableGenerator(
            schedule_version=version,
            branch_ids=[branch.id],
            time_limit=15,
            replace_existing=True,
        )
        result = generator.generate()

        if result['solver_status'] in ['OPTIMAL', 'FEASIBLE']:
            daily_hours = {d: 0 for d in range(1, 6)}
            for m in result['proposed_meetings']:
                if m['professor_id'] == professor_user.id:
                    daily_hours[m['weekday']] += m['duration_slots']

            for day, hours in daily_hours.items():
                assert hours <= 2, f"Prof exceeded fatigue limit on weekday {day}: {hours} hrs scheduled"

    @pytest.mark.parametrize("invalid_start_slot", [3, 4, 7, 8])
    def test_lab_3_hour_invalid_start_slots_rejected(
        self, timetable_environment, facilities, invalid_start_slot
    ):
        """
        Continuous Multi-Slot Boundary Edge Case:
        A 3-hour lab session requires 3 consecutive available slots.
        Starting at slot 3 crosses lunch (ends at slot 5).
        Starting at slot 4 crosses lunch (ends at slot 6).
        Starting at slot 7 exceeds operational day hours (ends at slot 9).
        Starting at slot 8 exceeds day hours (ends at slot 10).
        """
        version = timetable_environment['version']
        asgn_lab = timetable_environment['asgn_lab']
        comp_lab = facilities['comp_lab']

        validation = TimetableValidator.validate_meeting_placement(
            schedule_version=version,
            teaching_assignment=asgn_lab,
            weekday=1,
            start_slot=invalid_start_slot,
            duration_slots=3,
            room=comp_lab,
        )
        assert validation['allowed'] is False
        error_types = [c['type'] for c in validation['conflicts']]
        assert any(err in error_types for err in ['LUNCH_CROSSING', 'OUT_OF_BOUNDS', 'LAB_START_INVALID', 'INVALID_START_SLOT'])

    def test_lab_course_room_type_incompatibility_rejected(
        self, timetable_environment, facilities
    ):
        """
        Specialized Facility Edge Case:
        A computer lab course (requiring COMPUTER_LAB) cannot be placed inside
        a general lecture classroom (CLASSROOM).
        """
        version = timetable_environment['version']
        asgn_lab = timetable_environment['asgn_lab']
        classroom = facilities['classroom1']  # Regular classroom

        validation = TimetableValidator.validate_meeting_placement(
            schedule_version=version,
            teaching_assignment=asgn_lab,
            weekday=2,
            start_slot=1,
            duration_slots=3,
            room=classroom,
        )
        # Should be rejected due to room type mismatch
        assert validation['allowed'] is False
        error_types = [c['type'] for c in validation['conflicts']]
        assert any('ROOM' in t or 'TYPE' in t or 'CAPACITY' in t for t in error_types)

    def test_single_slot_unavailability_blocks_overlapping_multi_slot_lab(
        self, timetable_environment, facilities, professor_user
    ):
        """
        Unavailability Overlap Edge Case:
        If a professor is unavailable for only slot 2 on Tuesday,
        a 3-hour lab spanning slots 1..3 on Tuesday must be blocked.
        """
        version = timetable_environment['version']
        asgn_lab = timetable_environment['asgn_lab']
        comp_lab = facilities['comp_lab']

        # Prof unavailable only during slot 2
        ProfessorUnavailability.objects.create(
            professor=professor_user,
            weekday=2,
            start_slot=2,
            end_slot=2,
            reason="Committee duty",
        )

        validation = TimetableValidator.validate_meeting_placement(
            schedule_version=version,
            teaching_assignment=asgn_lab,
            weekday=2,
            start_slot=1,
            duration_slots=3,  # Covers slots 1, 2, 3 -> overlaps with slot 2
            room=comp_lab,
        )
        assert validation['allowed'] is False
        error_types = [c['type'] for c in validation['conflicts']]
        assert 'PROFESSOR_UNAVAILABLE' in error_types or 'PROFESSOR_BUSY' in error_types

    def test_concurrent_conflict_simulation_maintains_database_integrity(
        self, timetable_environment, facilities, admin_user
    ):
        """
        Concurrency Edge Case:
        Verify that database transactions preserve relational integrity:
        If two meetings attempt to reserve the same slot concurrently, the first succeeds
        and the second raises an HTTP 409 conflict, leaving zero orphan reservations.
        """
        version = timetable_environment['version']
        asgn1 = timetable_environment['asgn_dbms']
        asgn2 = timetable_environment['asgn_os']
        room = facilities['classroom1']

        # First booking succeeds
        m1 = TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn1,
            weekday=3,
            start_slot=5,
            duration_slots=1,
            room=room,
            user=admin_user,
        )
        assert m1.id is not None

        # Attempting second booking in same slot & room must raise or return error
        with pytest.raises(Exception):
            TimetableReservationService.save_meeting(
                schedule_version=version,
                teaching_assignment=asgn2,
                weekday=3,
                start_slot=5,
                duration_slots=1,
                room=room,
                user=admin_user,
            )

        # Confirm only exactly 1 meeting is saved
        assert ScheduledMeeting.objects.filter(
            schedule_version=version, weekday=3, start_slot=5
        ).count() == 1
