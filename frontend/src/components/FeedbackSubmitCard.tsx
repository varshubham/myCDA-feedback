"use client";

import { useState } from "react";
import type { FamilyLink, Session } from "@/lib/types";
import DashboardCard from "./DashboardCard";

export const RATING_DIMENSIONS = [
  { key: "rating_clarity", label: "Clarity", hint: "How clearly concepts were explained" },
  { key: "rating_engagement", label: "Engagement", hint: "How engaging the session was" },
  { key: "rating_pace", label: "Pace", hint: "Whether the pacing felt right" },
] as const;

export type RatingKey = (typeof RATING_DIMENSIONS)[number]["key"];

export interface FeedbackDraft {
  session: number;
  rating_clarity: number;
  rating_engagement: number;
  rating_pace: number;
  note: string;
}

const NOTE_LIMIT = 500;

export function formatSessionDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function StarRating({
  value,
  onChange,
  label,
}: {
  value: number;
  onChange: (next: number) => void;
  label: string;
}) {
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((score) => (
        <button
          key={score}
          type="button"
          onClick={() => onChange(score)}
          aria-label={`${label}: ${score} of 5`}
          aria-pressed={value === score}
          className={`h-8 w-8 rounded-md border text-sm font-medium transition-colors ${
            score <= value
              ? "border-cda-gold bg-cda-gold/30 text-cda-navy"
              : "border-gray-200 text-gray-300 hover:border-gray-300"
          }`}
        >
          ★
        </button>
      ))}
    </div>
  );
}

interface FeedbackSubmitCardProps {
  sessions: Session[];
  loading: boolean;
  error: string;
  familyLinks: FamilyLink[];
  studentId: number | null;
  onStudentChange: (studentId: number) => void;
  onSubmit: (draft: FeedbackDraft) => Promise<void>;
}

export default function FeedbackSubmitCard({
  sessions,
  loading,
  error,
  familyLinks,
  studentId,
  onStudentChange,
  onSubmit,
}: FeedbackSubmitCardProps) {
  const isParent = familyLinks.length > 0;
  const [openSessionId, setOpenSessionId] = useState<number | null>(null);
  const [ratings, setRatings] = useState<Record<RatingKey, number>>({
    rating_clarity: 0,
    rating_engagement: 0,
    rating_pace: 0,
  });
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const resetForm = () => {
    setOpenSessionId(null);
    setRatings({ rating_clarity: 0, rating_engagement: 0, rating_pace: 0 });
    setNote("");
    setFormError("");
  };

  const complete = RATING_DIMENSIONS.every((d) => ratings[d.key] > 0);

  const handleSubmit = async (sessionId: number) => {
    if (!complete || saving) return;
    setSaving(true);
    setFormError("");
    const draft = { session: sessionId, ...ratings, note };
    try {
      await onSubmit(draft);
      resetForm();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not submit feedback.");
    } finally {
      setSaving(false);
    }
  };

  const studentPicker = isParent && (
    <select
      value={studentId ?? ""}
      onChange={(e) => {
        resetForm();
        onStudentChange(Number(e.target.value));
      }}
      className="rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-700"
    >
      {familyLinks.map((link) => (
        <option key={link.id} value={link.student_display.id}>
          {link.student_display.display_name}
        </option>
      ))}
    </select>
  );

  return (
    <DashboardCard
      title="Leave Session Feedback"
      subtitle="Completed sessions from the last 30 days"
      action={studentPicker}
      flush
    >
      {loading && <p className="px-5 py-4 text-sm text-gray-400">Loading...</p>}

      {!loading && error && (
        <p className="px-5 py-4 text-sm text-red-500">{error}</p>
      )}

      {!loading && !error && sessions.length === 0 && (
        <p className="px-5 py-4 text-sm text-gray-500">
          Nothing to review right now.
        </p>
      )}

      {!loading && !error && sessions.length > 0 && (
        <ul className="divide-y divide-gray-100">
          {sessions.map((session) => {
            const open = openSessionId === session.id;
            return (
              <li key={session.id} className="px-5 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {formatSessionDate(session.scheduled_date)}
                      {session.topic ? ` · ${session.topic}` : ""}
                    </p>
                    <p className="text-xs text-gray-500">{session.class_name}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => (open ? resetForm() : setOpenSessionId(session.id))}
                    className="shrink-0 rounded-md border border-gray-200 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
                  >
                    {open ? "Cancel" : "Review"}
                  </button>
                </div>

                {open && (
                  <div className="mt-3 space-y-3">
                    {RATING_DIMENSIONS.map((dimension) => (
                      <div
                        key={dimension.key}
                        className="flex items-center justify-between gap-3"
                      >
                        <div>
                          <p className="text-xs font-medium text-gray-700">
                            {dimension.label}
                          </p>
                          <p className="text-xs text-gray-400">{dimension.hint}</p>
                        </div>
                        <StarRating
                          label={dimension.label}
                          value={ratings[dimension.key]}
                          onChange={(next) =>
                            setRatings((prev) => ({ ...prev, [dimension.key]: next }))
                          }
                        />
                      </div>
                    ))}

                    <div>
                      <textarea
                        value={note}
                        maxLength={NOTE_LIMIT}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Anything else worth sharing? (optional)"
                        rows={3}
                        className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-cda-blue focus:outline-none"
                      />
                      <p className="mt-1 text-right text-xs text-gray-400">
                        {note.length}/{NOTE_LIMIT}
                      </p>
                    </div>

                    {formError && (
                      <p className="text-xs text-red-500">{formError}</p>
                    )}

                    <button
                      type="button"
                      disabled={!complete || saving}
                      onClick={() => handleSubmit(session.id)}
                      className="w-full rounded-md bg-cda-navy px-3 py-2 text-sm font-medium text-white transition-opacity disabled:opacity-40"
                    >
                      {saving ? "Submitting..." : "Submit feedback"}
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </DashboardCard>
  );
}
