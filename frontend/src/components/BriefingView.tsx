import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy, Download, Eye, Share2 } from "lucide-react";
import { StoryCard, SourceList } from "@/components/StoryCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiPatch } from "@/lib/api";
import { SECTION_LABELS, SECTION_ORDER } from "@/lib/types";
import type { Briefing, DeskConfig, Story } from "@/lib/types";
import {
  WV_REGIONS,
  briefingToMarkdown,
  matchedWatchTerms,
  storyMatchesQuery,
  storyMatchesRegion,
} from "@/lib/regions";

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

export default function BriefingView({
  briefing,
  isPublic = false,
  canFlag = false,
}: {
  briefing: Briefing;
  isPublic?: boolean;
  canFlag?: boolean;
}) {
  const [region, setRegion] = useState<string>("");
  const [query, setQuery] = useState<string>("");

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<DeskConfig>("/settings"),
    staleTime: 60000,
    enabled: !isPublic, // /settings is authed — skip it on the public share view
  });
  const watchTerms = config?.watch_terms ?? [];

  // Flag/unflag a story as an episode candidate straight from the briefing (editors/admins only —
  // gated by canFlag, which the public share view never sets). Mirrors the toggle on StoryDetail.
  const qc = useQueryClient();
  const toggleCandidate = useMutation({
    mutationFn: (s: Story) =>
      apiPatch<Briefing>(`/briefings/${briefing.date}/stories/${s.id}`, { is_candidate: !s.is_candidate }),
    onSuccess: (_d, s) => {
      qc.invalidateQueries({ queryKey: ["briefing", briefing.date] });
      qc.invalidateQueries({ queryKey: ["briefing", "latest"] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
      toast.success(s.is_candidate ? "Removed from candidates" : "Flagged as episode candidate");
    },
    onError: () => toast.error("Could not update — please try again"),
  });

  const toggleExclude = useMutation({
    mutationFn: (s: Story) =>
      apiPatch<Briefing>(`/briefings/${briefing.date}/stories/${s.id}`, { is_excluded: !s.is_excluded }),
    onSuccess: (_d, s) => {
      qc.invalidateQueries({ queryKey: ["briefing", briefing.date] });
      qc.invalidateQueries({ queryKey: ["briefing", "latest"] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
      toast.success(s.is_excluded ? "Exclusion removed" : "Excluded from consideration");
    },
    onError: () => toast.error("Could not update — please try again"),
  });

  const togglePositive = useMutation({
    mutationFn: (s: Story) =>
      apiPatch<Briefing>(`/briefings/${briefing.date}/stories/${s.id}`, { is_positive: !s.is_positive }),
    onSuccess: (_d, s) => {
      qc.invalidateQueries({ queryKey: ["briefing", briefing.date] });
      qc.invalidateQueries({ queryKey: ["briefing", "latest"] });
      qc.invalidateQueries({ queryKey: ["positive-stories"] });
      toast.success(s.is_positive ? "Removed from positive stories" : "Flagged to end the episode on");
    },
    onError: () => toast.error("Could not update — please try again"),
  });

  const filtered = useMemo(
    () =>
      briefing.stories.filter(
        (s) => (!region || storyMatchesRegion(s, region)) && storyMatchesQuery(s, query),
      ),
    [briefing.stories, region, query],
  );
  const filtering = Boolean(region || query.trim());

  const watchHits = useMemo(() => {
    if (!watchTerms.length) return [];
    const hits = new Set<string>();
    briefing.stories.forEach((s) => matchedWatchTerms(s, watchTerms).forEach((t) => hits.add(t)));
    return [...hits];
  }, [briefing.stories, watchTerms]);

  const bySection = (s: string) => filtered.filter((st) => st.section === s);

  const copyMarkdown = async () => {
    try {
      await navigator.clipboard.writeText(briefingToMarkdown(briefing));
      toast.success("Briefing copied as Markdown");
    } catch {
      toast.error("Clipboard unavailable — use Download instead");
    }
  };

  const downloadMarkdown = () => {
    const blob = new Blob([briefingToMarkdown(briefing)], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `wv-education-desk-${briefing.date}.md`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Markdown downloaded");
  };

  const copyShareLink = async () => {
    try {
      const res = await apiGet<{ path: string }>(`/briefings/${briefing.date}/share`);
      const url = `${window.location.origin}${res.path}`;
      await navigator.clipboard.writeText(url);
      toast.success("Public share link copied — anyone with the link can read this briefing");
    } catch {
      toast.error("Could not create a share link — try again.");
    }
  };

  return (
    <div data-testid="briefing-view">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs tracking-[0.2em] text-accent uppercase">Daily Briefing</p>
          <h2 className="font-heading text-3xl font-bold tracking-tight" data-testid="briefing-date">
            {formatDate(briefing.date)}
          </h2>
        </div>
        <div className="flex gap-2">
          {!isPublic && (
            <Button variant="outline" size="sm" onClick={copyShareLink} data-testid="copy-share-link-button">
              <Share2 className="size-4" /> Copy share link
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={copyMarkdown} data-testid="copy-markdown-button">
            <Copy className="size-4" /> Copy Markdown
          </Button>
          <Button variant="outline" size="sm" onClick={downloadMarkdown} data-testid="download-markdown-button">
            <Download className="size-4" /> Download
          </Button>
        </div>
      </div>

      {briefing.editor_note && (
        <p
          className="mb-6 max-w-3xl border-l-2 border-accent pl-4 text-sm leading-relaxed text-muted-foreground"
          data-testid="briefing-editor-note"
        >
          {briefing.editor_note}
        </p>
      )}

      {watchHits.length > 0 && (
        <div
          className="mb-6 rounded-md border border-accent/40 bg-accent/10 p-4"
          data-testid="watchlist-alert"
        >
          <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Eye className="size-4 text-accent" /> Watchlist matches in today's edition
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {watchHits.map((t) => (
              <Badge key={t} className="bg-accent text-accent-foreground" data-testid={`watch-hit-${t}`}>
                {t}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Region + county/keyword filters */}
      <div className="mb-8 rounded-md border border-border bg-card/60 p-4" data-testid="filter-bar">
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => setRegion("")}
            data-testid="region-all"
            className={`rounded-sm px-2.5 py-1 text-xs transition-colors duration-150 ${
              region === "" ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"
            }`}
          >
            All regions
          </button>
          {WV_REGIONS.map((r) => (
            <button
              key={r.id}
              onClick={() => setRegion(region === r.id ? "" : r.id)}
              data-testid={`region-${r.id}`}
              className={`rounded-sm px-2.5 py-1 text-xs transition-colors duration-150 ${
                region === r.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        <Input
          className="mt-3 max-w-sm"
          placeholder="Search county, school, or keyword…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          data-testid="filter-search-input"
        />
      </div>

      {filtering && (
        <p className="mb-6 text-sm text-muted-foreground" data-testid="filter-count">
          Showing {filtered.length} of {briefing.stories.length} stories.
          {filtered.length === 0 && " No stories match this filter."}
        </p>
      )}

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
                  isPublic={isPublic}
                  canFlag={canFlag && !isPublic}
                  onToggleCandidate={() => toggleCandidate.mutate(story)}
                  onToggleExclude={() => toggleExclude.mutate(story)}
                  onTogglePositive={() => togglePositive.mutate(story)}
                />
              ))}
            </div>
          </section>
        );
      })}

      {!filtering && briefing.trends.length > 0 && (
        <section className="mb-12" data-testid="section-trends">
          <SectionHeading>Trends Worth Watching</SectionHeading>
          <div className="space-y-4">
            {briefing.trends.map((t, i) => (
              <div key={t.title || i} className="rounded-md border border-border bg-card p-5">
                <h3 className="font-heading text-lg font-bold">{t.title}</h3>
                {t.why_it_matters && <p className="mt-2 text-sm leading-relaxed">{t.why_it_matters}</p>}
                {t.evidence?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs tracking-[0.14em] text-muted-foreground uppercase">
                      Supporting developments
                    </p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                      {t.evidence.map((e) => (
                        <li key={e}>{e}</li>
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
                      {t.missing_evidence.map((e) => (
                        <li key={e}>{e}</li>
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

      {!filtering && briefing.podcast_ideas.length > 0 && (
        <section className="mb-12" data-testid="section-podcast-ideas">
          <SectionHeading>Podcast Opportunities</SectionHeading>
          <div className="grid gap-4 md:grid-cols-2">
            {briefing.podcast_ideas.map((p, i) => (
              <div key={p.working_title || i} className="rounded-md border border-border bg-secondary/40 p-5">
                <h3 className="font-heading text-lg font-bold">{p.working_title}</h3>
                {p.central_question && <p className="mt-2 text-sm italic">{p.central_question}</p>}
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

      {!filtering && briefing.source_log.length > 0 && (
        <section className="mb-6" data-testid="section-source-log">
          <SectionHeading>Source Log</SectionHeading>
          <SourceList sources={briefing.source_log} />
        </section>
      )}

      <p className="mt-10 border-t border-border pt-4 text-xs text-muted-foreground">
        Researched with {briefing.model || "the desk model"} using live web search · generated{" "}
        {new Date(briefing.generated_at).toLocaleString("en-US")}
        {!isPublic && (
          <>
            {" "}· machine-readable edition:{" "}
            <a className="text-primary hover:underline" href={`/api/briefings/${briefing.date}`}>
              /api/briefings/{briefing.date}
            </a>
          </>
        )}
      </p>
    </div>
  );
}
