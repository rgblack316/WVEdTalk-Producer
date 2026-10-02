import { useParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Star, Ban, Sparkles } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { SourceList, ScoreChip } from "@/components/StoryCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { apiGet, apiPatch } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { Briefing, Story } from "@/lib/types";
import { SECTION_LABELS } from "@/lib/types";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  if (!children) return null;
  return (
    <div className="mt-5">
      <h3 className="font-heading text-sm font-bold tracking-[0.14em] text-accent uppercase">
        {label}
      </h3>
      <div className="mt-1.5 text-sm leading-relaxed text-foreground/90">{children}</div>
    </div>
  );
}

export default function StoryDetail() {
  const { date = "", storyId = "" } = useParams();
  const qc = useQueryClient();
  const { canEdit } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["briefing", date],
    queryFn: () => apiGet<Briefing>(`/briefings/${date}`),
    retry: false,
  });

  const story: Story | undefined = data?.stories.find((s) => s.id === storyId);
  const [notes, setNotes] = useState("");
  useEffect(() => {
    if (story) setNotes(story.notes);
  }, [story, setNotes]);

  const update = useMutation({
    mutationFn: (body: { is_candidate?: boolean; is_excluded?: boolean; is_positive?: boolean; notes?: string }) =>
      apiPatch<Briefing>(`/briefings/${date}/stories/${storyId}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["briefing", date] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
      qc.invalidateQueries({ queryKey: ["positive-stories"] });
    },
    onError: () => toast.error("Could not save — try again."),
  });

  return (
    <DeskLayout>
      <Link
        to={`/briefings/${date}`}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        data-testid="story-back-link"
      >
        <ArrowLeft className="size-4" /> Back to briefing
      </Link>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading story…</div>
      ) : story ? (
        <article data-testid="story-detail" className="max-w-3xl">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="tracking-[0.14em] text-muted-foreground uppercase">
              {SECTION_LABELS[story.section] || story.section}
            </span>
            {story.location && (
              <span className="tracking-[0.14em] text-muted-foreground uppercase">
                · {story.location}
              </span>
            )}
            {story.classification?.map((c) => (
              <Badge key={c} variant={c === "DEVELOPING" ? "destructive" : "secondary"}>
                {c}
              </Badge>
            ))}
          </div>

          <h1 className="font-heading text-3xl font-bold tracking-tight">{story.headline}</h1>

          <div className="mt-3 flex flex-wrap gap-2">
            <ScoreChip label="Importance" value={story.importance} />
            <ScoreChip label="Podcast" value={story.podcast_potential} />
          </div>

          <Field label="What Happened">{story.what_happened}</Field>
          <Field label="Why It Matters">{story.why_it_matters}</Field>
          {story.podcast_angle && <Field label="Podcast Angle">{story.podcast_angle}</Field>}

          {story.what_is_new && <Field label="What Is New">{story.what_is_new}</Field>}
          {story.previously_known && (
            <Field label="What Was Previously Known">{story.previously_known}</Field>
          )}
          {story.unresolved && <Field label="What Remains Unresolved">{story.unresolved}</Field>}
          {story.watch_next && <Field label="What To Watch Next">{story.watch_next}</Field>}
          {story.original_date && (
            <Field label="Original Date Identified">{story.original_date}</Field>
          )}

          {story.questions?.length > 0 && (
            <Field label="Questions to Investigate">
              <ul className="list-disc space-y-1 pl-5">
                {story.questions.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
            </Field>
          )}

          {story.sources?.length > 0 && (
            <Field label="Sources">
              <SourceList sources={story.sources} />
            </Field>
          )}

          {canEdit ? (
          <div className="mt-8 rounded-md border border-border bg-secondary/40 p-5" data-testid="podcast-prep-panel">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-heading text-lg font-bold">Podcast prep</h3>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant={story.is_candidate ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    update.mutate({ is_candidate: !story.is_candidate });
                    toast.success(
                      story.is_candidate ? "Removed from candidates" : "Flagged as episode candidate",
                    );
                  }}
                  data-testid="toggle-candidate-button"
                >
                  <Star className={`size-4 ${story.is_candidate ? "fill-current" : ""}`} />
                  {story.is_candidate ? "Episode candidate" : "Flag as candidate"}
                </Button>
                <Button
                  variant={story.is_excluded ? "destructive" : "outline"}
                  size="sm"
                  onClick={() => {
                    update.mutate({ is_excluded: !story.is_excluded });
                    toast.success(
                      story.is_excluded ? "Exclusion removed" : "Excluded from consideration",
                    );
                  }}
                  data-testid="toggle-exclude-button"
                >
                  <Ban className="size-4" />
                  {story.is_excluded ? "Excluded" : "Exclude"}
                </Button>
                <Button
                  variant={story.is_positive ? "default" : "outline"}
                  size="sm"
                  className={story.is_positive ? "bg-emerald-600 text-white hover:bg-emerald-700" : ""}
                  onClick={() => {
                    update.mutate({ is_positive: !story.is_positive });
                    toast.success(
                      story.is_positive ? "Removed from positive stories" : "Flagged to end the episode on",
                    );
                  }}
                  data-testid="toggle-positive-button"
                >
                  <Sparkles className="size-4" />
                  {story.is_positive ? "Positive note" : "Mark positive"}
                </Button>
              </div>
            </div>
            <Textarea
              className="mt-4 min-h-28 bg-background"
              placeholder="Prep notes — angles, guests to book, questions, follow-ups…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              data-testid="notes-textarea"
            />
            <Button
              className="mt-3"
              size="sm"
              disabled={update.isPending || notes === story.notes}
              onClick={() => {
                update.mutate({ notes });
                toast.success("Notes saved");
              }}
              data-testid="save-notes-button"
            >
              Save notes
            </Button>
          </div>
          ) : (story.is_candidate || story.is_positive || story.notes) ? (
            <div
              className="mt-8 rounded-md border border-border bg-secondary/40 p-5"
              data-testid="podcast-prep-readonly"
            >
              <h3 className="font-heading text-lg font-bold">Podcast prep</h3>
              {story.is_candidate && (
                <Badge variant="outline" className="mt-2 gap-1">
                  <Star className="size-3 fill-current" /> Episode candidate
                </Badge>
              )}
              {story.is_positive && (
                <Badge variant="outline" className="mt-2 ml-2 gap-1 text-emerald-700 dark:text-emerald-400">
                  <Sparkles className="size-3" /> Positive note
                </Badge>
              )}
              {story.notes && (
                <p className="mt-3 border-l-2 border-accent pl-3 text-sm text-muted-foreground">
                  {story.notes}
                </p>
              )}
            </div>
          ) : null}
        </article>
      ) : (
        <div className="py-16 text-center" data-testid="story-not-found">
          <h2 className="font-heading text-2xl font-bold">Story not found</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            This story is not part of the {date} edition.
          </p>
        </div>
      )}
    </DeskLayout>
  );
}
