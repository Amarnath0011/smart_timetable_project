import pytest
from rest_framework import status
from apps.academics.models import (
    Cohort,
    InstructionGroup,
    Course,
    CourseDeliveryRule,
    CurriculumItem,
    CourseOffering,
    TeachingAssignment,
)


@pytest.mark.django_db
class TestAcademicsApiAndHierarchy:

    def test_cohort_generate_groups_action(self, api_client, admin_user, academic_setup):
        """
        Test POST /api/cohorts/{id}/generate-groups/ with type='SPLIT':
        Automatically splits a cohort of 60 into two 30-student lab instruction groups (e.g. A-L1, A-L2).
        """
        api_client.force_authenticate(user=admin_user)
        branch = academic_setup['branch_cse']
        term = academic_setup['term']

        cohort = Cohort.objects.create(
            branch=branch,
            term=term,
            semester_no=3,
            section_code='B',
            student_count=60,
        )

        resp = api_client.post(
            f"/api/cohorts/{cohort.id}/generate-groups/",
            {'type': 'SPLIT'},
            format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert len(resp.data) == 2

        groups = InstructionGroup.objects.filter(cohort=cohort).order_by('code')
        assert groups.count() == 2
        assert groups[0].code == 'B-L1' and groups[0].size == 30
        assert groups[1].code == 'B-L2' and groups[1].size == 30

    def test_course_creation_with_nested_delivery_rule(self, api_client, admin_user, academic_setup):
        """
        Creating a course with nested delivery_rule via POST /api/courses/
        atomically creates both Course and CourseDeliveryRule records.
        """
        api_client.force_authenticate(user=admin_user)
        dept = academic_setup['dept']

        resp = api_client.post(
            '/api/courses/',
            {
                'department': dept.id,
                'code': 'CS401',
                'name': 'Algorithms Design',
                'credit': 4,
                'course_type': 'THEORY',
                'delivery_rule': {
                    'weekly_meetings': 4,
                    'duration_slots': 1,
                    'preferred_room_type': 'CLASSROOM',
                },
            },
            format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['code'] == 'CS401'
        assert resp.data['delivery_rule']['weekly_meetings'] == 4

        course = Course.objects.get(code='CS401')
        assert course.delivery_rule.duration_slots == 1

    def test_duplicate_course_offering_in_same_term_rejected(
        self, api_client, admin_user, timetable_environment, academic_setup
    ):
        """
        A course cannot be offered twice to the exact same cohort within the same academic term.
        """
        api_client.force_authenticate(user=admin_user)
        cohort = timetable_environment['cohort']
        term = academic_setup['term']
        curr_item = timetable_environment['course_dbms'].curriculum_items.first()

        # Second attempt to offer the exact same curriculum item to the exact same cohort in the same term
        resp = api_client.post(
            '/api/course-offerings/',
            {
                'term': term.id,
                'cohort': cohort.id,
                'curriculum_item': curr_item.id,
            },
            format='json',
        )

        # UniqueConstraint on (term, cohort, curriculum_item) returns 400
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_teaching_assignment_creation_and_listing(
        self, api_client, admin_user, timetable_environment, professor_user_2
    ):
        """
        Assigning a faculty member to a course offering via POST /api/teaching-assignments/.
        """
        api_client.force_authenticate(user=admin_user)
        offering = timetable_environment['asgn_dbms'].course_offering

        resp = api_client.post(
            '/api/teaching-assignments/',
            {
                'course_offering': offering.id,
                'professor': professor_user_2.id,
                'instruction_group': None,
                'is_primary': False,
            },
            format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['professor_name'] == professor_user_2.full_name

    def test_course_creation_with_semester_and_branch_and_filtering(
        self, api_client, admin_user, academic_setup
    ):
        """
        Verify creating a course with a specific semester and branch via POST /api/courses/
        and filtering by ?semester=... and ?branch=...
        """
        api_client.force_authenticate(user=admin_user)
        branch = academic_setup['branch_cse']
        dept = academic_setup['dept']

        # 1. Create Course for Sem 4 in Branch CSE
        resp = api_client.post(
            '/api/courses/',
            {
                'department': dept.id,
                'branch': branch.id,
                'semester': 4,
                'code': 'CS402',
                'name': 'Design of Computer Systems',
                'credit': 3,
                'course_type': 'THEORY',
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['semester'] == 4
        assert resp.data['branch'] == branch.id
        assert resp.data['branch_code'] == branch.code

        # 2. Filter courses by semester=4
        resp_filter_sem4 = api_client.get('/api/courses/?semester=4')
        assert resp_filter_sem4.status_code == status.HTTP_200_OK
        sem4_courses = resp_filter_sem4.data if isinstance(resp_filter_sem4.data, list) else resp_filter_sem4.data.get('results', [])
        codes = [c['code'] for c in sem4_courses]
        assert 'CS402' in codes

        # 3. Filter courses by semester=1 should NOT contain CS402
        resp_filter_sem1 = api_client.get('/api/courses/?semester=1')
        assert resp_filter_sem1.status_code == status.HTTP_200_OK
        sem1_courses = resp_filter_sem1.data if isinstance(resp_filter_sem1.data, list) else resp_filter_sem1.data.get('results', [])
        sem1_codes = [c['code'] for c in sem1_courses]
        assert 'CS402' not in sem1_codes

        # 4. Verify auto-created curriculum item for CS402 with branch and semester 4
        curr_items = CurriculumItem.objects.filter(branch=branch, semester_no=4, course__code='CS402')
        assert curr_items.exists()

    def test_course_creation_with_professor_selection_and_assignment_sync(
        self, api_client, admin_user, academic_setup, professor_user
    ):
        """
        Verify creating a course with an assigned professor in the course form,
        ensuring professor_name is serialized and query filter ?professor=... works.
        """
        api_client.force_authenticate(user=admin_user)
        branch = academic_setup['branch_cse']
        dept = academic_setup['dept']

        # 1. Create course with professor selected
        resp = api_client.post(
            '/api/courses/',
            {
                'department': dept.id,
                'branch': branch.id,
                'semester': 5,
                'code': 'CS505',
                'name': 'Cloud Computing Systems',
                'credit': 4,
                'course_type': 'THEORY',
                'professor': professor_user.id,
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['professor'] == professor_user.id
        assert resp.data['professor_name'] == professor_user.full_name
        assert resp.data['professor_email'] == professor_user.email

        # 2. Filter courses by professor
        resp_filter = api_client.get(f'/api/courses/?professor={professor_user.id}')
        assert resp_filter.status_code == status.HTTP_200_OK
        results = resp_filter.data if isinstance(resp_filter.data, list) else resp_filter.data.get('results', [])
        codes = [c['code'] for c in results]
        assert 'CS505' in codes
