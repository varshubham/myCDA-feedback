# Design Decisions

## Data model

`SessionFeedback` has three foreign keys: the `session`, the `student` the review
is *about*, and the `submitter` who typed it.

Splitting student from submitter is what makes the parent flow work, and it is
what lets uniqueness sit on `(session, student)` rather than
`(session, submitter)`. A review belongs to a student's experience of a session,
and they have exactly one of those whether they described it themselves or their
parent did. So James submitting for Emma on a session Emma already reviewed is
correctly a duplicate, while James submitting for Liam on that same session is
correctly allowed. Uniqueness on submitter gets both cases backwards.

Three separate `PositiveSmallIntegerField`s rather than one score or a JSON blob:
it is a fixed, known schema, and it lets the database average each dimension
independently in one query — exactly what the summary needs. Each carries
`MinValueValidator(1)`/`MaxValueValidator(5)`, which DRF picks up from the model
automatically, so the range rule is not restated in the serializer. I used
`unique_together` rather than the newer `UniqueConstraint` because `FamilyLink`
and `ClassEnrollment` both do.

All six constraints are enforced in `SessionFeedbackSerializer.validate()`.
`submitter` is simply absent from `Meta.fields` — there is no field to write to,
so it cannot be set from the request body. I set `Meta.validators = []` to drop
DRF's auto `UniqueTogetherValidator`: it objects to `student` being optional, and
its stock message is not something you show a parent. The DB constraint still
backs the hand-written check.

## Anonymization

Structural, not by omission. `InstructorSummarySerializer` is a plain
`serializers.Serializer` over computed numbers — deliberately **not** a
`ModelSerializer` over `SessionFeedback`. It declares six numeric fields and has
nowhere to put a student, submitter or note, so no later change can leak one
through it. `rolling_summary_for()` returns floats and counts; raw rows never
leave the model layer. The student-facing and instructor-facing paths are
separate serializers, views and permission classes (`IsStudentOrParent` vs
`IsInstructorOrAdmin`, both from `core.permissions`).

There is no per-session breakdown at all — that is the vector the spec warns
about, since in a small class one session's scores identify who left them.

**Known limit:** aggregation is not anonymity at small N. One student and one
review in the window, and the "average" is that student's rating. Production
would suppress below ~3 entries; I left it out because the threshold is a policy
call rather than a coding one.

## Weighted rolling average

In `SessionFeedback.rolling_summary_for()`:

1. Take the instructor's last 10 **completed** sessions by `scheduled_date`
   descending — a window over sessions, not entries, and not all-time.
2. One grouped query collapses feedback to a mean per session per dimension.
3. Combine those weighted by each session's own duration:
   `sum(duration * session_mean) / sum(duration)`.

Weighting at session level is the deliberate part. Duration is a property of the
session, so a session with one review and one with ten each count by length, not
by turnout. Averaging entries directly would let a busy short session quietly
outweigh a long one.

`overall` is computed from the unrounded totals so it does not inherit
per-dimension rounding error. Sessions in the window with no feedback contribute
nothing to either side of the fraction, and sessions that age out of the window
drop off entirely — which is what makes it rolling. Duration comes from the
existing `Session.duration_minutes` property so the 60-minute fallback stays in
one place. `feedback/tests.py` pins the arithmetic: a 90-minute session averaging
4.0 with a 60-minute session averaging 3.0 must give 3.6, not the unweighted 3.5.

## A bug in the starter

`core/serializers.py` documents populating audit fields from
`get_current_user()`. It does not work under token auth.
`RequestAuditMiddleware` snapshots `request.user` in the middleware stack, where
Django has only set a lazy, session-backed user; DRF resolves the token later,
inside the view, and rebinds `request.user` after the snapshot was taken. The
thread-local therefore evaluates to `AnonymousUser` on every token-authenticated
request — I confirmed this against a live request before working around it.

It is not fixable from inside the middleware, since the ordering is the problem,
so the serializer resolves the submitter from `self.context["request"].user`. I
did not patch `core/`: it is shared by every app and nothing in the suite covers
it. Worth raising separately, because the same bug means `created_by` is silently
never populated on any token-authenticated write today.

## Where I deviated from the spec

- **Added `GET /feedback/eligible-sessions/`.** The frontend needs "completed,
  within 30 days, not yet reviewed" and none of the three listed endpoints
  provide it; doing it client-side would duplicate the 30-day rule in the
  browser, where it drifts. Shares `resolve_student()` with the create path, so
  "who may you act for" is defined once and the two cannot disagree.
- **Added an enrollment check.** Without it any student could post ratings for
  any session, and because the summary is anonymous there would be no way to
  trace the skew.
- **`/my/` filters students on `student=`, not `submitter=`.** Otherwise a
  student whose parent submitted for them sees an empty history while the session
  has silently vanished from their eligible list. Broader than the wording, but
  it shows them more of their own data and never anyone else's.
- **Added `sessions_with_feedback`** so the card can say how many sessions the
  reviews span.
- **Admin summary card has an instructor picker** built from `/classes/`, rather
  than adding a user-listing endpoint for one dropdown.

## Frontend

Cards follow the existing pattern — `"use client"`, `lib/api.ts`,
`DashboardCard`, loading/error/empty states, role-gated in `dashboard/page.tsx`.
The one structural choice is `FeedbackCards.tsx`, a container holding the state
the submit and history cards share: optimistic UI needs it, since on submit the
session must leave the eligible list and the entry join the history together,
and both are restored if the server rejects it.

## Trade-offs

- No edit or delete — the spec only describes submission. `updated_at` is there
  for when that changes.
- No DB `CheckConstraint` on the ratings; validators cover the only write path.
- Two simultaneous submissions for the same `(session, student)` would fail on
  the DB constraint as a 500 rather than a clean 400. Small window, and the data
  stays correct.
- The frontend renders `results` and ignores pagination; it needs a "load more"
  once a student passes 20 reviews.
- Parent grouping in `/my/` happens in the browser — fine at these volumes.
- Tests are backend-focused: 30 covering the validation rules, permissions, the
  uniqueness semantics, the anonymity of the summary payload and the weighted
  arithmetic. The frontend is verified by type-check, production build and a
  manual pass across all five roles.
