import logging
from datetime import time, date
from django.core.management.base import BaseCommand
from django.db import transaction

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
from apps.facilities.models import Campus, Building, Room, RoomUnavailability
from apps.faculty.models import ProfessorUnavailability
from apps.timetable.models import (
    ScheduleVersion,
    ScheduledMeeting,
    MeetingInstructionGroup,
    ProfessorSlotReservation,
    RoomSlotReservation,
    GroupSlotReservation,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Seeds realistic demo data for National Institute of Technology Jamshedpur (NIT JSR)'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Starting NIT Jamshedpur (NIT JSR) Demo Data Seeding ==="))

        # -------------------------------------------------------------------------
        # 1. ROLES
        # -------------------------------------------------------------------------
        admin_role, _ = Role.objects.get_or_create(
            code=Role.Code.SUPER_ADMIN,
            defaults={'name': 'Super Administrator', 'description': 'Full university system access'}
        )
        coord_role, _ = Role.objects.get_or_create(
            code=Role.Code.BRANCH_COORDINATOR,
            defaults={'name': 'Branch Coordinator', 'description': 'Coordinates branch timetable and allocations'}
        )
        prof_role, _ = Role.objects.get_or_create(
            code=Role.Code.PROFESSOR,
            defaults={'name': 'Professor', 'description': 'Faculty member and instructor'}
        )
        self.stdout.write(self.style.SUCCESS("[OK] Roles verified"))

        # -------------------------------------------------------------------------
        # 2. TIME SLOTS (8 daily slots, standard university schedule)
        # -------------------------------------------------------------------------
        slots_data = [
            (1, time(8, 30), time(9, 30), TimeSlot.Session.MORNING),
            (2, time(9, 30), time(10, 30), TimeSlot.Session.MORNING),
            (3, time(10, 30), time(11, 30), TimeSlot.Session.MORNING),
            (4, time(11, 30), time(12, 30), TimeSlot.Session.MORNING),
            (5, time(14, 0), time(15, 0), TimeSlot.Session.AFTERNOON),
            (6, time(15, 0), time(16, 0), TimeSlot.Session.AFTERNOON),
            (7, time(16, 0), time(17, 0), TimeSlot.Session.AFTERNOON),
            (8, time(17, 0), time(18, 0), TimeSlot.Session.AFTERNOON),
        ]
        for slot_no, start_t, end_t, sess in slots_data:
            TimeSlot.objects.update_or_create(
                slot_no=slot_no,
                defaults={
                    'start_time': start_t,
                    'end_time': end_t,
                    'session': sess,
                    'is_active': True,
                }
            )
        self.stdout.write(self.style.SUCCESS("[OK] 8 daily Time Slots seeded"))

        # -------------------------------------------------------------------------
        # 3. CAMPUS, BUILDINGS & ROOMS (NIT JSR Campus Facilities)
        # -------------------------------------------------------------------------
        campus, _ = Campus.objects.update_or_create(
            code='NIT_JSR',
            defaults={
                'name': 'NIT Jamshedpur Main Campus',
                'address': 'Adityapur, Jamshedpur, Jharkhand 831014, India',
                'is_active': True,
            }
        )

        buildings_data = [
            ('DJLHC', 'Diamond Jubilee Lecture Hall Complex', 4),
            ('CC_BLK', 'Computer Centre & IT Services Block', 3),
            ('CSE_DEPT', 'Department of Computer Science & Engineering', 3),
            ('ECE_DEPT', 'Department of Electronics & Communication Engineering', 3),
            ('ELEC_BLK', 'Department of Electrical Engineering', 3),
            ('MECH_BLK', 'Mechanical Engineering Complex', 3),
            ('CENTRAL_AUD', 'Central Auditorium & Convention Centre', 2),
        ]
        bld_map = {}
        for code, name, floors in buildings_data:
            bld, _ = Building.objects.update_or_create(
                campus=campus,
                code=code,
                defaults={'name': name, 'floors_count': floors, 'is_active': True}
            )
            bld_map[code] = bld

        rooms_data = [
            # (building_code, room_no, name, type, capacity, floor, has_projector)
            ('DJLHC', 'LH-101', 'Smart Lecture Hall 101', Room.RoomType.CLASSROOM, 75, 1, True),
            ('DJLHC', 'LH-102', 'Smart Lecture Hall 102', Room.RoomType.CLASSROOM, 75, 1, True),
            ('DJLHC', 'LH-201', 'Smart Lecture Hall 201', Room.RoomType.CLASSROOM, 75, 2, True),
            ('DJLHC', 'LH-202', 'Smart Lecture Hall 202', Room.RoomType.CLASSROOM, 75, 2, True),
            ('DJLHC', 'LH-301', 'Smart Lecture Hall 301', Room.RoomType.CLASSROOM, 65, 3, True),
            ('CC_BLK', 'CC-LAB-1', 'Systems & Programming Lab 1', Room.RoomType.COMPUTER_LAB, 45, 1, True),
            ('CC_BLK', 'CC-LAB-2', 'Network & Advanced Computing Lab', Room.RoomType.COMPUTER_LAB, 45, 1, True),
            ('CSE_DEPT', 'CS-LH1', 'CSE Seminar Classroom 1', Room.RoomType.CLASSROOM, 65, 1, True),
            ('CSE_DEPT', 'CS-LAB1', 'Algorithms & Database Lab', Room.RoomType.COMPUTER_LAB, 40, 2, True),
            ('CSE_DEPT', 'CS-LAB2', 'AI & Machine Learning Lab', Room.RoomType.COMPUTER_LAB, 40, 2, True),
            ('ECE_DEPT', 'EC-LH1', 'ECE Class Room 1', Room.RoomType.CLASSROOM, 65, 1, True),
            ('ECE_DEPT', 'EC-LAB1', 'Digital Electronics & Microprocessor Lab', Room.RoomType.ELECTRONICS_LAB, 36, 2, True),
            ('ECE_DEPT', 'EC-LAB2', 'VLSI & Communication Systems Lab', Room.RoomType.ELECTRONICS_LAB, 36, 2, True),
            ('ELEC_BLK', 'EE-LH1', 'Electrical Lecture Hall 1', Room.RoomType.CLASSROOM, 65, 1, True),
            ('ELEC_BLK', 'EE-LAB1', 'Electrical Machines & Power Lab', Room.RoomType.ELECTRONICS_LAB, 36, 1, True),
            ('MECH_BLK', 'ME-CAD', 'CAD / CAM Simulation Lab', Room.RoomType.COMPUTER_LAB, 40, 2, True),
            ('CENTRAL_AUD', 'AUD-MAIN', 'NIT JSR Diamond Auditorium', Room.RoomType.SEMINAR_HALL, 250, 1, True),
        ]
        for b_code, r_no, r_name, r_type, cap, fl, proj in rooms_data:
            Room.objects.update_or_create(
                building=bld_map[b_code],
                room_no=r_no,
                defaults={
                    'name': r_name,
                    'room_type': r_type,
                    'capacity': cap,
                    'floor': fl,
                    'has_projector': proj,
                    'is_active': True,
                }
            )
        self.stdout.write(self.style.SUCCESS("[OK] NIT JSR Campus, 7 Buildings & 17 Rooms seeded"))

        # -------------------------------------------------------------------------
        # 4. DEPARTMENTS & BRANCHES AT NIT JSR
        # -------------------------------------------------------------------------
        departments_info = [
            ('CSE', 'Computer Science and Engineering', 'Department of Computer Science and Engineering, NIT JSR'),
            ('ECE', 'Electronics and Communication Engineering', 'Department of Electronics and Communication Engineering, NIT JSR'),
            ('EE', 'Electrical Engineering', 'Department of Electrical Engineering, NIT JSR'),
            ('ME', 'Mechanical Engineering', 'Department of Mechanical Engineering, NIT JSR'),
            ('CE', 'Civil Engineering', 'Department of Civil Engineering, NIT JSR'),
            ('MME', 'Metallurgical and Materials Engineering', 'Department of Metallurgical & Materials Engineering, NIT JSR'),
            ('PIE', 'Production and Industrial Engineering', 'Department of Production & Industrial Engineering, NIT JSR'),
            ('CA', 'Computer Applications', 'Department of Computer Applications (MCA), NIT JSR'),
            ('MATH', 'Mathematics', 'Department of Mathematics & Computing, NIT JSR'),
        ]
        dept_map = {}
        for code, name, desc in departments_info:
            dept, _ = Department.objects.update_or_create(
                code=code,
                defaults={'name': name, 'description': desc, 'is_active': True}
            )
            dept_map[code] = dept

        branches_info = [
            (dept_map['CSE'], 'BTECH_CSE', 'B.Tech in Computer Science and Engineering', 'B.Tech', 8),
            (dept_map['CSE'], 'MTECH_CSE', 'M.Tech in Computer Science (Information Systems)', 'M.Tech', 4),
            (dept_map['ECE'], 'BTECH_ECE', 'B.Tech in Electronics and Communication Engineering', 'B.Tech', 8),
            (dept_map['EE'], 'BTECH_EE', 'B.Tech in Electrical Engineering', 'B.Tech', 8),
            (dept_map['ME'], 'BTECH_ME', 'B.Tech in Mechanical Engineering', 'B.Tech', 8),
            (dept_map['CE'], 'BTECH_CE', 'B.Tech in Civil Engineering', 'B.Tech', 8),
            (dept_map['MME'], 'BTECH_MME', 'B.Tech in Metallurgical and Materials Engineering', 'B.Tech', 8),
            (dept_map['CA'], 'MCA', 'Master of Computer Applications', 'MCA', 6),
        ]
        branch_map = {}
        for dept, b_code, b_name, degree, max_sems in branches_info:
            branch, _ = Branch.objects.update_or_create(
                department=dept,
                code=b_code,
                defaults={
                    'name': b_name,
                    'degree_name': degree,
                    'max_semesters': max_sems,
                    'is_active': True,
                }
            )
            branch_map[b_code] = branch
        self.stdout.write(self.style.SUCCESS("[OK] 9 NIT JSR Departments & 8 Academic Branches seeded"))

        # -------------------------------------------------------------------------
        # 5. USERS & FACULTY / PROFESSORS AT NIT JSR
        # -------------------------------------------------------------------------
        common_password = 'Password@123'

        # Super Admin
        admin_user, _ = User.objects.update_or_create(
            email='admin@nitjsr.ac.in',
            defaults={
                'full_name': 'Dr. Gautam Sutradhar (Director & Super Admin)',
                'employee_code': 'NITJSR-ADM-001',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        admin_user.set_password(common_password)
        admin_user.save()
        UserRoleAssignment.objects.get_or_create(user=admin_user, role=admin_role, branch=None)

        # Faculty list: (email, full_name, emp_code, dept_code, designation, max_hrs, role_branch_coord_code)
        faculty_roster = [
            # CSE Faculty
            ('dkumar.cse@nitjsr.ac.in', 'Dr. Dilip Kumar', 'NITJSR-CSE-001', 'CSE', 'Professor & HOD', 5, 'BTECH_CSE'),
            ('vkumar.cse@nitjsr.ac.in', 'Dr. Vinay Kumar', 'NITJSR-CSE-002', 'CSE', 'Associate Professor', 6, None),
            ('skumar.cse@nitjsr.ac.in', 'Dr. Sanjay Kumar', 'NITJSR-CSE-003', 'CSE', 'Assistant Professor', 6, None),
            ('bksingh.cse@nitjsr.ac.in', 'Dr. B. K. Singh', 'NITJSR-CSE-004', 'CSE', 'Professor', 6, None),
            ('sdutta.cse@nitjsr.ac.in', 'Dr. Subrata Dutta', 'NITJSR-CSE-005', 'CSE', 'Assistant Professor', 6, None),
            ('rkagrawal.cse@nitjsr.ac.in', 'Dr. R. K. Agrawal', 'NITJSR-CSE-006', 'CSE', 'Associate Professor', 6, None),
            ('kpatel.cse@nitjsr.ac.in', 'Dr. K. Patel', 'NITJSR-CSE-007', 'CSE', 'Assistant Professor', 6, None),

            # ECE Faculty
            ('kksingh.ece@nitjsr.ac.in', 'Dr. K. K. Singh', 'NITJSR-ECE-001', 'ECE', 'Professor & HOD', 5, 'BTECH_ECE'),
            ('rsinha.ece@nitjsr.ac.in', 'Dr. Rashmi Sinha', 'NITJSR-ECE-002', 'ECE', 'Associate Professor', 6, None),
            ('akumar.ece@nitjsr.ac.in', 'Dr. Amit Kumar', 'NITJSR-ECE-003', 'ECE', 'Assistant Professor', 6, None),
            ('bbhowmik.ece@nitjsr.ac.in', 'Dr. Basanta Bhowmik', 'NITJSR-ECE-004', 'ECE', 'Assistant Professor', 6, None),

            # EE Faculty
            ('nkumar.ee@nitjsr.ac.in', 'Dr. Niranjan Kumar', 'NITJSR-EE-001', 'EE', 'Professor & HOD', 5, 'BTECH_EE'),
            ('jkumar.ee@nitjsr.ac.in', 'Dr. Jitendra Kumar', 'NITJSR-EE-002', 'EE', 'Associate Professor', 6, None),
            ('ohgupta.ee@nitjsr.ac.in', 'Dr. Om Hari Gupta', 'NITJSR-EE-003', 'EE', 'Assistant Professor', 6, None),

            # ME Faculty
            ('rvsharma.me@nitjsr.ac.in', 'Dr. R. V. Sharma', 'NITJSR-ME-001', 'ME', 'Professor & HOD', 5, 'BTECH_ME'),
            ('skprasad.me@nitjsr.ac.in', 'Dr. S. K. Prasad', 'NITJSR-ME-002', 'ME', 'Associate Professor', 6, None),

            # CE Faculty
            ('akchoudhary.ce@nitjsr.ac.in', 'Dr. A. K. Choudhary', 'NITJSR-CE-001', 'CE', 'Professor & HOD', 6, 'BTECH_CE'),

            # CA Faculty
            ('dkyadav.ca@nitjsr.ac.in', 'Dr. D. K. Yadav', 'NITJSR-CA-001', 'CA', 'Associate Professor & HOD', 6, 'MCA'),
        ]

        prof_user_map = {}
        for email, full_name, emp_code, dept_code, desig, max_hrs, coord_branch in faculty_roster:
            user, _ = User.objects.update_or_create(
                email=email,
                defaults={
                    'full_name': full_name,
                    'employee_code': emp_code,
                    'is_staff': False,
                    'is_active': True,
                }
            )
            user.set_password(common_password)
            user.save()

            # Ensure Professor role assignment
            UserRoleAssignment.objects.get_or_create(user=user, role=prof_role, branch=None)

            # If also branch coordinator, add coordinator role assignment
            if coord_branch and coord_branch in branch_map:
                UserRoleAssignment.objects.get_or_create(
                    user=user,
                    role=coord_role,
                    branch=branch_map[coord_branch]
                )

            # Professor profile
            dept_obj = dept_map[dept_code]
            ProfessorProfile.objects.update_or_create(
                user=user,
                defaults={
                    'department': dept_obj,
                    'designation': desig,
                    'max_hours_per_day': max_hrs,
                }
            )
            prof_user_map[email] = user

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(faculty_roster)} NIT JSR Professors & Coordinators seeded"))

        # Add sample Professor Unavailability
        # Dilip Kumar: Monday slot 1-2 (HOD meeting)
        dilip_prof = prof_user_map['dkumar.cse@nitjsr.ac.in']
        ProfessorUnavailability.objects.update_or_create(
            professor=dilip_prof,
            weekday=1,
            start_slot=1,
            end_slot=2,
            defaults={'reason': 'HOD Academic Coordination Council Meeting'}
        )
        # K.K. Singh: Wednesday slot 7-8 (Senate Meeting)
        kksingh_prof = prof_user_map['kksingh.ece@nitjsr.ac.in']
        ProfessorUnavailability.objects.update_or_create(
            professor=kksingh_prof,
            weekday=3,
            start_slot=7,
            end_slot=8,
            defaults={'reason': 'Dean Academic / Senate Meeting'}
        )

        # -------------------------------------------------------------------------
        # 6. ACADEMIC YEAR & ACTIVE TERMS
        # -------------------------------------------------------------------------
        acad_year, _ = AcademicYear.objects.update_or_create(
            name='2026-27',
            defaults={
                'start_date': date(2026, 8, 1),
                'end_date': date(2027, 6, 30),
                'is_current': True,
                'is_active': True,
            }
        )

        odd_term, _ = AcademicTerm.objects.update_or_create(
            academic_year=acad_year,
            name='Odd Semester 2026-27 (Autumn)',
            defaults={
                'term_type': AcademicTerm.TermType.ODD,
                'start_date': date(2026, 8, 10),
                'end_date': date(2026, 12, 22),
                'is_active': True,
            }
        )

        even_term, _ = AcademicTerm.objects.update_or_create(
            academic_year=acad_year,
            name='Even Semester 2026-27 (Spring)',
            defaults={
                'term_type': AcademicTerm.TermType.EVEN,
                'start_date': date(2027, 1, 10),
                'end_date': date(2027, 5, 25),
                'is_active': True,
            }
        )
        self.stdout.write(self.style.SUCCESS("[OK] Academic Year 2026-27 and Odd/Even Terms seeded"))

        # -------------------------------------------------------------------------
        # 7. COURSES & SUBJECTS FOR NIT JSR CURRICULUM
        # -------------------------------------------------------------------------
        # Structure: (code, name, credit, course_type, dept_code, branch_code, sem, prof_email, weekly_meetings, duration_slots, pref_room_type)
        courses_catalog = [
            # === B.Tech CSE Semester 3 (Autumn) ===
            (
                'CS201', 'Data Structures and Algorithms', 4, Course.CourseType.THEORY,
                'CSE', 'BTECH_CSE', 3, 'skumar.cse@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'CS202', 'Discrete Mathematics & Graph Theory', 4, Course.CourseType.THEORY,
                'CSE', 'BTECH_CSE', 3, 'vkumar.cse@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'CS203', 'Digital Electronics and Logic Design', 3, Course.CourseType.THEORY,
                'CSE', 'BTECH_CSE', 3, 'rsinha.ece@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'CS204', 'Object Oriented Programming with Java', 3, Course.CourseType.THEORY,
                'CSE', 'BTECH_CSE', 3, 'sdutta.cse@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'CS205', 'Data Structures Laboratory', 2, Course.CourseType.LAB,
                'CSE', 'BTECH_CSE', 3, 'skumar.cse@nitjsr.ac.in', 2, 3, 'COMPUTER_LAB'
            ),
            (
                'CS206', 'Object Oriented Programming Laboratory', 2, Course.CourseType.LAB,
                'CSE', 'BTECH_CSE', 3, 'sdutta.cse@nitjsr.ac.in', 2, 3, 'COMPUTER_LAB'
            ),

            # === B.Tech CSE Semester 5 (Autumn) ===
            (
                'CS301', 'Database Management Systems', 4, Course.CourseType.THEORY,
                'CSE', 'BTECH_CSE', 5, 'dkumar.cse@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'CS302', 'Operating Systems', 4, Course.CourseType.THEORY,
                'CSE', 'BTECH_CSE', 5, 'bksingh.cse@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'CS303', 'Computer Networks & Internet Protocols', 3, Course.CourseType.THEORY,
                'CSE', 'BTECH_CSE', 5, 'rkagrawal.cse@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'CS304', 'Design and Analysis of Algorithms', 4, Course.CourseType.THEORY,
                'CSE', 'BTECH_CSE', 5, 'skumar.cse@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'CS305', 'Database Systems Laboratory', 2, Course.CourseType.LAB,
                'CSE', 'BTECH_CSE', 5, 'dkumar.cse@nitjsr.ac.in', 2, 3, 'COMPUTER_LAB'
            ),
            (
                'CS306', 'Operating Systems and Networks Lab', 2, Course.CourseType.LAB,
                'CSE', 'BTECH_CSE', 5, 'bksingh.cse@nitjsr.ac.in', 2, 3, 'COMPUTER_LAB'
            ),
            (
                'CS307', 'Technical Seminar & Mini Project', 1, Course.CourseType.SEMINAR,
                'CSE', 'BTECH_CSE', 5, 'dkumar.cse@nitjsr.ac.in', 1, 1, 'SEMINAR_HALL'
            ),

            # === B.Tech ECE Semester 3 (Autumn) ===
            (
                'EC201', 'Electronic Devices and Semiconductor Circuits', 4, Course.CourseType.THEORY,
                'ECE', 'BTECH_ECE', 3, 'kksingh.ece@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'EC202', 'Signals and Continuous Systems', 4, Course.CourseType.THEORY,
                'ECE', 'BTECH_ECE', 3, 'akumar.ece@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'EC203', 'Network Theory and Circuit Analysis', 3, Course.CourseType.THEORY,
                'ECE', 'BTECH_ECE', 3, 'bbhowmik.ece@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'EC204', 'Electronic Devices Laboratory', 2, Course.CourseType.LAB,
                'ECE', 'BTECH_ECE', 3, 'akumar.ece@nitjsr.ac.in', 2, 3, 'ELECTRONICS_LAB'
            ),

            # === B.Tech EE Semester 3 (Autumn) ===
            (
                'EE201', 'Electrical Circuit Analysis & Synthesis', 4, Course.CourseType.THEORY,
                'EE', 'BTECH_EE', 3, 'nkumar.ee@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'EE202', 'Electrical Machines - I', 4, Course.CourseType.THEORY,
                'EE', 'BTECH_EE', 3, 'jkumar.ee@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'EE203', 'Electrical Machines Laboratory - I', 2, Course.CourseType.LAB,
                'EE', 'BTECH_EE', 3, 'jkumar.ee@nitjsr.ac.in', 2, 3, 'ELECTRONICS_LAB'
            ),

            # === B.Tech ME Semester 3 (Autumn) ===
            (
                'ME201', 'Engineering Thermodynamics', 4, Course.CourseType.THEORY,
                'ME', 'BTECH_ME', 3, 'rvsharma.me@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'ME202', 'Fluid Mechanics and Hydraulic Machines', 4, Course.CourseType.THEORY,
                'ME', 'BTECH_ME', 3, 'skprasad.me@nitjsr.ac.in', 3, 1, 'CLASSROOM'
            ),
            (
                'ME203', 'Computer Aided Machine Drawing Lab', 2, Course.CourseType.LAB,
                'ME', 'BTECH_ME', 3, 'skprasad.me@nitjsr.ac.in', 2, 3, 'COMPUTER_LAB'
            ),
        ]

        course_obj_map = {}
        for (c_code, c_name, cr, c_type, dept_code, b_code, sem,
             prof_email, w_meet, dur, pref_room) in courses_catalog:

            prof_user = prof_user_map.get(prof_email)
            dept_obj = dept_map.get(dept_code)
            branch_obj = branch_map.get(b_code)

            course, _ = Course.objects.update_or_create(
                code=c_code,
                defaults={
                    'name': c_name,
                    'credit': cr,
                    'course_type': c_type,
                    'department': dept_obj,
                    'branch': branch_obj,
                    'semester': sem,
                    'professor': prof_user,
                    'is_active': True,
                }
            )

            CourseDeliveryRule.objects.update_or_create(
                course=course,
                defaults={
                    'weekly_meetings': w_meet,
                    'duration_slots': dur,
                    'preferred_room_type': pref_room,
                }
            )
            course_obj_map[c_code] = course

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(courses_catalog)} NIT JSR Courses & Delivery Rules seeded"))

        # -------------------------------------------------------------------------
        # 8. CURRICULUM ITEMS (Connecting Courses to Branch & Semester)
        # -------------------------------------------------------------------------
        curriculum_map = {}  # key: (branch_code, semester, course_code) -> CurriculumItem
        for (c_code, c_name, cr, c_type, dept_code, b_code, sem,
             prof_email, w_meet, dur, pref_room) in courses_catalog:
            branch_obj = branch_map[b_code]
            course_obj = course_obj_map[c_code]

            ci, _ = CurriculumItem.objects.update_or_create(
                branch=branch_obj,
                semester_no=sem,
                course=course_obj,
                defaults={'is_elective': False, 'is_active': True}
            )
            curriculum_map[(b_code, sem, c_code)] = ci

        self.stdout.write(self.style.SUCCESS("[OK] Curriculum Items linked across Semesters and Branches"))

        # -------------------------------------------------------------------------
        # 9. COHORTS & INSTRUCTION GROUPS (Sections & Lab Batches)
        # -------------------------------------------------------------------------
        # (branch_code, sem, sec, student_count, lab_groups)
        cohorts_info = [
            ('BTECH_CSE', 3, 'A', 60, [('3A-L1', 'Lab Batch 1', 30), ('3A-L2', 'Lab Batch 2', 30)]),
            ('BTECH_CSE', 3, 'B', 60, [('3B-L1', 'Lab Batch 1', 30), ('3B-L2', 'Lab Batch 2', 30)]),
            ('BTECH_CSE', 5, 'A', 60, [('5A-L1', 'Lab Batch 1', 30), ('5A-L2', 'Lab Batch 2', 30)]),
            ('BTECH_CSE', 5, 'B', 60, [('5B-L1', 'Lab Batch 1', 30), ('5B-L2', 'Lab Batch 2', 30)]),
            ('BTECH_ECE', 3, 'A', 60, [('ECE-3A-L1', 'Lab Batch 1', 30), ('ECE-3A-L2', 'Lab Batch 2', 30)]),
            ('BTECH_EE', 3, 'A', 60, [('EE-3A-L1', 'Lab Batch 1', 30), ('EE-3A-L2', 'Lab Batch 2', 30)]),
            ('BTECH_ME', 3, 'A', 60, [('ME-3A-L1', 'Lab Batch 1', 30), ('ME-3A-L2', 'Lab Batch 2', 30)]),
        ]

        cohort_map = {}  # key: (branch_code, sem, sec) -> Cohort
        groups_map = {}  # key: (cohort, code) -> InstructionGroup

        for b_code, sem, sec, count, lab_grps in cohorts_info:
            branch_obj = branch_map[b_code]
            cohort, _ = Cohort.objects.update_or_create(
                branch=branch_obj,
                term=odd_term,
                semester_no=sem,
                section_code=sec,
                defaults={'student_count': count, 'is_active': True}
            )
            cohort_map[(b_code, sem, sec)] = cohort

            # Create 'ALL' whole class group
            all_grp, _ = InstructionGroup.objects.update_or_create(
                cohort=cohort,
                code='ALL',
                defaults={'name': 'Entire Section', 'size': count, 'is_active': True}
            )
            groups_map[(cohort, 'ALL')] = all_grp

            # Create lab subgroups
            for g_code, g_name, g_size in lab_grps:
                ig, _ = InstructionGroup.objects.update_or_create(
                    cohort=cohort,
                    code=g_code,
                    defaults={'name': g_name, 'size': g_size, 'is_active': True}
                )
                groups_map[(cohort, g_code)] = ig

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(cohorts_info)} Cohorts and Lab Instruction Groups seeded"))

        # -------------------------------------------------------------------------
        # 10. COURSE OFFERINGS & TEACHING ASSIGNMENTS (For Active Odd Term)
        # -------------------------------------------------------------------------
        offering_count = 0
        assignment_count = 0

        for (b_code, sem, sec), cohort in cohort_map.items():
            # Find all curriculum items for this branch & semester
            relevant_items = [
                ci for (b, s, c), ci in curriculum_map.items()
                if b == b_code and s == sem
            ]

            for ci in relevant_items:
                offering, _ = CourseOffering.objects.update_or_create(
                    term=odd_term,
                    cohort=cohort,
                    curriculum_item=ci,
                    defaults={'is_active': True}
                )
                offering_count += 1

                # Assigned Professor
                assigned_prof = ci.course.professor
                if not assigned_prof:
                    assigned_prof = prof_user_map['dkumar.cse@nitjsr.ac.in']

                # If LAB course, assign groups
                if ci.course.course_type == Course.CourseType.LAB:
                    # Find lab groups
                    cohort_groups = [
                        g for (coh, code), g in groups_map.items()
                        if coh == cohort and code != 'ALL'
                    ]
                    for grp in cohort_groups:
                        TeachingAssignment.objects.update_or_create(
                            course_offering=offering,
                            professor=assigned_prof,
                            instruction_group=grp,
                            defaults={'is_primary': True, 'is_active': True}
                        )
                        assignment_count += 1
                else:
                    # Theory or Seminar: assigned to whole cohort (instruction_group=None)
                    TeachingAssignment.objects.update_or_create(
                        course_offering=offering,
                        professor=assigned_prof,
                        instruction_group=None,
                        defaults={'is_primary': True, 'is_active': True}
                    )
                    assignment_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"[OK] {offering_count} Course Offerings & {assignment_count} Teaching Assignments configured"
        ))

        # -------------------------------------------------------------------------
        # 11. PUBLISHED MASTER SCHEDULE VERSION FOR ODD SEMESTER (By Super Admin)
        # -------------------------------------------------------------------------
        master_version, _ = ScheduleVersion.objects.update_or_create(
            term=odd_term,
            version_no=1,
            defaults={
                'name': 'NIT JSR Autumn 2026-27 Master Timetable (Approved)',
                'status': ScheduleVersion.Status.PUBLISHED,
                'notes': 'Official master timetable approved and published by Super Admin (Dr. Gautam Sutradhar, Director NIT Jamshedpur).',
                'created_by': admin_user,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"[OK] Master ScheduleVersion Published: {master_version}"))

        # -------------------------------------------------------------------------
        # 12. SCHEDULED MEETINGS & SLOT RESERVATIONS (Populating Teacher Schedules)
        # -------------------------------------------------------------------------
        # (course_code, b_code, sem, sec, grp_code, weekday, start_slot, duration, room_no)
        # Weekdays: 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri
        scheduled_items = [
            # --- Dr. Dilip Kumar (dkumar.cse@nitjsr.ac.in) ---
            # CS301 (DBMS Theory - Sem 5 Sec A)
            ('CS301', 'BTECH_CSE', 5, 'A', None, 2, 3, 1, 'LH-101'), # Tue 10:30-11:30
            ('CS301', 'BTECH_CSE', 5, 'A', None, 4, 3, 1, 'LH-101'), # Thu 10:30-11:30
            ('CS301', 'BTECH_CSE', 5, 'A', None, 5, 2, 1, 'LH-101'), # Fri 09:30-10:30
            # CS305 (DBMS Lab - Sem 5 Sec A)
            ('CS305', 'BTECH_CSE', 5, 'A', '5A-L1', 2, 5, 3, 'CS-LAB1'), # Tue 14:00-17:00
            ('CS305', 'BTECH_CSE', 5, 'A', '5A-L2', 4, 5, 3, 'CS-LAB1'), # Thu 14:00-17:00
            # CS307 (Seminar - Sem 5 Sec A)
            ('CS307', 'BTECH_CSE', 5, 'A', None, 3, 4, 1, 'AUD-MAIN'), # Wed 11:30-12:30

            # --- Dr. Sanjay Kumar (skumar.cse@nitjsr.ac.in) ---
            # CS201 (DSA Theory - Sem 3 Sec A)
            ('CS201', 'BTECH_CSE', 3, 'A', None, 1, 3, 1, 'LH-101'), # Mon 10:30-11:30
            ('CS201', 'BTECH_CSE', 3, 'A', None, 3, 3, 1, 'LH-101'), # Wed 10:30-11:30
            ('CS201', 'BTECH_CSE', 3, 'A', None, 5, 3, 1, 'LH-101'), # Fri 10:30-11:30
            # CS205 (DSA Lab - Sem 3 Sec A)
            ('CS205', 'BTECH_CSE', 3, 'A', '3A-L1', 1, 5, 3, 'CC-LAB-1'), # Mon 14:00-17:00
            ('CS205', 'BTECH_CSE', 3, 'A', '3A-L2', 3, 5, 3, 'CC-LAB-1'), # Wed 14:00-17:00
            # CS304 (DAA Theory - Sem 5 Sec A)
            ('CS304', 'BTECH_CSE', 5, 'A', None, 2, 2, 1, 'LH-101'), # Tue 09:30-10:30
            ('CS304', 'BTECH_CSE', 5, 'A', None, 3, 2, 1, 'LH-101'), # Wed 09:30-10:30
            ('CS304', 'BTECH_CSE', 5, 'A', None, 4, 2, 1, 'LH-101'), # Thu 09:30-10:30

            # --- Dr. Vinay Kumar (vkumar.cse@nitjsr.ac.in) ---
            # CS202 (Discrete Math - Sem 3 Sec A)
            ('CS202', 'BTECH_CSE', 3, 'A', None, 1, 4, 1, 'LH-101'), # Mon 11:30-12:30
            ('CS202', 'BTECH_CSE', 3, 'A', None, 2, 4, 1, 'LH-101'), # Tue 11:30-12:30
            ('CS202', 'BTECH_CSE', 3, 'A', None, 4, 4, 1, 'LH-101'), # Thu 11:30-12:30
            # CS202 (Discrete Math - Sem 3 Sec B)
            ('CS202', 'BTECH_CSE', 3, 'B', None, 1, 2, 1, 'LH-102'), # Mon 09:30-10:30
            ('CS202', 'BTECH_CSE', 3, 'B', None, 3, 1, 1, 'LH-102'), # Wed 08:30-09:30
            ('CS202', 'BTECH_CSE', 3, 'B', None, 5, 1, 1, 'LH-102'), # Fri 08:30-09:30

            # --- Dr. B. K. Singh (bksingh.cse@nitjsr.ac.in) ---
            # CS302 (OS Theory - Sem 5 Sec A)
            ('CS302', 'BTECH_CSE', 5, 'A', None, 1, 1, 1, 'LH-101'), # Mon 08:30-09:30
            ('CS302', 'BTECH_CSE', 5, 'A', None, 3, 1, 1, 'LH-101'), # Wed 08:30-09:30
            ('CS302', 'BTECH_CSE', 5, 'A', None, 5, 1, 1, 'LH-101'), # Fri 08:30-09:30
            # CS306 (OS Lab - Sem 5 Sec A)
            ('CS306', 'BTECH_CSE', 5, 'A', '5A-L1', 3, 5, 3, 'CC-LAB-2'), # Wed 14:00-17:00
            ('CS306', 'BTECH_CSE', 5, 'A', '5A-L2', 5, 5, 3, 'CC-LAB-2'), # Fri 14:00-17:00

            # --- Dr. Rashmi Sinha (rsinha.ece@nitjsr.ac.in) ---
            # CS203 (Digital Electronics - Sem 3 Sec A)
            ('CS203', 'BTECH_CSE', 3, 'A', None, 2, 1, 1, 'LH-101'), # Tue 08:30-09:30
            ('CS203', 'BTECH_CSE', 3, 'A', None, 3, 4, 1, 'LH-101'), # Wed 11:30-12:30
            ('CS203', 'BTECH_CSE', 3, 'A', None, 4, 1, 1, 'LH-101'), # Thu 08:30-09:30

            # --- Dr. Subrata Dutta (sdutta.cse@nitjsr.ac.in) ---
            # CS204 (OOP Java - Sem 3 Sec A)
            ('CS204', 'BTECH_CSE', 3, 'A', None, 1, 1, 1, 'LH-102'), # Mon 08:30-09:30
            ('CS204', 'BTECH_CSE', 3, 'A', None, 2, 2, 1, 'LH-102'), # Tue 09:30-10:30
            ('CS204', 'BTECH_CSE', 3, 'A', None, 5, 4, 1, 'LH-102'), # Fri 11:30-12:30
            # CS206 (OOP Java Lab - Sem 3 Sec A)
            ('CS206', 'BTECH_CSE', 3, 'A', '3A-L1', 2, 5, 3, 'CC-LAB-2'), # Tue 14:00-17:00
            ('CS206', 'BTECH_CSE', 3, 'A', '3A-L2', 4, 5, 3, 'CC-LAB-2'), # Thu 14:00-17:00

            # --- Dr. R. K. Agrawal (rkagrawal.cse@nitjsr.ac.in) ---
            # CS303 (Computer Networks - Sem 5 Sec A)
            ('CS303', 'BTECH_CSE', 5, 'A', None, 1, 3, 1, 'LH-102'), # Mon 10:30-11:30
            ('CS303', 'BTECH_CSE', 5, 'A', None, 2, 4, 1, 'LH-102'), # Tue 11:30-12:30
            ('CS303', 'BTECH_CSE', 5, 'A', None, 4, 1, 1, 'LH-102'), # Thu 08:30-09:30

            # --- Dr. K. K. Singh (kksingh.ece@nitjsr.ac.in) ---
            # EC201 (Sem 3 Sec A)
            ('EC201', 'BTECH_ECE', 3, 'A', None, 1, 3, 1, 'EC-LH1'), # Mon 10:30-11:30
            ('EC201', 'BTECH_ECE', 3, 'A', None, 2, 3, 1, 'EC-LH1'), # Tue 10:30-11:30
            ('EC201', 'BTECH_ECE', 3, 'A', None, 4, 3, 1, 'EC-LH1'), # Thu 10:30-11:30

            # --- Dr. Amit Kumar (akumar.ece@nitjsr.ac.in) ---
            # EC202 (Sem 3 Sec A)
            ('EC202', 'BTECH_ECE', 3, 'A', None, 1, 4, 1, 'EC-LH1'), # Mon 11:30-12:30
            ('EC202', 'BTECH_ECE', 3, 'A', None, 3, 3, 1, 'EC-LH1'), # Wed 10:30-11:30
            ('EC202', 'BTECH_ECE', 3, 'A', None, 5, 3, 1, 'EC-LH1'), # Fri 10:30-11:30
            # EC204 (Lab - Sem 3 Sec A)
            ('EC204', 'BTECH_ECE', 3, 'A', 'ECE-3A-L1', 2, 5, 3, 'EC-LAB1'), # Tue 14:00-17:00
            ('EC204', 'BTECH_ECE', 3, 'A', 'ECE-3A-L2', 4, 5, 3, 'EC-LAB1'), # Thu 14:00-17:00

            # --- Dr. Niranjan Kumar (nkumar.ee@nitjsr.ac.in) ---
            # EE201 (Sem 3 Sec A)
            ('EE201', 'BTECH_EE', 3, 'A', None, 1, 2, 1, 'EE-LH1'), # Mon 09:30-10:30
            ('EE201', 'BTECH_EE', 3, 'A', None, 3, 2, 1, 'EE-LH1'), # Wed 09:30-10:30
            ('EE201', 'BTECH_EE', 3, 'A', None, 5, 2, 1, 'EE-LH1'), # Fri 09:30-10:30

            # --- Dr. Jitendra Kumar (jkumar.ee@nitjsr.ac.in) ---
            # EE202 (Sem 3 Sec A)
            ('EE202', 'BTECH_EE', 3, 'A', None, 2, 3, 1, 'EE-LH1'), # Tue 10:30-11:30
            ('EE202', 'BTECH_EE', 3, 'A', None, 4, 3, 1, 'EE-LH1'), # Thu 10:30-11:30
            ('EE202', 'BTECH_EE', 3, 'A', None, 5, 4, 1, 'EE-LH1'), # Fri 11:30-12:30
            # EE203 (Lab - Sem 3 Sec A)
            ('EE203', 'BTECH_EE', 3, 'A', 'EE-3A-L1', 1, 5, 3, 'EE-LAB1'), # Mon 14:00-17:00
            ('EE203', 'BTECH_EE', 3, 'A', 'EE-3A-L2', 3, 5, 3, 'EE-LAB1'), # Wed 14:00-17:00

            # --- Dr. R. V. Sharma (rvsharma.me@nitjsr.ac.in) ---
            # ME201 (Sem 3 Sec A)
            ('ME201', 'BTECH_ME', 3, 'A', None, 1, 1, 1, 'LH-201'), # Mon 08:30-09:30
            ('ME201', 'BTECH_ME', 3, 'A', None, 3, 1, 1, 'LH-201'), # Wed 08:30-09:30
            ('ME201', 'BTECH_ME', 3, 'A', None, 5, 1, 1, 'LH-201'), # Fri 08:30-09:30

            # --- Dr. S. K. Prasad (skprasad.me@nitjsr.ac.in) ---
            # ME202 (Sem 3 Sec A)
            ('ME202', 'BTECH_ME', 3, 'A', None, 2, 2, 1, 'LH-201'), # Tue 09:30-10:30
            ('ME202', 'BTECH_ME', 3, 'A', None, 4, 2, 1, 'LH-201'), # Thu 09:30-10:30
            ('ME202', 'BTECH_ME', 3, 'A', None, 5, 3, 1, 'LH-201'), # Fri 10:30-11:30
            # ME203 (Lab - Sem 3 Sec A)
            ('ME203', 'BTECH_ME', 3, 'A', 'ME-3A-L1', 2, 5, 3, 'ME-CAD'), # Tue 14:00-17:00
            ('ME203', 'BTECH_ME', 3, 'A', 'ME-3A-L2', 4, 5, 3, 'ME-CAD'), # Thu 14:00-17:00
        ]

        # Clean existing meetings and slot reservations for master_version
        ScheduledMeeting.objects.filter(schedule_version=master_version).delete()
        ProfessorSlotReservation.objects.filter(schedule_version=master_version).delete()
        RoomSlotReservation.objects.filter(schedule_version=master_version).delete()
        GroupSlotReservation.objects.filter(schedule_version=master_version).delete()

        created_meetings_count = 0
        for (c_code, b_code, sem, sec, grp_code, wday, s_slot, dur, r_no) in scheduled_items:
            cohort = cohort_map.get((b_code, sem, sec))
            ci = curriculum_map.get((b_code, sem, c_code))
            if not cohort or not ci:
                continue

            offering = CourseOffering.objects.filter(
                term=odd_term, cohort=cohort, curriculum_item=ci
            ).first()
            if not offering:
                continue

            target_group = None
            if grp_code:
                target_group = groups_map.get((cohort, grp_code))
                ta = TeachingAssignment.objects.filter(
                    course_offering=offering, instruction_group=target_group
                ).first()
            else:
                ta = TeachingAssignment.objects.filter(
                    course_offering=offering, instruction_group__isnull=True
                ).first()

            if not ta:
                # Fallback to any assignment for this offering
                ta = TeachingAssignment.objects.filter(course_offering=offering).first()

            if not ta:
                continue

            room_obj = Room.objects.filter(
                building__campus=campus, room_no=r_no
            ).first() or Room.objects.filter(room_no=r_no).first()

            if not room_obj:
                continue

            meeting = ScheduledMeeting.objects.create(
                schedule_version=master_version,
                teaching_assignment=ta,
                weekday=wday,
                start_slot=s_slot,
                duration_slots=dur,
                room=room_obj,
                created_by=admin_user,
            )

            # Associate instruction group
            assigned_groups = []
            if target_group:
                assigned_groups.append(target_group)
            elif (cohort, 'ALL') in groups_map:
                assigned_groups.append(groups_map[(cohort, 'ALL')])

            for grp in assigned_groups:
                MeetingInstructionGroup.objects.get_or_create(
                    scheduled_meeting=meeting,
                    instruction_group=grp,
                )

            # Create reservations for each occupied slot
            for slot in range(s_slot, s_slot + dur):
                ProfessorSlotReservation.objects.get_or_create(
                    schedule_version=master_version,
                    professor=ta.professor,
                    weekday=wday,
                    slot_no=slot,
                    defaults={'scheduled_meeting': meeting}
                )
                RoomSlotReservation.objects.get_or_create(
                    schedule_version=master_version,
                    room=room_obj,
                    weekday=wday,
                    slot_no=slot,
                    defaults={'scheduled_meeting': meeting}
                )
                for grp in assigned_groups:
                    GroupSlotReservation.objects.get_or_create(
                        schedule_version=master_version,
                        instruction_group=grp,
                        weekday=wday,
                        slot_no=slot,
                        defaults={'scheduled_meeting': meeting}
                    )

            created_meetings_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"[OK] {created_meetings_count} ScheduledMeetings & Slot Reservations created for Master Version by Super Admin"
        ))

        self.stdout.write(self.style.SUCCESS("""
=============================================================================
NIT Jamshedpur (NIT JSR) Demo Data successfully populated!
=============================================================================
Quick Test Credentials:
  - Super Admin:       admin@nitjsr.ac.in       / Password@123  (Role: SUPER_ADMIN)
  - CSE Coordinator:   dkumar.cse@nitjsr.ac.in  / Password@123  (Role: BRANCH_COORDINATOR, PROFESSOR)
  - ECE Coordinator:   kksingh.ece@nitjsr.ac.in / Password@123  (Role: BRANCH_COORDINATOR, PROFESSOR)
  - EE Coordinator:    nkumar.ee@nitjsr.ac.in   / Password@123  (Role: BRANCH_COORDINATOR, PROFESSOR)
  - Faculty (CSE):     skumar.cse@nitjsr.ac.in  / Password@123  (Role: PROFESSOR)
  - Faculty (CSE):     vkumar.cse@nitjsr.ac.in  / Password@123  (Role: PROFESSOR)
  - Faculty (ECE):     rsinha.ece@nitjsr.ac.in  / Password@123  (Role: PROFESSOR)

Seeded Entities Summary:
  - Campus: NIT Jamshedpur Main Campus (Adityapur)
  - Buildings: DJLHC, CC Block, CSE Dept, ECE Dept, EE Block, Mech Complex, Auditorium
  - Rooms: 17 rooms (Smart Classrooms, Computer Labs, Electronics Labs, Seminar Hall)
  - Departments: CSE, ECE, EE, ME, CE, MME, PIE, CA, MATH
  - Branches: B.Tech CSE, B.Tech ECE, B.Tech EE, B.Tech ME, B.Tech CE, B.Tech MME, M.Tech CSE, MCA
  - Academic Term: Odd Semester 2026-27 (Autumn) & Even Semester 2026-27
  - Courses: 22 NIT JSR Core Courses & Delivery Rules (DSA, DBMS, OS, Java, Networks, Digital Electronics, etc.)
  - Cohorts: B.Tech CSE Sem 3 & 5 (Sec A & B), B.Tech ECE Sem 3, B.Tech EE Sem 3, B.Tech ME Sem 3
  - Teaching Assignments: Theory & Lab subgroups linked to professors
=============================================================================
        """))
