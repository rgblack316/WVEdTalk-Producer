import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Ban, RotateCcw, Inbox, ExternalLink } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScoreChip } from "@/components/StoryCard";
import { apiGet, apiPatch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { CandidateStory, StorySubmission, Story } from "@/lib/types";

function formatDate(date: string) {
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return date;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function errText(e: unknown) {
  return e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e);
}

export default function Excluded() {
  const qc = useQueryClient();
  const { canEdit } = useAuth();

  const { data: stories, isLoading: loadingStories } = useQuery({
    queryKey: ["excluded-stories"],
    queryFn: () => apiGet<CandidateStory[]>("/excluded-stories"),
  });

  const { data: submissions, isLoading: loadingSubs } = useQuery({
    queryKey: ["submissions"],
    queryFn: () => apiGet<StorySubmission[]>("/submissions"),
  });

  const rejected = useMemo(
    () => (submissions ?? []).filter((s) => s.status === "rejected"),
    [submissions],
  );

  const restoreStory = useMutation({
    mutationFn: ({ date, storyId }: { date: string; storyId: string }) =>
      apiPatch(`/briefings/${date}/stories/${storyId}`, { is_excluded: false }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["excluded-stories"] });
      qc.invalidateQueries({ queryKey: ["briefing"] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
      toast.success("Story restored — it's back in consideration.");
    },
    onError: (e) => toast.error(errText(e)),
  });

  const restoreSubmission = useMutation({
    mutationFn: (id: string) => apiPatch<StorySubmission>(`/submissions/${id}`, { status: "new" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["submissions"] });
      toast.success("Submission restored to the inbox.");
    },
    onError: (e) => toast.error(errText(e)),
  });

  const isLoading = loadingStories || loadingSubs;
  const nothing = (stories?.length ?? 0) === 0 && rejected.length === 0;

  return (
    <DeskLayout>
      <div className="mb-8">
        <p className="text-xs tracking-[0.2em] text-accent uppercase">Review</p>
        <h2 className="font-heading text-3xl font-bold tracking-tight">Excluded &amp; rejected</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Everything you've set aside — briefing stories ruled out of episode consideration and reader
          tips you've rejected. Restore anything to bring it back.
        </p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading…</div>
      ) : nothing ? (
        <div className="py-16 text-center" data-testid="excluded-empty">
          <Ban className="mx-auto mb-4 size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Nothing excluded or rejected. Stories you exclude and tips you reject will collect here for review.
          </p>
        </div>
      ) : (
        <div className="space-y-10">
          <section data-testid="excluded-stories-section">
            <div className="mb-3 flex items-center gap-2 border-b border-border pb-1.5">
              <Ban className="size-4 text-destructive" />
              <h3 className="font-heading text-lg font-bold tracking-tight">Excluded briefing stories</h3>
              <span className="text-xs text-muted-foreground">({stories?.length ?? 0})</span>
            </div>
            {stories && stories.length > 0 ? (
              <div className="space-y-4" data-testid="excluded-stories-list">
                {stories.map(({ date, story }: CandidateStory) => (
                  <ExcludedStoryCard
                    key={`${date}-${story.id}`}
                    date={date}
                    story={story}
                    canEdit={canEdit}
                    busy={restoreStory.isPending}
                    onRestore={() => restoreStory.mutate({ date, storyId: story.id })}
                  />
                ))}
              </div>
            ) : (
              <p className="py-6 text-sm text-muted-foreground" data-testid="excluded-stories-empty">
                No excluded stories.
              </p>
            )}
          </section>

          <section data-testid="rejected-submissions-section">
            <div className="mb-3 flex items-center gap-2 border-b border-border pb-1.5">
              <Inbox className="size-4 text-destructive" />
              <h3 className="font-heading text-lg font-bold tracking-tight">Rejected reader tips</h3>
              <span className="text-xs text-muted-foreground">({rejected.length})</span>
            </div>
            {rejected.length > 0 ? (
              <div className="space-y-4" data-testid="rejected-submissions-list">
                {rejected.map((s) => (
                  <div
                    key={s.id}
                    className="rounded-md border border-border bg-card p-5"
                    data-testid={`rejected-submission-${s.id}`}
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                      <Badge variant="destructive">rejected</Badge>
                      <span className="text-muted-foreground">
                        {new Date(s.submitted_at).toLocaleString()}
                      </span>
                    </div>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-start gap-1 font-heading text-lg font-bold tracking-tight transition-colors hover:text-primary"
                      data-testid={`rejected-url-${s.id}`}
                    >
                      <span className={s.title ? "" : "break-all"}>{s.title || s.url}</span>
                      <ExternalLink className="mt-1 size-4 shrink-0" />
                    </a>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Submitted by <span className="font-medium text-foreground">{s.name}</span>
                    </p>
                    {canEdit && (
                      <div className="mt-3">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={restoreSubmission.isPending}
                          onClick={() => restoreSubmission.mutate(s.id)}
                          data-testid={`restore-submission-${s.id}`}
                        >
                          <RotateCcw className="size-4" /> Restore to inbox
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-6 text-sm text-muted-foreground" data-testid="rejected-submissions-empty">
                No rejected tips.
              </p>
            )}
          </section>
        </div>
      )}
    </DeskLayout>
  );
}

function ExcludedStoryCard({
  date,
  story,
  canEdit,
  busy,
  onRestore,
}: {
  date: string;
  story: Story;
  canEdit: boolean;
  busy: boolean;
  onRestore: () => void;
}) {
  return (
    <div className="rounded-md border border-border bg-card p-5" data-testid={`excluded-story-${story.id}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <Badge variant="outline" className="gap-1 text-destructive">
          <Ban className="size-3" /> {formatDate(date)}
        </Badge>
        {story.location && (
          <span className="tracking-[0.14em] text-muted-foreground uppercase">{story.location}</span>
        )}
        {story.classification?.map((c) => (
          <Badge key={c} variant="secondary">
            {c}
          </Badge>
        ))}
      </div>
      <Link
        to={`/briefings/${date}/stories/${story.id}`}
        className="font-heading text-xl font-bold tracking-tight transition-colors hover:text-primary"
      >
        {story.headline}
      </Link>
      <div className="mt-2 flex flex-wrap gap-2">
        <ScoreChip label="Importance" value={story.importance} />
        <ScoreChip label="Podcast" value={story.podcast_potential} />
      </div>
      {story.what_happened && (
        <p className="mt-3 text-sm leading-relaxed text-foreground/90">{story.what_happened}</p>
      )}
      {canEdit && (
        <div className="mt-3">
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={onRestore}
            data-testid={`restore-story-${story.id}`}
          >
            <RotateCcw className="size-4" /> Restore story
          </Button>
        </div>
      )}
    </div>
  );
}
