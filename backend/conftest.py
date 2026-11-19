from datetime import date, time
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User, Role, UserRoleAssignment, ProfessorProfile
from apps.academics.models import (
    Department,
    Branch,
    AcademicYear,
    AcademicTerm,
    TimeSlot,
    Cohort,
    InstructionGroup,
    Course,
    CourseDeliveryRule,
    CurriculumItem,
    CourseOffering,
    TeachingAssignment,
)
from apps.facilities.models import Campus, Building, Room
from apps.timetable.models import ScheduleVersion


@pytest.fixture(autouse=True)
def enable_eager_celery(settings):
    """Ensure celery tasks run synchronously during tests."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def api_client():
    """Provides a fresh Django REST Framework test client."""
    return APIClient()


@pytest.fixture
def roles(db):
    """Seed standard roles: Super Admin, Branch Coordinator, Professor."""
    admin_role = Role.objects.create(code=Role.Code.SUPER_ADMIN, name='Super Admin')
    coord_role = Role.objects.create(code=Role.Code.BRANCH_COORDINATOR, name='Branch Coordinator')
    prof_role = Role.objects.create(code=Role.Code.PROFESSOR, name='Professor')
    return {
        'admin': admin_role,
        'coord': coord_role,
        'prof': prof_role,
    }


@pytest.fixture
def admin_user(db, roles):
    user = User.objects.create_user(
        email='admin.test@university.edu',
        password='AdminPassword123!',
        full_name='Test Super Admin',
        is_staff=True,
        is_superuser=True,
    )
    UserRoleAssignment.objects.create(user=user, role=roles['admin'])
    return user


@pytest.fixture
def academic_setup(db):
    """Base academic hierarchy: Department, Branches, Year, Term, and TimeSlots (1..8)."""
    dept = Department.objects.create(code='CSE', name='Computer Science')
    branch_cse = Branch.objects.create(
        department=dept,
        code='BTECH_CSE',
        name='B.Tech CSE',
        degree_name='B.Tech',
        max_semesters=8,
    )
    branch_ece = Branch.objects.create(
        department=dept,
        code='BTECH_ECE',
        name='B.Tech ECE',
        degree_name='B.Tech',
        max_semesters=8,
    )

    year = AcademicYear.objects.create(
        name='2026-27',
        start_date=date(2026, 7, 1),
        end_date=date(2027, 6, 30),
    )
    term = AcademicTerm.objects.create(
        academic_year=year,
        name='Odd Sem 2026',
        start_date=date(2026, 7, 15),
        end_date=date(2026, 12, 15),
    )

    slots = []
    for i in range(1, 9):
        s_time = time(8 + i, 30) if i <= 4 else time(9 + i, 0)
        e_time = time(9 + i, 30) if i <= 4 else time(10 + i, 0)
        session = TimeSlot.Session.MORNING if i <= 4 else TimeSlot.Session.AFTERNOON
        slots.append(TimeSlot.objects.create(slot_no=i, start_time=s_time, end_time=e_time, session=session))

    return {
        'dept': dept,
        'branch_cse': branch_cse,
        'branch_ece': branch_ece,
        'year': year,
        'term': term,
        'slots': slots,
    }


@pytest.fixture
def coordinator_user(db, roles, academic_setup):
    user = User.objects.create_user(
        email='coord.test@university.edu',
        password='CoordPassword123!',
        full_name='Test CSE Coordinator',
    )
    UserRoleAssignment.objects.create(
        user=user,
        role=roles['coord'],
        branch=academic_setup['branch_cse'],
    )
    return user


@pytest.fixture
def professor_user(db, roles, academic_setup):
    user = User.objects.create_user(
        email='prof.sharma@university.edu',
        password='ProfPassword123!',
        full_name='Dr. Sharma',
    )
    UserRoleAssignment.objects.create(user=user, role=roles['prof'])
    ProfessorProfile.objects.create(
        user=user,
        department=academic_setup['dept'],
        designation='Professor',
        max_hours_per_day=6,
    )
    return user


@pytest.fixture
def professor_user_2(db, roles, academic_setup):
    user = User.objects.create_user(
        email='prof.verma@university.edu',
        password='ProfPassword123!',
        full_name='Dr. Verma',
    )
    UserRoleAssignment.objects.create(user=user, role=roles['prof'])
    ProfessorProfile.objects.create(
        user=user,
        department=academic_setup['dept'],
        designation='Associate Professor',
        max_hours_per_day=6,
    )
    return user


@pytest.fixture
def facilities(db):
    """Classrooms and Specialized Laboratories."""
    campus = Campus.objects.create(code='MAIN', name='Main Campus')
    building = Building.objects.create(campus=campus, code='ENG', name='Engineering Block')

    classroom1 = Room.objects.create(
        building=building,
        room_no='101',
        room_type=Room.RoomType.CLASSROOM,
        capacity=60,
    )
    classroom2 = Room.objects.create(
        building=building,
        room_no='102',
        room_type=Room.RoomType.CLASSROOM,
        capacity=60,
    )
    comp_lab = Room.objects.create(
        building=building,
        room_no='LAB1',
        room_type=Room.RoomType.COMPUTER_LAB,
        capacity=40,
    )
    return {
        'campus': campus,
        'building': building,
        'classroom1': classroom1,
        'classroom2': classroom2,
        'comp_lab': comp_lab,
    }


@pytest.fixture
def schedule_version(db, academic_setup):
    return ScheduleVersion.objects.create(
        term=academic_setup['term'],
        version_no=1,
        status=ScheduleVersion.Status.DRAFT,
        name='Draft Test Schedule',
    )


@pytest.fixture
def timetable_environment(db, academic_setup, facilities, professor_user, professor_user_2, schedule_version):
    """Full end-to-end timetable fixture with cohorts, courses, rules, and teaching assignments."""
    term = academic_setup['term']
    branch = academic_setup['branch_cse']

    cohort = Cohort.objects.create(
        branch=branch,
        term=term,
        semester_no=5,
        section_code='A',
        student_count=60,
    )
    lab_grp1 = InstructionGroup.objects.create(cohort=cohort, code='A-L1', size=30)
    lab_grp2 = InstructionGroup.objects.create(cohort=cohort, code='A-L2', size=30)

    # 3-Credit Theory Course (DBMS)
    course_dbms = Course.objects.create(
        department=academic_setup['dept'],
        code='CS501',
        name='Database Systems',
        credit=3,
        course_type=Course.CourseType.THEORY,
    )
    CourseDeliveryRule.objects.create(
        course=course_dbms,
        weekly_meetings=3,
        duration_slots=1,
        preferred_room_type='CLASSROOM',
    )
    curr_dbms = CurriculumItem.objects.create(branch=branch, semester_no=5, course=course_dbms)
    offering_dbms = CourseOffering.objects.create(term=term, cohort=cohort, curriculum_item=curr_dbms)
    asgn_dbms = TeachingAssignment.objects.create(
        course_offering=offering_dbms,
        professor=professor_user,
        instruction_group=None,
    )

    # 4-Credit Theory Course (OS)
    course_os = Course.objects.create(
        department=academic_setup['dept'],
        code='CS502',
        name='Operating Systems',
        credit=4,
        course_type=Course.CourseType.THEORY,
    )
    CourseDeliveryRule.objects.create(
        course=course_os,
        weekly_meetings=4,
        duration_slots=1,
        preferred_room_type='CLASSROOM',
    )
    curr_os = CurriculumItem.objects.create(branch=branch, semester_no=5, course=course_os)
    offering_os = CourseOffering.objects.create(term=term, cohort=cohort, curriculum_item=curr_os)
    asgn_os = TeachingAssignment.objects.create(
        course_offering=offering_os,
        professor=professor_user_2,
        instruction_group=None,
    )

    # 2-Credit Lab Course (DBMS Lab)
    course_lab = Course.objects.create(
        department=academic_setup['dept'],
        code='CS503L',
        name='DBMS Lab',
        credit=2,
        course_type=Course.CourseType.LAB,
    )
    CourseDeliveryRule.objects.create(
        course=course_lab,
        weekly_meetings=2,
        duration_slots=3,
        preferred_room_type='COMPUTER_LAB',
    )
    curr_lab = CurriculumItem.objects.create(branch=branch, semester_no=5, course=course_lab)
    offering_lab = CourseOffering.objects.create(term=term, cohort=cohort, curriculum_item=curr_lab)
    asgn_lab = TeachingAssignment.objects.create(
        course_offering=offering_lab,
        professor=professor_user,
        instruction_group=lab_grp1,
    )

    return {
        'version': schedule_version,
        'cohort': cohort,
        'lab_grp1': lab_grp1,
        'lab_grp2': lab_grp2,
        'asgn_dbms': asgn_dbms,
        'asgn_os': asgn_os,
        'asgn_lab': asgn_lab,
        'course_dbms': course_dbms,
        'course_os': course_os,
        'course_lab': course_lab,
    }
