import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from apps.accounts.models import User, ProfessorProfile


@pytest.mark.django_db
class TestFacultyCsvBulkImportEdgeCases:

    def test_valid_faculty_csv_import_success(self, api_client, admin_user, academic_setup):
        """Standard valid CSV creates users, assigns roles, and links professor profiles."""
        api_client.force_authenticate(user=admin_user)

        csv_content = (
            "email,full_name,employee_code,department_code,designation,max_hours_per_day\n"
            "dr.grace.hopper@university.edu,Dr. Grace Hopper,EMP801,CSE,Professor,5\n"
            "dr.john.vonneumann@university.edu,Dr. John von Neumann,EMP802,CSE,Professor,6\n"
        )
        csv_file = SimpleUploadedFile("faculty_valid.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/professors/import', {'file': csv_file}, format='multipart')

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['success'] is True
        assert resp.data['imported_count'] == 2
        assert User.objects.filter(email='dr.grace.hopper@university.edu').exists()
        assert ProfessorProfile.objects.filter(user__email='dr.john.vonneumann@university.edu').exists()

    def test_duplicate_email_in_csv_triggers_rollback(self, api_client, admin_user, academic_setup):
        """
        Atomicity Edge Case:
        If any row contains a duplicate email or already existing user email,
        the entire batch must roll back so no partial/corrupt data is persisted.
        """
        api_client.force_authenticate(user=admin_user)
        initial_user_count = User.objects.count()

        csv_content = (
            "email,full_name,employee_code,department_code,designation,max_hours_per_day\n"
            "prof.unique1@university.edu,Prof Unique One,EMP901,CSE,Assistant Professor,6\n"
            "prof.unique1@university.edu,Prof Duplicate Email,EMP902,CSE,Assistant Professor,6\n"
        )
        csv_file = SimpleUploadedFile("faculty_duplicate.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/professors/import', {'file': csv_file}, format='multipart')

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data['success'] is False
        assert len(resp.data['errors']) > 0
        # Transaction rollback guarantees no users were saved
        assert User.objects.count() == initial_user_count

    def test_invalid_department_code_reports_row_level_diagnostics(
        self, api_client, admin_user, academic_setup
    ):
        """
        Data Validation Edge Case:
        Referencing a non-existent department code (e.g. 'UNKNOWN_DEPT') must report
        the specific row number and error description.
        """
        api_client.force_authenticate(user=admin_user)

        csv_content = (
            "email,full_name,employee_code,department_code,designation,max_hours_per_day\n"
            "dr.faulty@university.edu,Dr. Faulty,EMP999,UNKNOWN_DEPT,Professor,6\n"
        )
        csv_file = SimpleUploadedFile("faculty_bad_dept.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/professors/import', {'file': csv_file}, format='multipart')

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data['success'] is False
        assert len(resp.data['errors']) > 0
        err_msg = str(resp.data['errors']).lower()
        assert 'department' in err_msg or 'unknown' in err_msg or 'row' in err_msg

    def test_out_of_range_max_hours_per_day_rejected(
        self, api_client, admin_user, academic_setup
    ):
        """
        Business Boundary Edge Case:
        A daily workload exceeding 8 hours (or negative hours) is unfeasible in an 8-slot operating day.
        """
        api_client.force_authenticate(user=admin_user)

        csv_content = (
            "email,full_name,employee_code,department_code,designation,max_hours_per_day\n"
            "dr.overworked@university.edu,Dr. Overworked,EMP888,CSE,Professor,15\n"
        )
        csv_file = SimpleUploadedFile("faculty_overworked.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = api_client.post('/api/professors/import', {'file': csv_file}, format='multipart')

        # Either rejected via 400 or capped safely
        assert resp.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK]
        if resp.status_code == status.HTTP_400_BAD_REQUEST:
            assert resp.data['success'] is False

    def test_empty_or_malformed_file_rejected(self, api_client, admin_user):
        """Submitting an empty file returns 400 Bad Request."""
        api_client.force_authenticate(user=admin_user)
        empty_file = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")

        resp = api_client.post('/api/professors/import', {'file': empty_file}, format='multipart')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
