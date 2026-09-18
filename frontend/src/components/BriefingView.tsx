import { StoryCard, SourceList } from "@/components/StoryCard";
import { SECTION_LABELS, SECTION_ORDER } from "@/lib/types";
import type { Briefing } from "@/lib/types";

function formatDate(date: string) {
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

export function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-4 border-b-2 border-foreground/80 pb-1 font-heading text-xl font-bold tracking-tight">
      {children}
    </h2>
  );
}

export default function BriefingView({ briefing }: { briefing: Briefing }) {
  const bySection = (s: string) => briefing.stories.filter((st) => st.section === s);

  return (
    <div data-testid="briefing-view">
      <div className="mb-8">
        <p className="text-xs tracking-[0.2em] text-accent uppercase">Daily Briefing</p>
        <h2 className="font-heading text-3xl font-bold tracking-tight" data-testid="briefing-date">
          {formatDate(briefing.date)}
        </h2>
        {briefing.editor_note && (
          <p
            className="mt-3 max-w-3xl border-l-2 border-accent pl-4 text-sm leading-relaxed text-muted-foreground"
            data-testid="briefing-editor-note"
          >
            {briefing.editor_note}
          </p>
        )}
      </div>

      {SECTION_ORDER.map((section) => {
        const stories = bySection(section);
        if (!stories.length) return null;
        const featured = section === "big_three";
        return (
          <section key={section} className="mb-12" data-testid={`section-${section}`}>
            <SectionHeading>{SECTION_LABELS[section]}</SectionHeading>
            <div className={featured ? "space-y-5" : "grid gap-4 md:grid-cols-2"}>
              {stories.map((story) => (
                <StoryCard
                  key={story.id}
                  story={story}
                  date={briefing.date}
                  featured={featured}
                />
              ))}
            </div>
          </section>
        );
      })}

      {briefing.trends.length > 0 && (
        <section className="mb-12" data-testid="section-trends">
          <SectionHeading>Trends Worth Watching</SectionHeading>
          <div className="space-y-4">
            {briefing.trends.map((t, i) => (
              <div key={i} className="rounded-md border border-border bg-card p-5">
                <h3 className="font-heading text-lg font-bold">{t.title}</h3>
                {t.why_it_matters && (
                  <p className="mt-2 text-sm leading-relaxed">{t.why_it_matters}</p>
                )}
                {t.evidence?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs tracking-[0.14em] text-muted-foreground uppercase">
                      Supporting developments
                    </p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                      {t.evidence.map((e, j) => (
                        <li key={j}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {t.missing_evidence?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs tracking-[0.14em] text-muted-foreground uppercase">
                      Evidence still missing
                    </p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                      {t.missing_evidence.map((e, j) => (
                        <li key={j}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {t.watch_next && (
                  <p className="mt-3 text-sm text-muted-foreground">
                    <span className="font-semibold text-foreground">Watch next. </span>
                    {t.watch_next}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {briefing.podcast_ideas.length > 0 && (
        <section className="mb-12" data-testid="section-podcast-ideas">
          <SectionHeading>Podcast Opportunities</SectionHeading>
          <div className="grid gap-4 md:grid-cols-2">
            {briefing.podcast_ideas.map((p, i) => (
              <div key={i} className="rounded-md border border-border bg-secondary/40 p-5">
                <h3 className="font-heading text-lg font-bold">{p.working_title}</h3>
                {p.central_question && (
                  <p className="mt-2 text-sm italic">{p.central_question}</p>
                )}
                {p.why_worth_exploring && (
                  <p className="mt-2 text-sm leading-relaxed">{p.why_worth_exploring}</p>
                )}
                {p.research_needed?.length > 0 && (
                  <p className="mt-3 text-sm text-muted-foreground">
                    <span className="font-semibold text-foreground">Research needed. </span>
                    {p.research_needed.join("; ")}
                  </p>
                )}
                {p.potential_guests?.length > 0 && (
                  <p className="mt-2 text-sm text-muted-foreground">
                    <span className="font-semibold text-foreground">Perspectives. </span>
                    {p.potential_guests.join("; ")}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {briefing.source_log.length > 0 && (
        <section className="mb-6" data-testid="section-source-log">
          <SectionHeading>Source Log</SectionHeading>
          <SourceList sources={briefing.source_log} />
        </section>
      )}

      <p className="mt-10 border-t border-border pt-4 text-xs text-muted-foreground">
        Researched with {briefing.model || "the desk model"} using live web search ·
        generated {new Date(briefing.generated_at).toLocaleString("en-US")} ·
        machine-readable edition:{" "}
        <a className="text-primary hover:underline" href={`/api/briefings/${briefing.date}`}>
          /api/briefings/{briefing.date}
        </a>
      </p>
    </div>
  );
}
