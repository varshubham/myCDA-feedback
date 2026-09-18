from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count

from accounts.models import User
from classes.models import Session

FEEDBACK_WINDOW_DAYS = 30
ROLLING_SESSION_LIMIT = 10
RATING_DIMENSIONS = ("clarity", "engagement", "pace")
RATING_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]


class SessionFeedback(models.Model):
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="feedback_received",
        limit_choices_to={"role": "student"},
    )
    submitter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="feedback_submitted",
    )
    rating_clarity = models.PositiveSmallIntegerField(
        validators=RATING_VALIDATORS,
        help_text="How clearly the instructor explained concepts (1-5).",
    )
    rating_engagement = models.PositiveSmallIntegerField(
        validators=RATING_VALIDATORS,
        help_text="How engaging the session was (1-5).",
    )
    rating_pace = models.PositiveSmallIntegerField(
        validators=RATING_VALIDATORS,
        help_text="Whether the pacing felt right (1-5).",
    )
    note = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("session", "student")
        ordering = ["-created_at"]
        verbose_name = "session feedback"
        verbose_name_plural = "session feedback"

    def __str__(self):
        return f"{self.student.get_display_name()} on {self.session}"

    @classmethod
    def rolling_summary_for(cls, instructor):
        sessions = Session.objects.filter(
            class_obj__instructor=instructor,
            status=Session.Status.COMPLETED,
        ).order_by("-scheduled_date")[:ROLLING_SESSION_LIMIT]
        durations = {s.id: s.duration_minutes for s in sessions}

        rows = list(
            cls.objects.filter(session_id__in=durations)
            .values("session_id")
            .annotate(
                clarity=Avg("rating_clarity"),
                engagement=Avg("rating_engagement"),
                pace=Avg("rating_pace"),
                entries=Count("id"),
            )
        )

        weighted = {dimension: 0.0 for dimension in RATING_DIMENSIONS}
        total_weight = 0
        feedback_count = 0

        for row in rows:
            weight = durations[row["session_id"]]
            total_weight += weight
            feedback_count += row["entries"]
            for dimension in RATING_DIMENSIONS:
                weighted[dimension] += row[dimension] * weight

        averages = {
            dimension: round(value / total_weight, 2) if total_weight else None
            for dimension, value in weighted.items()
        }
        averages["overall"] = (
            round(sum(weighted.values()) / (len(RATING_DIMENSIONS) * total_weight), 2)
            if total_weight
            else None
        )

        return {
            "weighted_averages": averages,
            "feedback_count": feedback_count,
            "sessions_with_feedback": len(rows),
        }
