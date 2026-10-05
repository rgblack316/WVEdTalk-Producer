import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Archive as ArchiveIcon, ChevronLeft, ChevronRight } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";
import type { BriefingSummary } from "@/lib/types";

const PER_PAGE = 10;

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

  const [page, setPage] = useState(0);
  const total = data?.length ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PER_PAGE));

  // Keep the page in range if the data shrinks (e.g. after a refetch).
  useEffect(() => {
    if (page > pageCount - 1) setPage(pageCount - 1);
  }, [page, pageCount]);

  const pageItems = useMemo(
    () => (data ?? []).slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE),
    [data, page],
  );

  const from = total === 0 ? 0 : page * PER_PAGE + 1;
  const to = Math.min(page * PER_PAGE + PER_PAGE, total);

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
        <>
          <div className="space-y-3" data-testid="archive-list">
            {pageItems.map((b) => (
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
                      <li key={h} className="flex gap-2">
                        <span className="font-heading font-bold text-accent">{i + 1}</span>
                        <span>{h}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Link>
            ))}
          </div>

          {pageCount > 1 && (
            <div
              className="mt-6 flex items-center justify-between gap-4 border-t border-border pt-4"
              data-testid="archive-pagination"
            >
              <span className="text-xs text-muted-foreground" data-testid="archive-range">
                Showing {from}–{to} of {total}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  data-testid="archive-prev"
                >
                  <ChevronLeft className="size-4" /> Previous
                </Button>
                <span className="text-xs text-muted-foreground tabular-nums" data-testid="archive-page-indicator">
                  Page {page + 1} of {pageCount}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= pageCount - 1}
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  data-testid="archive-next"
                >
                  Next <ChevronRight className="size-4" />
                </Button>
              </div>
            </div>
          )}
        </>
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
