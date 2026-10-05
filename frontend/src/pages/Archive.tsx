import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Archive as ArchiveIcon, ChevronLeft, ChevronRight } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";
import type { BriefingSummary } from "@/lib/types";

const PER_PAGE_OPTIONS = [10, 25, 50];
const PER_PAGE_STORAGE_KEY = "wvedtalk.archive.perPage";
const ORDER_STORAGE_KEY = "wvedtalk.archive.order";

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

// A compact page list: first, last, current and its neighbours, with "…" filling the gaps.
function pageList(current: number, count: number): (number | "ellipsis")[] {
  const keep = new Set<number>([0, count - 1, current, current - 1, current + 1]);
  const sorted = [...keep].filter((p) => p >= 0 && p < count).sort((a, b) => a - b);
  const out: (number | "ellipsis")[] = [];
  let prev = -1;
  for (const p of sorted) {
    if (prev >= 0 && p - prev > 1) out.push("ellipsis");
    out.push(p);
    prev = p;
  }
  return out;
}

export default function Archive() {
  const { data, isLoading } = useQuery({
    queryKey: ["briefings"],
    queryFn: () => apiGet<BriefingSummary[]>("/briefings"),
  });

  // Remember the chosen page size between visits.
  const [perPage, setPerPage] = useState<number>(() => {
    const saved = typeof window !== "undefined" ? Number(window.localStorage.getItem(PER_PAGE_STORAGE_KEY)) : NaN;
    return PER_PAGE_OPTIONS.includes(saved) ? saved : 10;
  });
  useEffect(() => {
    window.localStorage.setItem(PER_PAGE_STORAGE_KEY, String(perPage));
  }, [perPage]);

  // Read order: the API returns newest-first; "oldest" simply reverses it. Remembered across visits.
  const [order, setOrder] = useState<"newest" | "oldest">(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(ORDER_STORAGE_KEY) : null;
    return saved === "oldest" ? "oldest" : "newest";
  });
  useEffect(() => {
    window.localStorage.setItem(ORDER_STORAGE_KEY, order);
  }, [order]);

  const [page, setPage] = useState(0);
  const total = data?.length ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / perPage));

  // Keep the page in range if the data shrinks or the page size grows.
  useEffect(() => {
    if (page > pageCount - 1) setPage(pageCount - 1);
  }, [page, pageCount]);

  const ordered = useMemo(
    () => (order === "newest" ? data ?? [] : [...(data ?? [])].reverse()),
    [data, order],
  );
  const pageItems = useMemo(
    () => ordered.slice(page * perPage, page * perPage + perPage),
    [ordered, page, perPage],
  );

  const from = total === 0 ? 0 : page * perPage + 1;
  const to = Math.min(page * perPage + perPage, total);

  return (
    <DeskLayout>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs tracking-[0.2em] text-accent uppercase">Archive</p>
          <h2 className="font-heading text-3xl font-bold tracking-tight">Past editions</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Every daily briefing, newest first. Each edition opens to its full statewide workup.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          {total > 1 && (
            <div className="flex items-center gap-1 rounded-md border border-border p-0.5" data-testid="archive-order">
              {([["newest", "Newest first"], ["oldest", "Oldest first"]] as const).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    setOrder(key);
                    setPage(0);
                  }}
                  data-testid={`order-${key}`}
                  className={`rounded px-2.5 py-1 text-xs transition-colors duration-150 ${
                    order === key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
          {total > PER_PAGE_OPTIONS[0] && (
            <label className="flex items-center gap-2 text-xs text-muted-foreground" data-testid="archive-per-page-label">
              Per page
              <select
                value={perPage}
                onChange={(e) => {
                  setPerPage(Number(e.target.value));
                  setPage(0);
                }}
                className="rounded-sm border border-border bg-card px-2 py-1 text-sm text-foreground"
                data-testid="archive-per-page"
              >
                {PER_PAGE_OPTIONS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
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
              className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-4"
              data-testid="archive-pagination"
            >
              <span className="text-xs text-muted-foreground" data-testid="archive-range">
                Showing {from}–{to} of {total}
              </span>
              <div className="flex flex-wrap items-center gap-1.5">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  data-testid="archive-prev"
                >
                  <ChevronLeft className="size-4" /> Previous
                </Button>
                {pageList(page, pageCount).map((item, i) =>
                  item === "ellipsis" ? (
                    <span key={`e-${i}`} className="px-1 text-xs text-muted-foreground" aria-hidden>
                      …
                    </span>
                  ) : (
                    <Button
                      key={item}
                      variant={item === page ? "default" : "outline"}
                      size="sm"
                      className="min-w-9 tabular-nums"
                      aria-current={item === page ? "page" : undefined}
                      onClick={() => setPage(item)}
                      data-testid={`archive-page-btn-${item + 1}`}
                    >
                      {item + 1}
                    </Button>
                  ),
                )}
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
