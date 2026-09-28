import { ExternalLink } from "lucide-react";
import { isExternalUrl } from "@/components/StoryCard";
import type { SourceLink } from "@/lib/types";

// Renders the recording script with chapter headers: any line formatted as "## Title"
// (emitted by the producer between story segments) becomes a styled chapter heading and
// doubles as a podcast chapter title. A quick chapter list is shown above the script.
// When `links` are provided, a "Links to New Sources for This Week" show-notes list of
// clickable hyperlinks is rendered after the script for easy episode note publishing.
export function ScriptView({
  script,
  chapters,
  links,
}: {
  script: string;
  chapters?: string[];
  links?: SourceLink[];
}) {
  const lines = (script || "").split("\n");
  const validLinks = (links ?? []).filter((s) => isExternalUrl(s?.url));
  return (
    <div>
      {chapters && chapters.length > 0 && (
        <div
          className="mb-4 rounded-md border border-border bg-secondary/40 p-4"
          data-testid="episode-chapters"
        >
          <p className="text-xs tracking-[0.14em] text-accent uppercase">Chapters</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
            {chapters.map((c, i) => (
              <li key={`${c}-${i}`} data-testid={`chapter-${i}`}>
                {c}
              </li>
            ))}
          </ol>
        </div>
      )}
      <div className="rounded-md border border-border bg-card p-6 font-sans text-[15px] leading-7 text-foreground/90">
        {lines.map((ln, i) => {
          const h = ln.match(/^\s*##\s+(.+?)\s*$/);
          if (h) {
            return (
              <h4
                key={i}
                className="mt-6 mb-2 border-b border-border pb-1 font-heading text-lg font-bold text-primary first:mt-0"
                data-testid="script-chapter-heading"
              >
                {h[1]}
              </h4>
            );
          }
          if (!ln.trim()) return <div key={i} className="h-3" />;
          return (
            <p key={i} className="whitespace-pre-wrap">
              {ln}
            </p>
          );
        })}
      </div>

      {validLinks.length > 0 && (
        <div className="mt-6 rounded-md border border-border bg-card p-6" data-testid="episode-links">
          <h4 className="mb-3 border-b border-border pb-1 font-heading text-base font-bold text-primary">
            Links to New Sources for This Week:
          </h4>
          <ul className="space-y-1.5">
            {validLinks.map((src, i) => (
              <li key={src.url || i} className="text-sm" data-testid={`episode-link-${i}`}>
                <a
                  href={src.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-start gap-1.5 text-primary hover:underline"
                >
                  <ExternalLink className="mt-1 size-3 shrink-0" />
                  <span>
                    {src.title || src.url}
                    {src.outlet && <span className="text-muted-foreground"> — {src.outlet}</span>}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
