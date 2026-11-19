import pytest
from rest_framework import status
from apps.facilities.models import Room, RoomUnavailability
from apps.timetable.models import ScheduledMeeting, RoomSlotReservation
from apps.timetable.services.reservation_service import TimetableReservationService


@pytest.mark.django_db
class TestRoomAvailabilityAndBatchUpdates:

    def test_available_rooms_filters_by_capacity_and_type(
        self, api_client, admin_user, timetable_environment, facilities
    ):
        """
        Verify GET /api/timetable/{version_id}/available-rooms returns free rooms
        meeting minimum capacity and matching room_type.
        """
        api_client.force_authenticate(user=admin_user)
        version = timetable_environment['version']

        # Query for CLASSROOM with min_capacity=50
        resp = api_client.get(
            f"/api/timetable/{version.id}/available-rooms?weekday=1&start_slot=1&duration_slots=1&min_capacity=50&room_type=CLASSROOM"
        )
        assert resp.status_code == status.HTTP_200_OK
        rooms = resp.data
        room_ids = [r['id'] for r in rooms]

        assert facilities['classroom1'].id in room_ids
        assert facilities['classroom2'].id in room_ids
        # Computer lab should be filtered out by room_type
        assert facilities['comp_lab'].id not in room_ids

    def test_occupied_room_excluded_from_available_rooms(
        self, api_client, admin_user, timetable_environment, facilities
    ):
        """
        When Room 101 is reserved on Monday Slot 1,
        it must be excluded from available rooms for Monday Slot 1.
        """
        api_client.force_authenticate(user=admin_user)
        version = timetable_environment['version']
        asgn = timetable_environment['asgn_dbms']
        room1 = facilities['classroom1']

        # Book room 1 on Monday Slot 1
        TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn,
            weekday=1,
            start_slot=1,
            duration_slots=1,
            room=room1,
            user=admin_user,
        )

        resp = api_client.get(
            f"/api/timetable/{version.id}/available-rooms?weekday=1&start_slot=1&duration_slots=1"
        )
        assert resp.status_code == status.HTTP_200_OK
        available_ids = [r['id'] for r in resp.data]

        assert room1.id not in available_ids
        assert facilities['classroom2'].id in available_ids

    def test_room_unavailability_maintenance_excluded_from_available_rooms(
        self, api_client, admin_user, timetable_environment, facilities
    ):
        """
        Rooms undergoing maintenance via RoomUnavailability must be excluded from availability query.
        """
        api_client.force_authenticate(user=admin_user)
        version = timetable_environment['version']
        room2 = facilities['classroom2']

        # Block Room 102 on Tuesday Slots 1..4 for maintenance
        RoomUnavailability.objects.create(
            room=room2,
            weekday=2,
            start_slot=1,
            end_slot=4,
            reason="Air Conditioner Maintenance",
        )

        resp = api_client.get(
            f"/api/timetable/{version.id}/available-rooms?weekday=2&start_slot=2&duration_slots=1"
        )
        assert resp.status_code == status.HTTP_200_OK
        available_ids = [r['id'] for r in resp.data]

        assert room2.id not in available_ids

    def test_batch_update_meetings_atomic_success(
        self, api_client, admin_user, timetable_environment, facilities
    ):
        """
        Verify POST /api/timetable/batch-update updates multiple placements simultaneously.
        """
        api_client.force_authenticate(user=admin_user)
        version = timetable_environment['version']
        asgn_dbms = timetable_environment['asgn_dbms']
        asgn_os = timetable_environment['asgn_os']
        room1 = facilities['classroom1']
        room2 = facilities['classroom2']

        # Pre-place 2 meetings
        m1 = TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn_dbms,
            weekday=1,
            start_slot=1,
            duration_slots=1,
            room=room1,
            user=admin_user,
        )
        m2 = TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn_os,
            weekday=2,
            start_slot=1,
            duration_slots=1,
            room=room2,
            user=admin_user,
        )

        # Batch update: swap days
        updates = [
            {
                'meeting_id': m1.id,
                'teaching_assignment_id': asgn_dbms.id,
                'weekday': 3,
                'start_slot': 2,
                'duration_slots': 1,
                'room_id': room1.id,
            },
            {
                'meeting_id': m2.id,
                'teaching_assignment_id': asgn_os.id,
                'weekday': 4,
                'start_slot': 2,
                'duration_slots': 1,
                'room_id': room2.id,
            },
        ]

        resp = api_client.post(
            '/api/timetable/batch-update',
            {'schedule_version_id': version.id, 'updates': updates},
            format='json',
        )

        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 2

        m1.refresh_from_db()
        m2.refresh_from_db()
        assert m1.weekday == 3 and m1.start_slot == 2
        assert m2.weekday == 4 and m2.start_slot == 2

    def test_batch_update_conflict_triggers_full_rollback(
        self, api_client, admin_user, timetable_environment, facilities
    ):
        """
        Atomicity Verification:
        If one meeting update in a batch causes a conflict (e.g. professor busy),
        the entire batch must roll back so no partial state is applied.
        """
        api_client.force_authenticate(user=admin_user)
        version = timetable_environment['version']
        asgn_dbms = timetable_environment['asgn_dbms']
        asgn_os = timetable_environment['asgn_os']
        room1 = facilities['classroom1']
        room2 = facilities['classroom2']

        # Place initial meetings
        m1 = TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn_dbms,
            weekday=1,
            start_slot=1,
            duration_slots=1,
            room=room1,
            user=admin_user,
        )
        m2 = TimetableReservationService.save_meeting(
            schedule_version=version,
            teaching_assignment=asgn_os,
            weekday=2,
            start_slot=1,
            duration_slots=1,
            room=room2,
            user=admin_user,
        )

        # Batch update where item 2 clashes with item 1's destination (same cohort in 2 rooms simultaneously)
        updates = [
            {
                'meeting_id': m1.id,
                'teaching_assignment_id': asgn_dbms.id,
                'weekday': 5,
                'start_slot': 1,
                'duration_slots': 1,
                'room_id': room1.id,
            },
            {
                'meeting_id': m2.id,
                'teaching_assignment_id': asgn_os.id,
                'weekday': 5,
                'start_slot': 1,  # Clash! Cohort already booked on Friday Slot 1 by m1
                'duration_slots': 1,
                'room_id': room2.id,
            },
        ]

        resp = api_client.post(
            '/api/timetable/batch-update',
            {'schedule_version_id': version.id, 'updates': updates},
            format='json',
        )

        # Must fail with 409 Conflict
        assert resp.status_code == status.HTTP_409_CONFLICT

        # Confirm rollback: m1 and m2 remained in their original slots
        m1.refresh_from_db()
        m2.refresh_from_db()
        assert m1.weekday == 1 and m1.start_slot == 1
        assert m2.weekday == 2 and m2.start_slot == 1
