from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import FamilyLink, User
from classes.models import Session
from classes.serializers import SessionSerializer
from core.permissions import IsInstructorOrAdmin, IsStudentOrParent

from .models import FEEDBACK_WINDOW_DAYS, SessionFeedback
from .serializers import (
    InstructorSummarySerializer,
    SessionFeedbackSerializer,
    resolve_student,
)


class FeedbackCreateView(generics.CreateAPIView):
    serializer_class = SessionFeedbackSerializer
    permission_classes = [IsStudentOrParent]


class MyFeedbackView(generics.ListAPIView):
    serializer_class = SessionFeedbackSerializer
    permission_classes = [IsStudentOrParent]

    def get_queryset(self):
        user = self.request.user
        queryset = SessionFeedback.objects.select_related(
            "student",
            "session",
            "session__class_obj",
            "session__class_obj__instructor",
        )
        if user.role == User.Role.STUDENT:
            return queryset.filter(student=user)
        children = FamilyLink.objects.filter(parent=user).values_list(
            "student_id", flat=True
        )
        return queryset.filter(student__in=children)


class EligibleSessionsView(generics.ListAPIView):
    serializer_class = SessionSerializer
    permission_classes = [IsStudentOrParent]

    def get_queryset(self):
        student_id = self.request.query_params.get("student_id")
        student = resolve_student(
            self.request.user,
            get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
            if student_id
            else None,
        )

        reviewed = SessionFeedback.objects.filter(student=student).values_list(
            "session_id", flat=True
        )
        cutoff = timezone.now() - timedelta(days=FEEDBACK_WINDOW_DAYS)
        return (
            Session.objects.filter(
                class_obj__enrollments__student=student,
                class_obj__enrollments__is_active=True,
                status=Session.Status.COMPLETED,
                scheduled_date__gte=cutoff,
            )
            .exclude(id__in=reviewed)
            .select_related("class_obj", "class_obj__instructor")
            .distinct()
        )


class InstructorSummaryView(APIView):
    permission_classes = [IsInstructorOrAdmin]

    def get(self, request):
        instructor = request.user

        if request.user.role == User.Role.ADMIN:
            instructor_id = request.query_params.get("instructor_id")
            if not instructor_id:
                return Response(
                    {"instructor_id": "Admins must name an instructor to summarize."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            instructor = get_object_or_404(
                User, pk=instructor_id, role=User.Role.INSTRUCTOR
            )

        summary = SessionFeedback.rolling_summary_for(instructor)
        return Response(InstructorSummarySerializer(summary).data)
