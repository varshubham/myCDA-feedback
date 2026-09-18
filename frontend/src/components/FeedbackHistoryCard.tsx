"use client";

import type { SessionFeedback } from "@/lib/types";
import DashboardCard from "./DashboardCard";
import { RATING_DIMENSIONS, formatSessionDate } from "./FeedbackSubmitCard";

interface FeedbackHistoryCardProps {
  entries: SessionFeedback[];
  loading: boolean;
  error: string;
  groupByStudent: boolean;
  pendingIds: number[];
}

function FeedbackRow({ entry, pending }: { entry: SessionFeedback; pending: boolean }) {
  return (
    <li className={`px-5 py-3 ${pending ? "opacity-50" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-gray-900">
            {formatSessionDate(entry.session_detail.scheduled_date)}
            {entry.session_detail.topic ? ` · ${entry.session_detail.topic}` : ""}
          </p>
          <p className="text-xs text-gray-500">
            {entry.session_detail.class_name}
          </p>
        </div>
        <div className="flex shrink-0 gap-3">
          {RATING_DIMENSIONS.map((dimension) => (
            <div key={dimension.key} className="text-center">
              <p className="text-xs text-gray-400">{dimension.label}</p>
              <p className="text-sm font-semibold text-cda-navy">
                {entry[dimension.key]}
              </p>
            </div>
          ))}
        </div>
      </div>
      {entry.note && (
        <p className="mt-2 border-l-2 border-gray-200 pl-2 text-xs text-gray-600">
          {entry.note}
        </p>
      )}
    </li>
  );
}

export default function FeedbackHistoryCard({
  entries,
  loading,
  error,
  groupByStudent,
  pendingIds,
}: FeedbackHistoryCardProps) {
  if (loading) {
    return (
      <DashboardCard title="Feedback History">
        <p className="text-sm text-gray-400">Loading...</p>
      </DashboardCard>
    );
  }

  if (error) {
    return (
      <DashboardCard title="Feedback History">
        <p className="text-sm text-red-500">{error}</p>
      </DashboardCard>
    );
  }

  if (entries.length === 0) {
    return (
      <DashboardCard title="Feedback History">
        <p className="text-sm text-gray-500">No feedback submitted yet.</p>
      </DashboardCard>
    );
  }

  const subtitle = `${entries.length} review${entries.length !== 1 ? "s" : ""}`;

  if (!groupByStudent) {
    return (
      <DashboardCard title="Feedback History" subtitle={subtitle} flush>
        <ul className="divide-y divide-gray-100">
          {entries.map((entry) => (
            <FeedbackRow
              key={entry.id}
              entry={entry}
              pending={pendingIds.includes(entry.id)}
            />
          ))}
        </ul>
      </DashboardCard>
    );
  }

  const byStudent = new Map<number, SessionFeedback[]>();
  entries.forEach((entry) => {
    const id = entry.student_display.id;
    byStudent.set(id, [...(byStudent.get(id) ?? []), entry]);
  });

  return (
    <DashboardCard title="Feedback History" subtitle={subtitle} flush>
      <div className="divide-y divide-gray-100">
        {Array.from(byStudent.entries()).map(([id, studentEntries]) => (
          <div key={id}>
            <p className="bg-gray-50 px-5 py-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
              {studentEntries[0].student_display.display_name}
            </p>
            <ul className="divide-y divide-gray-100">
              {studentEntries.map((entry) => (
                <FeedbackRow
                  key={entry.id}
                  entry={entry}
                  pending={pendingIds.includes(entry.id)}
                />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </DashboardCard>
  );
}
