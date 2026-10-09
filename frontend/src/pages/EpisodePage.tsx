import { useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Copy, Download, Clock, Loader2, ListTree, Megaphone, Link2, ShieldCheck, AlertTriangle, Eye, EyeOff, ClipboardCheck } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScoreChip, SourceList, isExternalUrl } from "@/components/StoryCard";
import { ScriptView } from "@/components/ScriptView";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { episodeToMarkdown } from "@/lib/episode";
import type { WeeklyEpisode, DeskConfig, SourceLink } from "@/lib/types";

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

function totalRuntime(script: string): number {
  return Math.max(1, Math.round(script.trim().split(/\s+/).filter(Boolean).length / 150));
}

function StoryTimer({ minutes }: { minutes: number | null }) {
  if (minutes === null || minutes === undefined) return null;
  const m = Math.round(minutes * 10) / 10;
  return (
    <span className="inline-flex items-center gap-1 rounded-sm border border-border bg-secondary/60 px-2 py-0.5 text-xs">
      <Clock className="size-3 text-muted-foreground" />
      <span className="font-semibold tabular-nums">~{m} min</span>
    </span>
  );
}

export default function EpisodePage() {
  const { week = "" } = useParams();
  const qc = useQueryClient();
  const { canEdit } = useAuth();
  const { data: episode, isLoading, error } = useQuery({
    queryKey: ["episode", week],
    queryFn: () => apiGet<WeeklyEpisode>(`/episodes/${week}`),
    retry: false,
  });
  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<DeskConfig>("/settings"),
    staleTime: 60000,
  });
  const hideUnverified = !!config?.hide_unverified_sources;
  const [hideUnverifiedLocal, setHideUnverifiedLocal] = useState(false);

  // Every source link in the episode (each selected story's sources + the show-notes list) and the
  // subset flagged unverified — powers the dead-link report banner at the top of the page.
  const unverifiedCount = useMemo(() => {
    if (!episode) return 0;
    const links: SourceLink[] = [
      ...episode.selected_stories.flatMap((s) => s.sources),
      ...episode.episode_links,
    ];
    return links.filter((l) => isExternalUrl(l.url) && l.verified === false).length;
  }, [episode]);

  // Only the verified show-notes links, for the one-click "copy clean list" into episode descriptions.
  const cleanLinks = useMemo(
    () => (episode?.episode_links ?? []).filter((l) => isExternalUrl(l.url) && l.verified !== false),
    [episode],
  );

  const chapterize = useMutation({
    mutationFn: () => apiPost<WeeklyEpisode>(`/episodes/${week}/chapterize`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["episode", week] });
      toast.success("Chapter headers added");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e)),
  });

  const supportToggle = useMutation({
    mutationFn: (enabled: boolean) => apiPost<WeeklyEpisode>(`/episodes/${week}/support`, { enabled }),
    onSuccess: (_d, enabled) => {
      qc.invalidateQueries({ queryKey: ["episode", week] });
      toast.success(enabled ? "Support read added" : "Support read removed");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e)),
  });

  const relink = useMutation({
    mutationFn: () => apiPost<WeeklyEpisode>(`/episodes/${week}/relink`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["episode", week] });
      toast.success("Source links updated");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e)),
  });

  const verifyLinks = useMutation({
    mutationFn: () => apiPost<WeeklyEpisode>(`/episodes/${week}/verify-links`),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["episode", week] });
      qc.invalidateQueries({ queryKey: ["unverified-count"] });
      const u = [...d.selected_stories.flatMap((s) => s.sources), ...d.episode_links].filter(
        (l) => l.verified === false,
      ).length;
      toast.success(u ? `Re-verified — ${u} link${u === 1 ? "" : "s"} still unverified` : "Re-verified — all sources reachable");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e)),
  });

  const copyCleanLinks = async () => {
    if (!cleanLinks.length) {
      toast.error("No verified links to copy");
      return;
    }
    const text = cleanLinks
      .map((s) => `${s.title || s.url}${s.outlet ? ` — ${s.outlet}` : ""}\n${s.url}`)
      .join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`Copied ${cleanLinks.length} verified link${cleanLinks.length === 1 ? "" : "s"}`);
    } catch {
      toast.error("Clipboard unavailable");
    }
  };

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
      <Link
        to="/episodes"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        data-testid="episode-back-link"
      >
        <ArrowLeft className="size-4" /> Back to weekly producer
      </Link>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading episode…</div>
      ) : episode ? (
        <div data-testid="episode-view">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-heading text-2xl font-bold" data-testid="episode-week">
              WVEdTalk — Week of {fmt(episode.week_start)} – {fmt(episode.week_end)}
            </h3>
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-2 flex items-center gap-1.5 text-sm text-muted-foreground">
                <Clock className="size-3.5" /> ~{totalRuntime(episode.recording_script)} min
              </span>
              <Button variant="outline" size="sm" onClick={copyScript} data-testid="copy-script-button">
                <Copy className="size-4" /> Copy script
              </Button>
              <Button variant="outline" size="sm" onClick={downloadDoc} data-testid="download-episode-button">
                <Download className="size-4" /> Download document
              </Button>
              <Button variant="outline" size="sm" onClick={copyCleanLinks} data-testid="copy-clean-links-button">
                <ClipboardCheck className="size-4" /> Copy verified links
              </Button>
              {canEdit && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={verifyLinks.isPending}
                  onClick={() => verifyLinks.mutate()}
                  data-testid="verify-episode-links-button"
                >
                  {verifyLinks.isPending ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
                  {verifyLinks.isPending ? "Re-verifying…" : "Re-verify links"}
                </Button>
              )}
            </div>
          </div>

          {unverifiedCount > 0 && (
            <div
              className="mb-6 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-sm"
              data-testid="episode-deadlink-report"
            >
              <AlertTriangle className="size-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <span className="font-medium">
                <span data-testid="episode-unverified-count" className="tabular-nums">{unverifiedCount}</span>{" "}
                unverified source link{unverifiedCount === 1 ? "" : "s"} in this episode — verify before citing on air.
              </span>
              <button
                type="button"
                onClick={() => setHideUnverifiedLocal((v) => !v)}
                data-testid="episode-hide-unverified-toggle"
                className="inline-flex items-center gap-1 rounded-sm border border-amber-500/50 px-2 py-0.5 text-xs text-amber-700 transition-colors duration-150 hover:bg-amber-500/20 dark:text-amber-300"
              >
                {hideUnverifiedLocal ? <Eye className="size-3" /> : <EyeOff className="size-3" />}
                {hideUnverifiedLocal ? "Show unverified" : "Hide unverified"}
              </button>
            </div>
          )}

          {episode.editorial_summary && (
            <section className="mb-10">
              <SectionHeading>Weekly Research Producer Notes</SectionHeading>
              <p className="mb-6 max-w-3xl border-l-2 border-accent pl-4 text-sm leading-relaxed text-muted-foreground">
                {episode.editorial_summary}
              </p>
              <div className="space-y-4">
                {episode.selected_stories.map((s, i) => (
                  <article key={s.story || i} className="rounded-md border border-border bg-card p-5">
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
                      <StoryTimer minutes={s.estimated_minutes} />
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
                    {s.sources.length > 0 && (
                      <div className="mt-3 border-t border-border pt-3">
                        <SourceList sources={s.sources} hideUnverified={hideUnverified || hideUnverifiedLocal} />
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}

          {episode.not_selected.length > 0 && (
            <section className="mb-10">
              <SectionHeading>Stories Considered But Not Selected</SectionHeading>
              <div className="grid gap-3 md:grid-cols-2">
                {episode.not_selected.map((n, i) => (
                  <div key={n.story || i} className="rounded-md border border-dashed border-border bg-muted/40 p-4">
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

          <section className="mb-10">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b-2 border-foreground/80 pb-1">
              <h2 className="font-heading text-xl font-bold tracking-tight">Recording Script</h2>
              <div className="flex flex-wrap items-center gap-2">
                {canEdit && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={supportToggle.isPending}
                    onClick={() => supportToggle.mutate(!episode.support_included)}
                    data-testid="support-toggle-button"
                  >
                    {supportToggle.isPending ? <Loader2 className="size-4 animate-spin" /> : <Megaphone className="size-4" />}
                    {episode.support_included ? "Remove support read" : "Add support read"}
                  </Button>
                )}
                {canEdit && (!episode.chapters || episode.chapters.length === 0) && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={chapterize.isPending}
                    onClick={() => chapterize.mutate()}
                    data-testid="chapterize-button"
                  >
                    {chapterize.isPending ? <Loader2 className="size-4 animate-spin" /> : <ListTree className="size-4" />}
                    {chapterize.isPending ? "Adding chapters…" : "Add chapter headers"}
                  </Button>
                )}
                {canEdit && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={relink.isPending}
                    onClick={() => relink.mutate()}
                    data-testid="relink-button"
                  >
                    {relink.isPending ? <Loader2 className="size-4 animate-spin" /> : <Link2 className="size-4" />}
                    {relink.isPending ? "Updating links…" : "Update source links"}
                  </Button>
                )}
              </div>
            </div>
            <ScriptView
              script={episode.recording_script}
              chapters={episode.chapters}
              links={episode.episode_links}
              forceHideUnverified={hideUnverifiedLocal}
            />
          </section>
        </div>
      ) : (
        <div className="py-16 text-center" data-testid="episode-not-found">
          <h2 className="font-heading text-2xl font-bold">Episode unavailable</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {error instanceof ApiError && error.status === 404
              ? `No WVEdTalk episode was produced for the week of ${week}.`
              : "This episode could not be loaded here."}
          </p>
        </div>
      )}
    </DeskLayout>
  );
}
