import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Star } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { ScoreChip } from "@/components/StoryCard";
import { apiGet } from "@/lib/api";
import type { CandidateStory } from "@/lib/types";

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

export default function Candidates() {
  const { data, isLoading } = useQuery({
    queryKey: ["candidates"],
    queryFn: () => apiGet<CandidateStory[]>("/candidates"),
  });

  return (
    <DeskLayout>
      <div className="mb-8">
        <p className="text-xs tracking-[0.2em] text-accent uppercase">Podcast Prep</p>
        <h2 className="font-heading text-3xl font-bold tracking-tight">Episode candidates</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Every story flagged across all editions, newest first. Open a story to edit its prep notes.
        </p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading candidates…</div>
      ) : data && data.length > 0 ? (
        <div className="space-y-4" data-testid="candidate-list">
          {data.map(({ date, story }) => (
            <div
              key={story.id}
              className="wire-rise rounded-md border border-border bg-card p-5"
              data-testid={`candidate-${story.id}`}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="outline" className="gap-1">
                  <Star className="size-3 fill-current" />
                  {formatDate(date)}
                </Badge>
                {story.location && (
                  <span className="tracking-[0.14em] text-muted-foreground uppercase">
                    {story.location}
                  </span>
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
              {story.notes && (
                <p className="mt-3 border-l-2 border-accent pl-3 text-sm text-muted-foreground">
                  {story.notes}
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="py-16 text-center" data-testid="candidates-empty">
          <Star className="mx-auto mb-4 size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No episode candidates yet. Open any story and flag it to build the shortlist here.
          </p>
        </div>
      )}
    </DeskLayout>
  );
}
