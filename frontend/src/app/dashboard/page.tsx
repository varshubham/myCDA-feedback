"use client";

import { useAuth } from "@/contexts/AuthContext";
import ActiveClassesCard from "@/components/ActiveClassesCard";
import ProfileCard from "@/components/ProfileCard";
import FeedbackCards from "@/components/FeedbackCards";
import InstructorSummaryCard from "@/components/InstructorSummaryCard";

/**
 * myCDA Dashboard
 *
 * Cards are rendered based on the user's role.
 */
export default function DashboardPage() {
  const { user } = useAuth();

  if (!user) return null;

  const canSubmitFeedback = user.role === "student" || user.role === "parent";
  const canSeeSummary = user.role === "instructor" || user.role === "admin";

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-gray-900">Dashboard</h1>
      <p className="mb-6 text-sm text-gray-500">
        Welcome back, {user.display_name}
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Visible to everyone */}
        <ActiveClassesCard />
        <ProfileCard />

        {canSubmitFeedback && <FeedbackCards />}
        {canSeeSummary && <InstructorSummaryCard />}
      </div>
    </div>
  );
}
