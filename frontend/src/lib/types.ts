export type UserRole = "admin" | "instructor" | "parent" | "student";

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  preferred_name: string;
  role: UserRole;
  display_name: string;
  created_at: string;
  updated_at: string;
  family_links?: FamilyLink[];
}

export interface FamilyLink {
  id: number;
  student: number;
  student_display: UserMinimal;
  relationship: string;
  created_at: string;
}

export interface UserMinimal {
  id: number;
  display_name: string;
  role: UserRole;
}

export interface ClassItem {
  id: number;
  name: string;
  description: string;
  instructor: number;
  instructor_display: UserMinimal;
  is_active: boolean;
  student_count: number;
  created_at: string;
  updated_at: string;
}

export interface Session {
  id: number;
  class_obj: number;
  class_name: string;
  instructor_display: UserMinimal;
  scheduled_date: string;
  status: "scheduled" | "completed" | "cancelled";
  duration_minutes: number;
  topic: string;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  page: number;
  page_size: number;
  results: T[];
}

export interface SessionFeedback {
  id: number;
  session: number;
  session_detail: Session;
  student: number;
  student_display: UserMinimal;
  rating_clarity: number;
  rating_engagement: number;
  rating_pace: number;
  note: string;
  created_at: string;
  updated_at: string;
}

export interface WeightedAverages {
  clarity: number | null;
  engagement: number | null;
  pace: number | null;
  overall: number | null;
}

export interface InstructorSummary {
  weighted_averages: WeightedAverages;
  feedback_count: number;
  sessions_with_feedback: number;
}
