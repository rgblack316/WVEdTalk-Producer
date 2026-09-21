// Hand-mirrored from backend/models/briefing.py — keep both in sync in one edit.

export interface SourceLink {
  title: string;
  url: string;
  outlet: string;
}

export interface Story {
  id: string;
  section: string;
  rank: number | null;
  headline: string;
  location: string;
  classification: string[];
  importance: number | null;
  podcast_potential: number | null;
  what_happened: string;
  why_it_matters: string;
  podcast_angle: string;
  questions: string[];
  original_date: string;
  what_is_new: string;
  previously_known: string;
  unresolved: string;
  watch_next: string;
  sources: SourceLink[];
  is_candidate: boolean;
  notes: string;
}

export interface Trend {
  title: string;
  why_it_matters: string;
  evidence: string[];
  missing_evidence: string[];
  watch_next: string;
}

export interface PodcastIdea {
  working_title: string;
  central_question: string;
  why_worth_exploring: string;
  supporting_stories: string[];
  research_needed: string[];
  potential_guests: string[];
}

export interface Briefing {
  id: string;
  date: string;
  generated_at: string;
  status: string;
  model: string;
  editor_note: string;
  stories: Story[];
  trends: Trend[];
  podcast_ideas: PodcastIdea[];
  source_log: SourceLink[];
  error: string;
}

export interface BriefingSummary {
  date: string;
  generated_at: string;
  status: string;
  story_count: number;
  big_three: string[];
}

export interface RunStatus {
  running: boolean;
  date: string;
  started_at: string | null;
  finished_at: string | null;
  message: string;
  last_error: string;
}

export interface CandidateStory {
  date: string;
  story: Story;
}

export interface DeskConfig {
  recipients: string[];
  watch_terms: string[];
  script_length: string;
  auto_lock_minutes: number;
  timezone: string;
  daily_hour: number;
  daily_minute: number;
  weekly_dow: number;
  weekly_hour: number;
  weekly_minute: number;
}

export interface RunLogEntry {
  id: string;
  kind: string;
  trigger: string;
  status: string;
  label: string;
  detail: string;
  started_at: string;
  finished_at: string;
}

export interface NextRuns {
  daily_next: string;
  weekly_next: string;
}

export interface User {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

export interface AuthState {
  authenticated: boolean;
  user: User | null;
}

export interface CreatedUser {
  user: User;
  temp_password: string;
}

export interface Subscriber {
  email: string;
  active: boolean;
  subscribed_at: string | null;
}

export interface EpisodeStory {
  story: string;
  location: string;
  classification: string[];
  importance: number | null;
  podcast_potential: number | null;
  estimated_minutes: number | null;
  why_it_made_the_cut: string;
  what_happened_during_week: string;
  what_remains_unresolved: string;
  why_it_matters: string;
  sources: SourceLink[];
}

export interface NotSelectedStory {
  story: string;
  location: string;
  why_considered: string;
  why_not_selected: string;
}

export interface LookAheadItem {
  label: string;
  date: string;
}

export interface WeeklyEpisode {
  id: string;
  week_of: string;
  week_start: string;
  week_end: string;
  generated_at: string;
  status: string;
  model: string;
  editorial_summary: string;
  selected_stories: EpisodeStory[];
  not_selected: NotSelectedStory[];
  look_ahead: LookAheadItem[];
  recording_script: string;
  chapters: string[];
  source_log: SourceLink[];
  error: string;
}

export interface EpisodeSummary {
  week_of: string;
  week_start: string;
  week_end: string;
  generated_at: string;
  status: string;
  story_count: number;
  selected_headlines: string[];
}

export interface ProduceStatus {
  running: boolean;
  week_of: string;
  started_at: string | null;
  finished_at: string | null;
  message: string;
  last_error: string;
}

export const SECTION_LABELS: Record<string, string> = {
  big_three: "The Big Three",
  other: "Other Significant Stories",
  developing: "Developing Stories",
  state_policy: "State Policy & Politics",
  k12: "K–12 Education",
  higher_ed: "Higher Education",
};

export const SECTION_ORDER = [
  "big_three",
  "other",
  "developing",
  "state_policy",
  "k12",
  "higher_ed",
];
