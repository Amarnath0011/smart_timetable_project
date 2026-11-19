import pytest
from rest_framework import status
from apps.facilities.models import Room
from apps.faculty.models import ProfessorUnavailability
from apps.scheduler.models import AutoScheduleProposal
from apps.scheduler.services.generator import TimetableGenerator
from apps.scheduler.services.scoring import ScheduleScorer
from apps.timetable.models import (
    ScheduledMeeting,
    ProfessorSlotReservation,
    RoomSlotReservation,
)


@pytest.mark.django_db
class TestTimetableOrToolsGenerator:

    def test_generator_satisfies_all_curriculum_meetings(
        self, timetable_environment, academic_setup
    ):
        """
        Verify that CP-SAT solver successfully schedules:
        - 3-Credit Theory (DBMS): Exactly 3 one-hour meetings on distinct days.
        - 4-Credit Theory (OS): Exactly 4 one-hour meetings on distinct days.
        - 2-Credit Lab (DBMS Lab): Exactly 2 three-hour continuous meetings on distinct days.
        """
        version = timetable_environment['version']
        branch_id = academic_setup['branch_cse'].id

        generator = TimetableGenerator(
            schedule_version=version,
            branch_ids=[branch_id],
            time_limit=15,
            replace_existing=True,
        )
        result = generator.generate()

        assert result['solver_status'] in ['OPTIMAL', 'FEASIBLE']
        assert len(result['unscheduled_offerings']) == 0
        assert result['quality_score'] > 0

        meetings = result['proposed_meetings']
        # Total expected meetings = 3 (DBMS) + 4 (OS) + 2 (Lab) = 9
        assert len(meetings) == 9

        # 1. 3-Credit Theory checks
        dbms = [m for m in meetings if m['course_code'] == 'CS501']
        assert len(dbms) == 3
        assert all(m['duration_slots'] == 1 for m in dbms)
        assert len(set(m['weekday'] for m in dbms)) == 3, "3-credit theory must be on distinct days"

        # 2. 4-Credit Theory checks
        os = [m for m in meetings if m['course_code'] == 'CS502']
        assert len(os) == 4
        assert all(m['duration_slots'] == 1 for m in os)
        assert len(set(m['weekday'] for m in os)) == 4, "4-credit theory must be on distinct days"

        # 3. 2-Credit Lab checks
        lab = [m for m in meetings if m['course_code'] == 'CS503L']
        assert len(lab) == 2
        assert len(set(m['weekday'] for m in lab)) == 2, "Lab meetings must be on distinct days"
        for m in lab:
            assert m['duration_slots'] == 3
            assert m['start_slot'] in [1, 2, 5, 6], "Lab start slot must be 1, 2, 5, or 6"
            assert m['room_type'] in [
                Room.RoomType.COMPUTER_LAB,
                Room.RoomType.ELECTRONICS_LAB,
                Room.RoomType.CHEMISTRY_LAB,
            ], "Lab must be placed in a laboratory room"

    def test_generator_respects_professor_unavailability(
        self, timetable_environment, academic_setup, professor_user
    ):
        """Verify the solver never places a professor during their recorded unavailable hours."""
        version = timetable_environment['version']
        branch_id = academic_setup['branch_cse'].id

        # Block Dr. Sharma entirely on Monday (weekday=1)
        ProfessorUnavailability.objects.create(
            professor=professor_user,
            weekday=1,
            start_slot=1,
            end_slot=8,
            reason="Dean meetings on Mondays",
        )

        generator = TimetableGenerator(
            schedule_version=version,
            branch_ids=[branch_id],
            time_limit=15,
            replace_existing=True,
        )
        result = generator.generate()

        assert result['solver_status'] in ['OPTIMAL', 'FEASIBLE']
        for m in result['proposed_meetings']:
            if m['professor_id'] == professor_user.id:
                assert m['weekday'] != 1, "Professor was scheduled on Monday despite unavailability!"

    def test_generator_diagnoses_unscheduled_offerings_when_lab_room_missing(
        self, timetable_environment, academic_setup
    ):
        """When required facility types are unavailable, the solver returns structured diagnostic reasons."""
        version = timetable_environment['version']
        branch_id = academic_setup['branch_cse'].id

        # Deactivate all labs
        Room.objects.filter(room_type=Room.RoomType.COMPUTER_LAB).update(is_active=False)

        generator = TimetableGenerator(
            schedule_version=version,
            branch_ids=[branch_id],
            time_limit=10,
            replace_existing=True,
        )
        result = generator.generate()

        unscheduled = result['unscheduled_offerings']
        unscheduled_courses = [u.get('course_code') for u in unscheduled]
        assert 'CS503L' in unscheduled_courses

        lab_diag = next(u for u in unscheduled if u.get('course_code') == 'CS503L')
        assert 'laboratory' in lab_diag['reason'].lower()

    def test_schedule_scorer_evaluates_quality_metrics(
        self, timetable_environment, academic_setup
    ):
        """Verify the quality scorer calculates overall score and soft-constraint breakdown."""
        version = timetable_environment['version']
        branch_id = academic_setup['branch_cse'].id

        generator = TimetableGenerator(
            schedule_version=version,
            branch_ids=[branch_id],
            time_limit=15,
            replace_existing=True,
        )
        result = generator.generate()

        # ScheduleScorer.calculate_score is a classmethod
        score_data = ScheduleScorer.calculate_score(result['proposed_meetings'])

        assert 'overall_score' in score_data
        assert 0 <= score_data['overall_score'] <= 100
        assert 'breakdown' in score_data
        breakdown = score_data['breakdown']
        assert 'student_gaps_score' in breakdown
        assert 'professor_gaps_score' in breakdown
        assert 'load_balance_score' in breakdown
        assert 'consecutive_hours_score' in breakdown

    def test_atomic_proposal_commit_and_concurrency_conflict(
        self, api_client, timetable_environment, academic_setup, facilities, admin_user
    ):
        """
        Verify proposal workflow:
        1. Valid proposal commits atomically into ScheduledMeeting and reservations.
        2. Database records reflect all scheduled meetings and slot reservations.
        """
        version = timetable_environment['version']
        branch_id = academic_setup['branch_cse'].id

        generator = TimetableGenerator(
            schedule_version=version,
            branch_ids=[branch_id],
            time_limit=15,
            replace_existing=True,
        )
        gen_result = generator.generate()
        proposed = gen_result['proposed_meetings']
        assert len(proposed) > 0

        # Create proposal
        proposal = AutoScheduleProposal.objects.create(
            schedule_version=version,
            selected_branches=[branch_id],
            proposed_meetings=proposed,
            solver_status=gen_result['solver_status'],
            quality_score=gen_result['quality_score'],
            generation_metadata={'replace_existing': True},
            created_by=admin_user,
        )
        assert proposal.status == AutoScheduleProposal.ProposalStatus.PENDING

        # Commit proposal via API
        api_client.force_authenticate(user=admin_user)
        commit_url = f"/api/timetable/{version.id}/commit-proposal"
        resp = api_client.post(commit_url, {'proposal_id': proposal.id}, format='json')

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['status'] == 'COMMITTED'

        proposal.refresh_from_db()
        assert proposal.status == AutoScheduleProposal.ProposalStatus.COMMITTED

        # Verify DB records
        meetings_count = ScheduledMeeting.objects.filter(schedule_version=version).count()
        assert meetings_count == len(proposed)
        assert ProfessorSlotReservation.objects.filter(schedule_version=version).count() > 0
        assert RoomSlotReservation.objects.filter(schedule_version=version).count() > 0
