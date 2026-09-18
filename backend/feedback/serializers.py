from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from accounts.models import FamilyLink, User
from accounts.serializers import UserMinimalSerializer
from classes.models import ClassEnrollment, Session
from classes.serializers import SessionSerializer
from core.serializers import BaseModelSerializer

from .models import FEEDBACK_WINDOW_DAYS, SessionFeedback


def resolve_student(submitter, student):
    if submitter.role == User.Role.STUDENT:
        if student is not None and student != submitter:
            raise serializers.ValidationError(
                {"student": "You can only submit feedback for yourself."}
            )
        return submitter

    if student is None:
        raise serializers.ValidationError(
            {"student": "Select which student this feedback is for."}
        )
    if not FamilyLink.objects.filter(parent=submitter, student=student).exists():
        raise serializers.ValidationError(
            {"student": "You are not linked to that student."}
        )
    return student


class SessionFeedbackSerializer(BaseModelSerializer):
    student = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.STUDENT),
        required=False,
    )
    student_display = UserMinimalSerializer(source="student", read_only=True)
    session_detail = SessionSerializer(source="session", read_only=True)

    class Meta:
        model = SessionFeedback
        fields = [
            "id",
            "session",
            "session_detail",
            "student",
            "student_display",
            "rating_clarity",
            "rating_engagement",
            "rating_pace",
            "note",
            "created_at",
            "updated_at",
        ]
        validators = []

    def validate(self, data):
        submitter = self.context["request"].user
        student = resolve_student(submitter, data.get("student"))
        session = data["session"]

        if session.status != Session.Status.COMPLETED:
            raise serializers.ValidationError(
                {"session": "Feedback is only accepted for completed sessions."}
            )

        cutoff = timezone.now() - timedelta(days=FEEDBACK_WINDOW_DAYS)
        if session.scheduled_date < cutoff:
            raise serializers.ValidationError(
                {
                    "session": f"This session closed for feedback "
                    f"{FEEDBACK_WINDOW_DAYS} days after it ran."
                }
            )

        if not ClassEnrollment.objects.filter(
            class_obj=session.class_obj, student=student, is_active=True
        ).exists():
            raise serializers.ValidationError(
                {"session": "That student is not enrolled in this class."}
            )

        if SessionFeedback.objects.filter(session=session, student=student).exists():
            raise serializers.ValidationError(
                {"session": "Feedback has already been submitted for this session."}
            )

        data["student"] = student
        data["submitter"] = submitter
        return data


class WeightedAveragesSerializer(serializers.Serializer):
    clarity = serializers.FloatField(allow_null=True)
    engagement = serializers.FloatField(allow_null=True)
    pace = serializers.FloatField(allow_null=True)
    overall = serializers.FloatField(allow_null=True)


class InstructorSummarySerializer(serializers.Serializer):
    weighted_averages = WeightedAveragesSerializer()
    feedback_count = serializers.IntegerField()
    sessions_with_feedback = serializers.IntegerField()
