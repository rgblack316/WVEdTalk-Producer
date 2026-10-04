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
  is_excluded: boolean;
  is_positive: boolean;
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

export interface CandidateRef {
  date: string;
  story_id: string;
}

export interface DeskConfig {
  recipients: string[];
  watch_terms: string[];
  script_length: string;
  auto_lock_minutes: number;
  auto_thank_on_use: boolean;
  support_segment: string;
  support_default_on: boolean;
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

// Mirrors backend/models/config.py DeliveryFailure / DigestSendResult.
export interface DeliveryFailure {
  email: string;
  error: string;
}

export interface DigestSendResult {
  date: string;
  admin_sent: number;
  admin_failed: number;
  sub_sent: number;
  sub_failed: number;
  failures: DeliveryFailure[];
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

export interface ExportArchive {
  format: string;
  version: number;
  exported_at: string;
  db_name: string;
  counts: Record<string, number>;
  collections: Record<string, unknown[]>;
}

export interface ImportResult {
  mode: string;
  integrity_ok: boolean;
  results: Record<string, { in_archive: number; loaded: number; failed: number; actual: number; match: boolean }>;
}

export interface ImportPreview {
  mode: string;
  dry_run: boolean;
  results: Record<
    string,
    { in_archive: number; existing: number; to_add: number; to_update: number; to_delete: number; resulting: number }
  >;
}

export interface CreatedUser {
  user: User;
  temp_password: string;
}

export interface Contributor {
  name: string;
  email: string;
  submitted_at: string;
}

export interface StorySubmission {
  id: string;
  url: string;
  title: string;
  name: string;
  email: string;
  status: string; // new | used | archived | rejected | merged
  thanked: boolean;
  note: string;
  used_in: string | null;
  used_ref: string | null;
  contributors: Contributor[];
  merged_into: string | null;
  submitted_at: string;
  updated_at: string | null;
}

export interface PublicConfig {
  turnstile_site_key: string | null;
  turnstile_enabled: boolean;
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
  support_included: boolean;
  source_log: SourceLink[];
  episode_links: SourceLink[];
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
