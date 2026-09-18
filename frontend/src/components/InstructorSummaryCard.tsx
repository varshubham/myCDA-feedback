"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type {
  ClassItem,
  InstructorSummary,
  PaginatedResponse,
  UserMinimal,
  WeightedAverages,
} from "@/lib/types";
import DashboardCard from "./DashboardCard";

const DIMENSIONS: { key: keyof WeightedAverages; label: string }[] = [
  { key: "clarity", label: "Clarity" },
  { key: "engagement", label: "Engagement" },
  { key: "pace", label: "Pace" },
];

function ScoreBar({ label, score }: { label: string; score: number | null }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="text-xs font-medium text-gray-700">{label}</p>
        <p className="text-sm font-semibold text-cda-navy">
          {score === null ? "--" : score.toFixed(2)}
        </p>
      </div>
      <div className="mt-1 h-2 rounded-full bg-gray-100">
        <div
          className="h-2 rounded-full bg-cda-mint"
          style={{ width: `${score === null ? 0 : (score / 5) * 100}%` }}
        />
      </div>
    </div>
  );
}

export default function InstructorSummaryCard() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [instructors, setInstructors] = useState<UserMinimal[]>([]);
  const [instructorId, setInstructorId] = useState<number | null>(null);
  const [summary, setSummary] = useState<InstructorSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAdmin) return;
    api
      .get<PaginatedResponse<ClassItem>>("/classes/")
      .then((res) => {
        const unique = new Map<number, UserMinimal>();
        res.results.forEach((cls) =>
          unique.set(cls.instructor_display.id, cls.instructor_display)
        );
        const list = Array.from(unique.values());
        setInstructors(list);
        setInstructorId(list.length > 0 ? list[0].id : null);
        if (list.length === 0) setLoading(false);
      })
      .catch(() => {
        setError("Could not load instructors.");
        setLoading(false);
      });
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin && instructorId === null) return;
    const query = instructorId ? `?instructor_id=${instructorId}` : "";
    setLoading(true);
    setError("");
    api
      .get<InstructorSummary>(`/feedback/instructor-summary/${query}`)
      .then(setSummary)
      .catch(() => setError("Could not load the feedback summary."))
      .finally(() => setLoading(false));
  }, [isAdmin, instructorId]);

  const picker = isAdmin && instructors.length > 0 && (
    <select
      value={instructorId ?? ""}
      onChange={(e) => setInstructorId(Number(e.target.value))}
      className="rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-700"
    >
      {instructors.map((instructor) => (
        <option key={instructor.id} value={instructor.id}>
          {instructor.display_name}
        </option>
      ))}
    </select>
  );

  if (loading) {
    return (
      <DashboardCard title="Session Feedback" action={picker}>
        <p className="text-sm text-gray-400">Loading...</p>
      </DashboardCard>
    );
  }

  if (error || !summary) {
    return (
      <DashboardCard title="Session Feedback" action={picker}>
        <p className="text-sm text-red-500">
          {error || "No summary available."}
        </p>
      </DashboardCard>
    );
  }

  const { weighted_averages: averages, feedback_count: count } = summary;

  return (
    <DashboardCard
      title="Session Feedback"
      subtitle="Weighted rolling average, last 10 completed sessions"
      action={picker}
    >
      {count === 0 ? (
        <p className="text-sm text-gray-500">
          No feedback has been submitted for these recent sessions yet.
        </p>
      ) : (
        <div className="space-y-4">
          <div className="flex items-end gap-2">
            <span className="text-3xl font-semibold text-cda-navy">
              {averages.overall === null ? "--" : averages.overall.toFixed(2)}
            </span>
            <span className="pb-1 text-sm text-gray-400">/ 5 overall</span>
          </div>

          <div className="space-y-3">
            {DIMENSIONS.map((dimension) => (
              <ScoreBar
                key={dimension.key}
                label={dimension.label}
                score={averages[dimension.key]}
              />
            ))}
          </div>

          <p className="text-xs text-gray-500">
            {count} review{count !== 1 ? "s" : ""} across{" "}
            {summary.sessions_with_feedback} session
            {summary.sessions_with_feedback !== 1 ? "s" : ""}, weighted by session
            length.
          </p>
        </div>
      )}

      <p className="mt-4 border-t border-gray-100 pt-3 text-xs text-gray-400">
        Aggregated and anonymized. Individual reviews, written notes and student
        identities are never shown.
      </p>
    </DashboardCard>
  );
}
