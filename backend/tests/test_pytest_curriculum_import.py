import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from apps.academics.models import Course, CourseDeliveryRule, CurriculumItem


@pytest.mark.django_db
class TestCurriculumCsvBulkImport:

    def test_valid_curriculum_csv_import_success(self, api_client, admin_user, academic_setup):
        """
        Uploading a well-formatted curriculum CSV creates Course, DeliveryRule,
        and CurriculumItem associations for the target branch.
        """
        api_client.force_authenticate(user=admin_user)
        branch = academic_setup['branch_cse']

        csv_content = (
            "branch_code,semester_no,course_code,course_name,credit,course_type,weekly_meetings,duration_slots\n"
            f"{branch.code},5,CS510,Computer Networks,4,THEORY,4,1\n"
            f"{branch.code},5,CS511L,Networks Lab,2,LAB,2,3\n"
        )
        csv_file = SimpleUploadedFile("curriculum_valid.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/curriculum/import', {'file': csv_file}, format='multipart')

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['success'] is True
        assert resp.data['imported_count'] == 2

        # Verify Course and Delivery Rule created
        course_net = Course.objects.get(code='CS510')
        assert course_net.credit == 4
        assert course_net.delivery_rule.weekly_meetings == 4
        assert course_net.delivery_rule.duration_slots == 1

        # Verify CurriculumItem created
        assert CurriculumItem.objects.filter(branch=branch, semester_no=5, course=course_net).exists()

        course_lab = Course.objects.get(code='CS511L')
        assert course_lab.course_type == Course.CourseType.LAB
        assert course_lab.delivery_rule.duration_slots == 3

    def test_missing_required_headers_rejected(self, api_client, admin_user):
        """A CSV missing required header fields (e.g. course_type, credit) must be rejected immediately."""
        api_client.force_authenticate(user=admin_user)

        csv_content = (
            "branch_code,semester_no,course_code\n"
            "BTECH_CSE,5,CS510\n"
        )
        csv_file = SimpleUploadedFile("curriculum_bad_headers.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/curriculum/import', {'file': csv_file}, format='multipart')

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data['success'] is False
        assert any('missing required headers' in err['message'].lower() for err in resp.data['errors'])

    def test_unknown_branch_code_reports_row_error(self, api_client, admin_user):
        """Referencing a non-existent branch code returns row diagnostic error."""
        api_client.force_authenticate(user=admin_user)

        csv_content = (
            "branch_code,semester_no,course_code,course_name,credit,course_type,weekly_meetings,duration_slots\n"
            "NON_EXISTENT_BRANCH,5,CS599,Ghost Course,3,THEORY,3,1\n"
        )
        csv_file = SimpleUploadedFile("curriculum_bad_branch.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/curriculum/import', {'file': csv_file}, format='multipart')

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data['success'] is False
        assert any('branch' in err['message'].lower() for err in resp.data['errors'])

    def test_semester_exceeding_branch_max_semesters_rejected(self, api_client, admin_user, academic_setup):
        """A semester number > branch.max_semesters (e.g. 9 for B.Tech with max 8) must be rejected."""
        api_client.force_authenticate(user=admin_user)
        branch = academic_setup['branch_cse']

        csv_content = (
            "branch_code,semester_no,course_code,course_name,credit,course_type,weekly_meetings,duration_slots\n"
            f"{branch.code},9,CS901,Impossible Course,3,THEORY,3,1\n"
        )
        csv_file = SimpleUploadedFile("curriculum_bad_sem.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/curriculum/import', {'file': csv_file}, format='multipart')

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data['success'] is False
        assert any('exceeds' in err['message'].lower() for err in resp.data['errors'])

    def test_invalid_course_type_rejected(self, api_client, admin_user, academic_setup):
        """Unsupported course_type value (e.g. 'ONLINE' or 'SEMINAR' not in choices) must fail validation."""
        api_client.force_authenticate(user=admin_user)
        branch = academic_setup['branch_cse']

        csv_content = (
            "branch_code,semester_no,course_code,course_name,credit,course_type,weekly_meetings,duration_slots\n"
            f"{branch.code},5,CS590,Seminar Course,3,INVALID_TYPE,3,1\n"
        )
        csv_file = SimpleUploadedFile("curriculum_bad_type.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/curriculum/import', {'file': csv_file}, format='multipart')

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data['success'] is False
        assert any('course_type' in err['message'].lower() for err in resp.data['errors'])

    def test_transactional_rollback_when_one_row_fails(self, api_client, admin_user, academic_setup):
        """
        Transactional Atomicity:
        If Row 1 is valid but Row 2 fails validation, Row 1 must NOT be saved in the database.
        """
        api_client.force_authenticate(user=admin_user)
        branch = academic_setup['branch_cse']

        csv_content = (
            "branch_code,semester_no,course_code,course_name,credit,course_type,weekly_meetings,duration_slots\n"
            f"{branch.code},5,CS588,Good Course,3,THEORY,3,1\n"
            f"{branch.code},12,CS589,Bad Semester Course,3,THEORY,3,1\n"
        )
        csv_file = SimpleUploadedFile("curriculum_partial_fail.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/curriculum/import', {'file': csv_file}, format='multipart')

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        # Entire batch rolled back: CS588 must NOT exist
        assert not Course.objects.filter(code='CS588').exists()
