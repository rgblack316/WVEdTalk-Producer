import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Mic, Copy, Download, ExternalLink } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScoreChip } from "@/components/StoryCard";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { episodeToMarkdown } from "@/lib/episode";
import type { EpisodeSummary, ProduceStatus, WeeklyEpisode } from "@/lib/types";

function fmt(date: string) {
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return date;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-4 border-b-2 border-foreground/80 pb-1 font-heading text-xl font-bold tracking-tight">
      {children}
    </h2>
  );
}

export default function Episodes() {
  const qc = useQueryClient();

  const { data: episode, isLoading } = useQuery({
    queryKey: ["episode", "latest"],
    queryFn: () => apiGet<WeeklyEpisode | null>("/episodes/latest"),
    refetchInterval: 60000,
  });
  const { data: list } = useQuery({
    queryKey: ["episodes"],
    queryFn: () => apiGet<EpisodeSummary[]>("/episodes"),
  });
  const { data: status } = useQuery({
    queryKey: ["produce-status"],
    queryFn: () => apiGet<ProduceStatus>("/produce-status"),
    refetchInterval: (q) => (q.state.data?.running ? 5000 : 30000),
  });

  const produce = useMutation({
    mutationFn: () => apiPost<ProduceStatus>("/produce"),
    onSuccess: () => {
      toast.success("Producing this week's WVEdTalk episode — this takes a few minutes.");
      qc.invalidateQueries({ queryKey: ["produce-status"] });
    },
    onError: (e) => {
      const msg = e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e);
      toast.error(msg);
    },
  });

  const running = status?.running ?? false;

  const copyScript = async () => {
    if (!episode) return;
    try {
      await navigator.clipboard.writeText(episode.recording_script);
      toast.success("Recording script copied");
    } catch {
      toast.error("Clipboard unavailable — use Download instead");
    }
  };
  const downloadDoc = () => {
    if (!episode) return;
    const blob = new Blob([episodeToMarkdown(episode)], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `wvedtalk-${episode.week_of}.md`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Episode document downloaded");
  };

  return (
    <DeskLayout>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs tracking-[0.2em] text-accent uppercase">WVEdTalk · Weekly Producer</p>
          <h2 className="font-heading text-3xl font-bold tracking-tight">Weekly episode script</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Every Friday at 2:00 PM Eastern, the producer reviews the week's archive, researches the
            full week fresh, and writes a recording-ready WVEdTalk script for Randy Black.
          </p>
        </div>
        <Button
          disabled={running || produce.isPending}
          onClick={() => produce.mutate()}
          data-testid="produce-now-button"
        >
          {running ? <Loader2 className="size-4 animate-spin" /> : <Mic className="size-4" />}
          {running ? "Producing…" : "Produce this week"}
        </Button>
      </div>

      {running && (
        <div className="mb-6 rounded-md border border-accent/40 bg-accent/10 p-3 text-sm" data-testid="produce-status">
          <span className="desk-pulse font-medium">{status?.message || "Producing…"}</span>
        </div>
      )}

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading…</div>
      ) : episode ? (
        <div data-testid="episode-view">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-heading text-2xl font-bold" data-testid="episode-week">
              Week of {fmt(episode.week_start)} – {fmt(episode.week_end)}
            </h3>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={copyScript} data-testid="copy-script-button">
                <Copy className="size-4" /> Copy script
              </Button>
              <Button variant="outline" size="sm" onClick={downloadDoc} data-testid="download-episode-button">
                <Download className="size-4" /> Download document
              </Button>
            </div>
          </div>

          {episode.editorial_summary && (
            <section className="mb-10" data-testid="episode-producer-notes">
              <SectionHeading>Weekly Research Producer Notes</SectionHeading>
              <p className="mb-6 max-w-3xl border-l-2 border-accent pl-4 text-sm leading-relaxed text-muted-foreground">
                {episode.editorial_summary}
              </p>
              <div className="space-y-4">
                {episode.selected_stories.map((s, i) => (
                  <article key={i} className="rounded-md border border-border bg-card p-5" data-testid={`episode-story-${i}`}>
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
                      {s.location && (
                        <span className="tracking-[0.14em] text-muted-foreground uppercase">{s.location}</span>
                      )}
                      {s.classification.map((c) => (
                        <Badge key={c} variant={c === "DEVELOPING" ? "destructive" : "secondary"}>
                          {c}
                        </Badge>
                      ))}
                    </div>
                    <h4 className="font-heading text-lg font-bold">{s.story}</h4>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <ScoreChip label="Importance" value={s.importance} />
                      <ScoreChip label="Podcast" value={s.podcast_potential} />
                    </div>
                    {s.why_it_made_the_cut && (
                      <p className="mt-3 text-sm leading-relaxed">
                        <span className="font-semibold text-accent">Why it made the cut. </span>
                        {s.why_it_made_the_cut}
                      </p>
                    )}
                    {s.what_happened_during_week && (
                      <p className="mt-2 text-sm leading-relaxed">
                        <span className="font-semibold">This week. </span>
                        {s.what_happened_during_week}
                      </p>
                    )}
                    {s.why_it_matters && (
                      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        <span className="font-semibold text-foreground">Why it matters. </span>
                        {s.why_it_matters}
                      </p>
                    )}
                    {s.what_remains_unresolved && (
                      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        <span className="font-semibold text-foreground">Unresolved. </span>
                        {s.what_remains_unresolved}
                      </p>
                    )}
                    {s.sources.length > 0 && (
                      <ul className="mt-3 space-y-1 border-t border-border pt-3">
                        {s.sources.map((src, j) => (
                          <li key={j} className="text-sm">
                            <a href={src.url} target="_blank" rel="noreferrer" className="inline-flex items-start gap-1.5 text-primary hover:underline">
                              <ExternalLink className="mt-1 size-3 shrink-0" />
                              <span>
                                {src.title || src.url}
                                {src.outlet && <span className="text-muted-foreground"> — {src.outlet}</span>}
                              </span>
                            </a>
                          </li>
                        ))}
                      </ul>
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}

          {episode.not_selected.length > 0 && (
            <section className="mb-10" data-testid="episode-not-selected">
              <SectionHeading>Stories Considered But Not Selected</SectionHeading>
              <div className="grid gap-3 md:grid-cols-2">
                {episode.not_selected.map((n, i) => (
                  <div key={i} className="rounded-md border border-dashed border-border bg-muted/40 p-4">
                    <h4 className="font-heading font-bold">{n.story}</h4>
                    {n.location && (
                      <p className="text-xs tracking-[0.14em] text-muted-foreground uppercase">{n.location}</p>
                    )}
                    {n.why_considered && (
                      <p className="mt-2 text-sm">
                        <span className="font-semibold">Considered. </span>
                        {n.why_considered}
                      </p>
                    )}
                    {n.why_not_selected && (
                      <p className="mt-1 text-sm text-muted-foreground">
                        <span className="font-semibold text-foreground">Cut because. </span>
                        {n.why_not_selected}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {episode.look_ahead.length > 0 && (
            <section className="mb-10" data-testid="episode-look-ahead">
              <SectionHeading>Look Ahead</SectionHeading>
              <ul className="space-y-1.5">
                {episode.look_ahead.map((i, idx) => (
                  <li key={idx} className="flex gap-2 text-sm">
                    <span className="font-semibold text-accent">›</span>
                    <span>
                      {i.label}
                      {i.date && <span className="text-muted-foreground"> — {i.date}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="mb-10" data-testid="episode-script">
            <SectionHeading>Recording Script</SectionHeading>
            <div className="rounded-md border border-border bg-card p-6">
              <pre className="font-sans text-[15px] leading-7 whitespace-pre-wrap text-foreground/90">
                {episode.recording_script}
              </pre>
            </div>
          </section>

          {list && list.length > 1 && (
            <section className="mb-6" data-testid="episode-archive">
              <SectionHeading>Past Episodes</SectionHeading>
              <ul className="space-y-1.5">
                {list.map((e) => (
                  <li key={e.week_of} className="text-sm">
                    <Link to={`/episodes/${e.week_of}`} className="text-primary hover:underline">
                      Week of {fmt(e.week_start)} – {fmt(e.week_end)}
                    </Link>
                    <span className="text-muted-foreground"> · {e.story_count} stories</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      ) : (
        <div className="py-16 text-center" data-testid="episode-empty">
          <Mic className="mx-auto mb-4 size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No weekly episode yet. It runs automatically Friday at 2:00 PM Eastern — or produce this
            week's now.
          </p>
        </div>
      )}
    </DeskLayout>
  );
}
