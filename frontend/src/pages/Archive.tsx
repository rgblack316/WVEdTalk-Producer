import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Archive as ArchiveIcon } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { apiGet } from "@/lib/api";
import type { BriefingSummary } from "@/lib/types";

function formatDate(date: string) {
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return date;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    weekday: "short",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export default function Archive() {
  const { data, isLoading } = useQuery({
    queryKey: ["briefings"],
    queryFn: () => apiGet<BriefingSummary[]>("/briefings"),
  });

  return (
    <DeskLayout>
      <div className="mb-8">
        <p className="text-xs tracking-[0.2em] text-accent uppercase">Archive</p>
        <h2 className="font-heading text-3xl font-bold tracking-tight">Past editions</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Every daily briefing, newest first. Each edition opens to its full statewide workup.
        </p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading archive…</div>
      ) : data && data.length > 0 ? (
        <div className="space-y-3" data-testid="archive-list">
          {data.map((b) => (
            <Link
              key={b.date}
              to={`/briefings/${b.date}`}
              data-testid={`archive-item-${b.date}`}
              className="wire-rise block rounded-md border border-border bg-card p-5 transition-shadow duration-200 hover:shadow-md"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-heading text-xl font-bold">{formatDate(b.date)}</h3>
                <Badge variant="secondary">{b.story_count} stories</Badge>
              </div>
              {b.big_three.length > 0 && (
                <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
                  {b.big_three.map((h, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="font-heading font-bold text-accent">{i + 1}</span>
                      <span>{h}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Link>
          ))}
        </div>
      ) : (
        <div className="py-16 text-center" data-testid="archive-empty">
          <ArchiveIcon className="mx-auto mb-4 size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No editions yet. Use <span className="font-semibold text-foreground">Run now</span> to
            generate the first briefing.
          </p>
        </div>
      )}
    </DeskLayout>
  );
}
