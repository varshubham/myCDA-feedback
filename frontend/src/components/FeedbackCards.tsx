"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type {
  PaginatedResponse,
  Session,
  SessionFeedback,
  UserMinimal,
} from "@/lib/types";
import FeedbackHistoryCard from "./FeedbackHistoryCard";
import FeedbackSubmitCard, { FeedbackDraft } from "./FeedbackSubmitCard";

function readApiError(err: unknown): string {
  if (err instanceof ApiError) {
    const first = Object.values(err.body)[0];
    if (Array.isArray(first) && first.length > 0) return String(first[0]);
    if (typeof first === "string") return first;
  }
  return "Could not submit feedback. Please try again.";
}

function byNewestSession(a: Session, b: Session) {
  return b.scheduled_date.localeCompare(a.scheduled_date);
}

export default function FeedbackCards() {
  const { user } = useAuth();
  const isParent = user?.role === "parent";
  const familyLinks = user?.family_links ?? [];

  const [studentId, setStudentId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [entries, setEntries] = useState<SessionFeedback[]>([]);
  const [pendingIds, setPendingIds] = useState<number[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const nextTempId = useRef(-1);

  useEffect(() => {
    if (isParent && studentId === null && familyLinks.length > 0) {
      setStudentId(familyLinks[0].student_display.id);
    }
  }, [isParent, studentId, familyLinks]);

  useEffect(() => {
    if (isParent && studentId === null) {
      setSessionsLoading(familyLinks.length > 0);
      return;
    }
    const query = studentId ? `?student_id=${studentId}` : "";
    setSessionsLoading(true);
    setSessionsError("");
    api
      .get<PaginatedResponse<Session>>(`/feedback/eligible-sessions/${query}`)
      .then((res) => setSessions(res.results))
      .catch(() => setSessionsError("Could not load eligible sessions."))
      .finally(() => setSessionsLoading(false));
  }, [isParent, studentId, familyLinks.length]);

  useEffect(() => {
    api
      .get<PaginatedResponse<SessionFeedback>>("/feedback/my/")
      .then((res) => setEntries(res.results))
      .catch(() => setHistoryError("Could not load feedback history."))
      .finally(() => setHistoryLoading(false));
  }, []);

  const currentStudent = useCallback((): UserMinimal | null => {
    if (!user) return null;
    if (!isParent) {
      return { id: user.id, display_name: user.display_name, role: user.role };
    }
    const link = familyLinks.find((l) => l.student_display.id === studentId);
    return link ? link.student_display : null;
  }, [user, isParent, familyLinks, studentId]);

  const handleSubmit = async (draft: FeedbackDraft) => {
    const session = sessions.find((s) => s.id === draft.session);
    const student = currentStudent();
    if (!session || !student) return;

    const tempId = nextTempId.current--;
    const now = new Date().toISOString();
    const optimistic: SessionFeedback = {
      id: tempId,
      session: session.id,
      session_detail: session,
      student: student.id,
      student_display: student,
      rating_clarity: draft.rating_clarity,
      rating_engagement: draft.rating_engagement,
      rating_pace: draft.rating_pace,
      note: draft.note,
      created_at: now,
      updated_at: now,
    };

    setSessions((prev) => prev.filter((s) => s.id !== session.id));
    setEntries((prev) => [optimistic, ...prev]);
    setPendingIds((prev) => [...prev, tempId]);

    try {
      const saved = await api.post<SessionFeedback>("/feedback/", {
        ...draft,
        ...(isParent ? { student: student.id } : {}),
      });
      setEntries((prev) => prev.map((e) => (e.id === tempId ? saved : e)));
    } catch (err) {
      setSessions((prev) => [...prev, session].sort(byNewestSession));
      setEntries((prev) => prev.filter((e) => e.id !== tempId));
      throw new Error(readApiError(err));
    } finally {
      setPendingIds((prev) => prev.filter((id) => id !== tempId));
    }
  };

  if (!user) return null;

  return (
    <>
      <FeedbackSubmitCard
        sessions={sessions}
        loading={sessionsLoading}
        error={
          isParent && familyLinks.length === 0
            ? "No students are linked to your account."
            : sessionsError
        }
        familyLinks={isParent ? familyLinks : []}
        studentId={studentId}
        onStudentChange={setStudentId}
        onSubmit={handleSubmit}
      />
      <FeedbackHistoryCard
        entries={entries}
        loading={historyLoading}
        error={historyError}
        groupByStudent={isParent}
        pendingIds={pendingIds}
      />
    </>
  );
}
