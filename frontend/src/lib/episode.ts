import type { WeeklyEpisode } from "@/lib/types";

export function episodeToMarkdown(e: WeeklyEpisode): string {
  const L: string[] = [];
  L.push(`# WVEdTalk — Weekly Episode`, ``, `**Week of ${e.week_start} – ${e.week_end}**`, ``, `---`, ``);

  L.push(`## WEEKLY RESEARCH PRODUCER NOTES`, ``);
  if (e.editorial_summary) L.push(e.editorial_summary, ``);

  e.selected_stories.forEach((s) => {
    L.push(`### ${s.story}`);
    if (s.location) L.push(`**Location:** ${s.location}`);
    if (s.classification.length) L.push(`**Classification:** ${s.classification.join(" / ")}`);
    const sc: string[] = [];
    if (s.importance !== null) sc.push(`Importance ${s.importance}/10`);
    if (s.podcast_potential !== null) sc.push(`Podcast ${s.podcast_potential}/10`);
    if (sc.length) L.push(`**Scores:** ${sc.join(" · ")}`);
    L.push(``);
    if (s.why_it_made_the_cut) L.push(`**Why It Made the Cut.** ${s.why_it_made_the_cut}`, ``);
    if (s.what_happened_during_week) L.push(`**What Happened During the Week.** ${s.what_happened_during_week}`, ``);
    if (s.what_remains_unresolved) L.push(`**What Remains Unresolved.** ${s.what_remains_unresolved}`, ``);
    if (s.why_it_matters) L.push(`**Why It Matters.** ${s.why_it_matters}`, ``);
    if (s.sources.length) {
      L.push(`**Strongest Sources:**`);
      s.sources.forEach((src) =>
        L.push(`- [${src.title || src.url}](${src.url})${src.outlet ? ` — ${src.outlet}` : ""}`),
      );
      L.push(``);
    }
  });

  if (e.not_selected.length) {
    L.push(`## STORIES CONSIDERED BUT NOT SELECTED`, ``);
    e.not_selected.forEach((n) => {
      L.push(`### ${n.story}`);
      if (n.location) L.push(`**Location:** ${n.location}`);
      if (n.why_considered) L.push(`**Why It Was Considered.** ${n.why_considered}`);
      if (n.why_not_selected) L.push(`**Why It Was Not Selected.** ${n.why_not_selected}`);
      L.push(``);
    });
  }

  if (e.look_ahead.length) {
    L.push(`## LOOK AHEAD`, ``);
    e.look_ahead.forEach((i) => L.push(`- ${i.label}${i.date ? ` (${i.date})` : ""}`));
    L.push(``);
  }

  if (e.chapters && e.chapters.length) {
    L.push(`## CHAPTERS`, ``);
    e.chapters.forEach((c, i) => L.push(`${i + 1}. ${c}`));
    L.push(``);
  }

  L.push(`## RECORDING SCRIPT`, ``, e.recording_script, ``);

  if (e.source_log.length) {
    L.push(`## SOURCE LOG`, ``);
    e.source_log.forEach((src) =>
      L.push(`- [${src.title || src.url}](${src.url})${src.outlet ? ` — ${src.outlet}` : ""}`),
    );
    L.push(``);
  }
  L.push(`---`, `*Produced with ${e.model} using live web research.*`);
  return L.join("\n");
}
