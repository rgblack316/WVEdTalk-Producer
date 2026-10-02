import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, Star, Ban } from "lucide-react";
import type { SourceLink, Story } from "@/lib/types";

// A source is only a real article link if it's an absolute http(s) URL to another site — never
// empty/relative (renders as href="" → our own briefing page) and never our own host.
export function isExternalUrl(u: string | undefined | null): boolean {
  try {
    const url = new URL(u ?? "");
    return /^https?:$/.test(url.protocol) && url.host !== window.location.host;
  } catch {
    return false;
  }
}

export function ScoreChip({ label, value }: { label: string; value: number | null }) {
  if (value === null || value === undefined) return null;
  return (
    <span className="inline-flex items-baseline gap-1 rounded-sm border border-border bg-secondary/60 px-2 py-0.5 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold tabular-nums">{value}/10</span>
    </span>
  );
}

export function SourceList({ sources }: { sources: SourceLink[] }) {
  const items = (sources ?? []).filter((s) => isExternalUrl(s?.url));
  if (!items.length) return null;
  return (
    <ul className="space-y-1" data-testid="story-source-list">
      {items.map((s, i) => (
        <li key={`${s.url}-${i}`} className="text-sm">
          <a
            href={s.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-start gap-1.5 text-primary underline-offset-4 transition-colors duration-150 hover:underline"
          >
            <ExternalLink className="mt-1 size-3 shrink-0" />
            <span>
              {s.title || s.url}
              {s.outlet && <span className="text-muted-foreground"> — {s.outlet}</span>}
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}

export function StoryCard({
  story,
  date,
  featured = false,
  isPublic = false,
  canFlag = false,
  onToggleCandidate,
  onToggleExclude,
}: {
  story: Story;
  date: string;
  featured?: boolean;
  isPublic?: boolean;
  canFlag?: boolean;
  onToggleCandidate?: () => void;
  onToggleExclude?: () => void;
}) {
  return (
    <article
      className={`wire-rise rounded-md border border-border bg-card p-5 transition-shadow duration-200 hover:shadow-md ${
        featured ? "rule-top pt-5" : ""
      }`}
      data-testid={`story-card-${story.id}`}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        {story.rank && featured && (
          <span className="font-heading text-lg leading-none font-bold text-accent">
            {story.rank}
          </span>
        )}
        {story.location && (
          <span className="tracking-[0.14em] text-muted-foreground uppercase">{story.location}</span>
        )}
        {story.classification?.map((c) => (
          <Badge key={c} variant={c === "DEVELOPING" ? "destructive" : "secondary"}>
            {c}
          </Badge>
        ))}
        {story.is_candidate && !canFlag && (
          <Badge variant="outline" className="gap-1">
            <Star className="size-3 fill-current" /> Episode candidate
          </Badge>
        )}
      </div>

      {isPublic ? (
        <h3
          className={`font-heading font-bold tracking-tight ${featured ? "text-2xl" : "text-lg"}`}
          data-testid={`story-heading-${story.id}`}
        >
          {story.headline}
        </h3>
      ) : (
        <Link
          to={`/briefings/${date}/stories/${story.id}`}
          className="block"
          data-testid={`story-link-${story.id}`}
        >
          <h3
            className={`font-heading font-bold tracking-tight transition-colors duration-150 hover:text-primary ${
              featured ? "text-2xl" : "text-lg"
            }`}
          >
            {story.headline}
          </h3>
        </Link>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <ScoreChip label="Importance" value={story.importance} />
        <ScoreChip label="Podcast" value={story.podcast_potential} />
        {canFlag && (
          <button
            type="button"
            onClick={onToggleCandidate}
            data-testid={`flag-candidate-${story.id}`}
            className={`inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs transition-colors duration-150 ${
              story.is_candidate
                ? "border-accent bg-accent text-accent-foreground"
                : "border-border text-muted-foreground hover:border-accent hover:text-foreground"
            }`}
          >
            <Star className={`size-3 ${story.is_candidate ? "fill-current" : ""}`} />
            {story.is_candidate ? "Episode candidate" : "Flag as candidate"}
          </button>
        )}
        {canFlag && (
          <button
            type="button"
            onClick={onToggleExclude}
            data-testid={`exclude-candidate-${story.id}`}
            className={`inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs transition-colors duration-150 ${
              story.is_excluded
                ? "border-destructive bg-destructive text-white"
                : "border-border text-muted-foreground hover:border-destructive hover:text-foreground"
            }`}
          >
            <Ban className="size-3" />
            {story.is_excluded ? "Excluded" : "Exclude"}
          </button>
        )}
      </div>

      {story.what_happened && (
        <p className="mt-3 text-sm leading-relaxed text-foreground/90">{story.what_happened}</p>
      )}
      {featured && story.why_it_matters && (
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          <span className="font-semibold text-foreground">Why it matters. </span>
          {story.why_it_matters}
        </p>
      )}
      {featured && story.sources?.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <SourceList sources={story.sources.slice(0, 4)} />
        </div>
      )}
    </article>
  );
}
