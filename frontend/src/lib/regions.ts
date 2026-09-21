import type { Briefing, Story } from "@/lib/types";

// Approximate WV regional groupings by county. A story matches a region if its
// location text mentions any of the region's counties or the region name itself.
export const WV_REGIONS: { id: string; label: string; counties: string[] }[] = [
  { id: "northern", label: "Northern", counties: ["Hancock", "Brooke", "Ohio", "Marshall", "Wetzel", "Tyler"] },
  {
    id: "north-central",
    label: "North-central",
    counties: ["Monongalia", "Marion", "Harrison", "Taylor", "Preston", "Barbour", "Doddridge", "Gilmer", "Lewis", "Upshur"],
  },
  {
    id: "eastern-panhandle",
    label: "Eastern Panhandle",
    counties: ["Berkeley", "Jefferson", "Morgan", "Hampshire", "Hardy", "Mineral", "Grant"],
  },
  { id: "central", label: "Central", counties: ["Braxton", "Clay", "Calhoun", "Roane", "Webster", "Nicholas"] },
  { id: "mountain", label: "Mountain", counties: ["Tucker", "Pendleton", "Pocahontas", "Randolph", "Greenbrier"] },
  {
    id: "southern",
    label: "Southern",
    counties: ["Raleigh", "Fayette", "Summers", "Monroe", "Mercer", "McDowell", "Wyoming"],
  },
  {
    id: "southwestern",
    label: "Southwestern",
    counties: ["Logan", "Mingo", "Boone", "Lincoln", "Wayne", "Cabell", "Mason"],
  },
  {
    id: "western",
    label: "Western",
    counties: ["Wood", "Wirt", "Jackson", "Pleasants", "Ritchie", "Putnam", "Kanawha"],
  },
];

export function storyMatchesRegion(story: Story, regionId: string): boolean {
  const region = WV_REGIONS.find((r) => r.id === regionId);
  if (!region) return true;
  const loc = story.location.toLowerCase();
  if (loc.includes(region.label.toLowerCase())) return true;
  return region.counties.some((c) => loc.includes(c.toLowerCase()));
}

export function storyMatchesQuery(story: Story, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const hay = [
    story.headline,
    story.location,
    story.what_happened,
    story.why_it_matters,
    ...story.classification,
  ]
    .join(" ")
    .toLowerCase();
  return hay.includes(needle);
}

// Watchlist: a term matches if it appears anywhere in the story's text.
export function matchedWatchTerms(story: Story, terms: string[]): string[] {
  const hay = [story.headline, story.location, story.what_happened, story.why_it_matters]
    .join(" ")
    .toLowerCase();
  return terms.filter((t) => t.trim() && hay.includes(t.trim().toLowerCase()));
}

function fmtDate(date: string) {
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return date;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

const SECTION_TITLES: Record<string, string> = {
  big_three: "THE BIG THREE",
  other: "OTHER SIGNIFICANT STORIES",
  developing: "DEVELOPING STORIES",
  state_policy: "STATE POLICY & POLITICS",
  k12: "K–12 EDUCATION",
  higher_ed: "HIGHER EDUCATION",
};
const ORDER = ["big_three", "other", "developing", "state_policy", "k12", "higher_ed"];

export function briefingToMarkdown(b: Briefing): string {
  const L: string[] = [];
  const logo = typeof window !== "undefined" ? `${window.location.origin}/wvedtalk-logo.png` : "/wvedtalk-logo.png";
  L.push(`![WVEdTalk News Desk](${logo})`, ``);
  L.push(`# WV EDUCATION NEWS DESK`, ``, `**Daily Briefing — ${fmtDate(b.date)}**`, ``);
  if (b.editor_note) L.push(`> ${b.editor_note}`, ``);
  L.push(`---`, ``);

  for (const section of ORDER) {
    const stories = b.stories.filter((s) => s.section === section);
    if (!stories.length) continue;
    L.push(`## ${SECTION_TITLES[section]}`, ``);
    for (const s of stories) {
      L.push(`### ${s.rank ? `${s.rank}. ` : ""}${s.headline}`);
      if (s.location) L.push(`**Location:** ${s.location}`);
      if (s.classification.length) L.push(`**Classification:** ${s.classification.join(" / ")}`);
      const scores: string[] = [];
      if (s.importance !== null) scores.push(`Importance ${s.importance}/10`);
      if (s.podcast_potential !== null) scores.push(`Podcast ${s.podcast_potential}/10`);
      if (scores.length) L.push(`**Scores:** ${scores.join(" · ")}`);
      L.push(``);
      if (s.what_happened) L.push(`**What Happened.** ${s.what_happened}`, ``);
      if (s.why_it_matters) L.push(`**Why It Matters.** ${s.why_it_matters}`, ``);
      if (s.what_is_new) L.push(`**What Is New.** ${s.what_is_new}`, ``);
      if (s.previously_known) L.push(`**Previously Known.** ${s.previously_known}`, ``);
      if (s.unresolved) L.push(`**Unresolved.** ${s.unresolved}`, ``);
      if (s.watch_next) L.push(`**Watch Next.** ${s.watch_next}`, ``);
      if (s.podcast_angle) L.push(`**Podcast Angle.** ${s.podcast_angle}`, ``);
      if (s.questions.length) {
        L.push(`**Questions to Investigate:**`);
        s.questions.forEach((q) => L.push(`- ${q}`));
        L.push(``);
      }
      if (s.sources.length) {
        L.push(`**Sources:**`);
        s.sources.forEach((src) =>
          L.push(`- [${src.title || src.url}](${src.url})${src.outlet ? ` — ${src.outlet}` : ""}`),
        );
        L.push(``);
      }
    }
  }

  if (b.trends.length) {
    L.push(`## TRENDS WORTH WATCHING`, ``);
    b.trends.forEach((t) => {
      L.push(`### ${t.title}`);
      if (t.why_it_matters) L.push(t.why_it_matters, ``);
      t.evidence.forEach((e) => L.push(`- Evidence: ${e}`));
      t.missing_evidence.forEach((e) => L.push(`- Missing: ${e}`));
      if (t.watch_next) L.push(`- Watch next: ${t.watch_next}`);
      L.push(``);
    });
  }

  if (b.podcast_ideas.length) {
    L.push(`## PODCAST OPPORTUNITIES`, ``);
    b.podcast_ideas.forEach((p) => {
      L.push(`### ${p.working_title}`);
      if (p.central_question) L.push(`*${p.central_question}*`, ``);
      if (p.why_worth_exploring) L.push(p.why_worth_exploring, ``);
      if (p.research_needed.length) L.push(`**Research needed:** ${p.research_needed.join("; ")}`);
      if (p.potential_guests.length) L.push(`**Perspectives:** ${p.potential_guests.join("; ")}`);
      L.push(``);
    });
  }

  if (b.source_log.length) {
    L.push(`## SOURCE LOG`, ``);
    b.source_log.forEach((src) =>
      L.push(`- [${src.title || src.url}](${src.url})${src.outlet ? ` — ${src.outlet}` : ""}`),
    );
    L.push(``);
  }

  L.push(`---`, `*Researched with ${b.model} using live web search.*`);
  return L.join("\n");
}
