from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import FamilyLink, User
from classes.models import Class, ClassEnrollment, Session
from feedback.models import SessionFeedback


def make_session(class_obj, days_ago, status_value="completed", duration=60):
    return Session.objects.create(
        class_obj=class_obj,
        scheduled_date=timezone.now() - timedelta(days=days_ago),
        status=status_value,
        session_metadata={"duration_minutes": duration, "topic_covered": "Topic"},
    )


class FeedbackBaseTestCase(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            username="fb.instr", email="fb.instr@cda.test",
            password="testpass123", role="instructor",
        )
        self.parent = User.objects.create_user(
            username="fb.parent", email="fb.parent@cda.test",
            password="testpass123", role="parent",
        )
        self.student = User.objects.create_user(
            username="fb.student", email="fb.student@cda.test",
            password="testpass123", role="student",
        )
        self.sibling = User.objects.create_user(
            username="fb.sibling", email="fb.sibling@cda.test",
            password="testpass123", role="student",
        )
        self.outsider = User.objects.create_user(
            username="fb.outsider", email="fb.outsider@cda.test",
            password="testpass123", role="student",
        )
        FamilyLink.objects.create(parent=self.parent, student=self.student)
        FamilyLink.objects.create(parent=self.parent, student=self.sibling)

        self.cls = Class.objects.create(
            name="Feedback Test Class", instructor=self.instructor
        )
        for student in (self.student, self.sibling, self.outsider):
            ClassEnrollment.objects.create(class_obj=self.cls, student=student)

        self.session = make_session(self.cls, days_ago=5)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def payload(self, **overrides):
        body = {
            "session": self.session.id,
            "rating_clarity": 4,
            "rating_engagement": 5,
            "rating_pace": 3,
            "note": "Useful session.",
        }
        body.update(overrides)
        return body


class FeedbackSubmissionTests(FeedbackBaseTestCase):
    def test_student_submits_for_self(self):
        response = self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = SessionFeedback.objects.get()
        self.assertEqual(entry.student, self.student)
        self.assertEqual(entry.submitter, self.student)

    def test_submitter_is_ignored_in_request_body(self):
        response = self.client_for(self.student).post(
            "/api/v1/feedback/",
            self.payload(submitter=self.outsider.id),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SessionFeedback.objects.get().submitter, self.student)

    def test_parent_submits_for_linked_student(self):
        response = self.client_for(self.parent).post(
            "/api/v1/feedback/",
            self.payload(student=self.student.id),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = SessionFeedback.objects.get()
        self.assertEqual(entry.student, self.student)
        self.assertEqual(entry.submitter, self.parent)

    def test_parent_must_name_a_student(self):
        response = self.client_for(self.parent).post(
            "/api/v1/feedback/", self.payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("student", response.data)

    def test_parent_cannot_submit_for_unlinked_student(self):
        response = self.client_for(self.parent).post(
            "/api/v1/feedback/",
            self.payload(student=self.outsider.id),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("student", response.data)

    def test_student_cannot_submit_for_another_student(self):
        response = self.client_for(self.student).post(
            "/api/v1/feedback/",
            self.payload(student=self.sibling.id),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_instructor_cannot_submit(self):
        response = self.client_for(self.instructor).post(
            "/api/v1/feedback/", self.payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FeedbackValidationTests(FeedbackBaseTestCase):
    def test_rejects_scheduled_session(self):
        upcoming = make_session(self.cls, days_ago=-3, status_value="scheduled")
        response = self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(session=upcoming.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_cancelled_session(self):
        cancelled = make_session(self.cls, days_ago=5, status_value="cancelled")
        response = self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(session=cancelled.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_session_older_than_thirty_days(self):
        stale = make_session(self.cls, days_ago=31)
        response = self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(session=stale.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_student_not_enrolled(self):
        other_class = Class.objects.create(
            name="Unrelated Class", instructor=self.instructor
        )
        foreign = make_session(other_class, days_ago=5)
        response = self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(session=foreign.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_duplicate_for_same_student(self):
        client = self.client_for(self.student)
        client.post("/api/v1/feedback/", self.payload(), format="json")
        response = client.post("/api/v1/feedback/", self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SessionFeedback.objects.count(), 1)

    def test_parent_resubmission_is_a_duplicate(self):
        self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(), format="json"
        )
        response = self.client_for(self.parent).post(
            "/api/v1/feedback/",
            self.payload(student=self.student.id),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SessionFeedback.objects.count(), 1)

    def test_sibling_feedback_on_same_session_is_allowed(self):
        self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(), format="json"
        )
        response = self.client_for(self.parent).post(
            "/api/v1/feedback/",
            self.payload(student=self.sibling.id),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SessionFeedback.objects.count(), 2)

    def test_rejects_rating_below_one(self):
        response = self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(rating_clarity=0), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_rating_above_five(self):
        response = self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(rating_pace=6), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_note_over_five_hundred_characters(self):
        response = self.client_for(self.student).post(
            "/api/v1/feedback/", self.payload(note="x" * 501), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EligibleSessionsTests(FeedbackBaseTestCase):
    def test_lists_only_open_sessions(self):
        make_session(self.cls, days_ago=40)
        make_session(self.cls, days_ago=2, status_value="cancelled")
        response = self.client_for(self.student).get(
            "/api/v1/feedback/eligible-sessions/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["id"] for row in response.data["results"]], [self.session.id]
        )

    def test_reviewed_session_drops_out(self):
        client = self.client_for(self.student)
        client.post("/api/v1/feedback/", self.payload(), format="json")
        response = client.get("/api/v1/feedback/eligible-sessions/")
        self.assertEqual(response.data["count"], 0)

    def test_parent_scopes_by_student(self):
        SessionFeedback.objects.create(
            session=self.session,
            student=self.student,
            submitter=self.parent,
            rating_clarity=4,
            rating_engagement=4,
            rating_pace=4,
        )
        client = self.client_for(self.parent)
        self.assertEqual(
            client.get(
                f"/api/v1/feedback/eligible-sessions/?student_id={self.student.id}"
            ).data["count"],
            0,
        )
        self.assertEqual(
            client.get(
                f"/api/v1/feedback/eligible-sessions/?student_id={self.sibling.id}"
            ).data["count"],
            1,
        )

    def test_parent_cannot_scope_to_unlinked_student(self):
        response = self.client_for(self.parent).get(
            f"/api/v1/feedback/eligible-sessions/?student_id={self.outsider.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MyFeedbackTests(FeedbackBaseTestCase):
    def setUp(self):
        super().setUp()
        self.second_session = make_session(self.cls, days_ago=10)
        SessionFeedback.objects.create(
            session=self.session, student=self.student, submitter=self.parent,
            rating_clarity=4, rating_engagement=4, rating_pace=4,
        )
        SessionFeedback.objects.create(
            session=self.second_session, student=self.sibling, submitter=self.sibling,
            rating_clarity=3, rating_engagement=3, rating_pace=3,
        )
        SessionFeedback.objects.create(
            session=self.session, student=self.outsider, submitter=self.outsider,
            rating_clarity=5, rating_engagement=5, rating_pace=5,
        )

    def test_student_sees_own_feedback_including_parent_submitted(self):
        response = self.client_for(self.student).get("/api/v1/feedback/my/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["student_display"]["id"], self.student.id
        )

    def test_parent_sees_all_linked_students(self):
        response = self.client_for(self.parent).get("/api/v1/feedback/my/")
        self.assertEqual(response.data["count"], 2)
        returned = {row["student_display"]["id"] for row in response.data["results"]}
        self.assertEqual(returned, {self.student.id, self.sibling.id})

    def test_ordered_most_recent_first(self):
        response = self.client_for(self.parent).get("/api/v1/feedback/my/")
        stamps = [row["created_at"] for row in response.data["results"]]
        self.assertEqual(stamps, sorted(stamps, reverse=True))


class InstructorSummaryTests(FeedbackBaseTestCase):
    def setUp(self):
        super().setUp()
        self.long_session = make_session(self.cls, days_ago=5, duration=90)
        self.short_session = make_session(self.cls, days_ago=10, duration=60)

        SessionFeedback.objects.create(
            session=self.long_session, student=self.student, submitter=self.student,
            rating_clarity=4, rating_engagement=5, rating_pace=3, note="Secret note",
        )
        SessionFeedback.objects.create(
            session=self.long_session, student=self.sibling, submitter=self.sibling,
            rating_clarity=4, rating_engagement=3, rating_pace=3,
        )
        SessionFeedback.objects.create(
            session=self.short_session, student=self.student, submitter=self.student,
            rating_clarity=3, rating_engagement=2, rating_pace=5,
        )

    def test_weighted_average_uses_session_duration(self):
        response = self.client_for(self.instructor).get(
            "/api/v1/feedback/instructor-summary/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        averages = response.data["weighted_averages"]
        self.assertAlmostEqual(averages["clarity"], 3.6)
        self.assertAlmostEqual(averages["engagement"], 3.2)
        self.assertAlmostEqual(averages["pace"], 3.8)
        self.assertAlmostEqual(averages["overall"], 3.53)
        self.assertEqual(response.data["feedback_count"], 3)
        self.assertEqual(response.data["sessions_with_feedback"], 2)

    def test_response_exposes_no_identity_or_notes(self):
        response = self.client_for(self.instructor).get(
            "/api/v1/feedback/instructor-summary/"
        )
        body = str(response.data)
        for leak in ("student", "submitter", "note", "Secret note", "fb.student"):
            self.assertNotIn(leak, body)

    def test_window_covers_only_the_last_ten_sessions(self):
        for offset in range(10):
            make_session(self.cls, days_ago=offset * 0.4, duration=60)
        response = self.client_for(self.instructor).get(
            "/api/v1/feedback/instructor-summary/"
        )
        self.assertEqual(response.data["feedback_count"], 0)
        self.assertIsNone(response.data["weighted_averages"]["overall"])

    def test_other_instructor_feedback_is_excluded(self):
        other = User.objects.create_user(
            username="fb.instr2", email="fb.instr2@cda.test",
            password="testpass123", role="instructor",
        )
        response = self.client_for(other).get("/api/v1/feedback/instructor-summary/")
        self.assertEqual(response.data["feedback_count"], 0)

    def test_student_is_denied(self):
        response = self.client_for(self.student).get(
            "/api/v1/feedback/instructor-summary/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_must_name_an_instructor(self):
        admin = User.objects.create_user(
            username="fb.admin", email="fb.admin@cda.test",
            password="testpass123", role="admin",
        )
        client = self.client_for(admin)
        self.assertEqual(
            client.get("/api/v1/feedback/instructor-summary/").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        response = client.get(
            f"/api/v1/feedback/instructor-summary/?instructor_id={self.instructor.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["feedback_count"], 3)
