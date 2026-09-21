import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Lock } from "lucide-react";
import BriefingView from "@/components/BriefingView";
import { apiGet, ApiError } from "@/lib/api";
import type { Briefing } from "@/lib/types";

// Public, unauthenticated read view reached via a share link (/share/briefing/:date?t=token).
// The token is validated server-side by GET /api/public/briefings/:date.
export default function SharedBriefing() {
  const { date = "" } = useParams();
  const [params] = useSearchParams();
  const token = params.get("t") ?? "";

  const { data, isLoading, error } = useQuery({
    queryKey: ["public-briefing", date, token],
    queryFn: () =>
      apiGet<Briefing>(`/public/briefings/${date}?token=${encodeURIComponent(token)}`),
    retry: false,
  });

  return (
    <div className="min-h-screen bg-background" data-testid="shared-briefing">
      <header className="border-b border-border bg-card/70 backdrop-blur">
        <div className="mx-auto max-w-6xl px-5 py-4">
          <img
            src="/wvedtalk-logo.png"
            alt="WVEdTalk News Desk"
            className="h-14 w-auto md:h-16"
          />
          <p className="mt-2 text-xs tracking-[0.18em] text-muted-foreground uppercase">
            Shared briefing · West Virginia
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        {isLoading ? (
          <div className="flex items-center justify-center py-24 text-muted-foreground">
            <Loader2 className="size-6 animate-spin" />
          </div>
        ) : error ? (
          <div className="py-24 text-center" data-testid="shared-briefing-error">
            <Lock className="mx-auto mb-4 size-10 text-muted-foreground" />
            <h2 className="font-heading text-2xl font-bold">This link isn't valid</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {error instanceof ApiError && error.status === 404
                ? `No briefing was published for ${date}.`
                : "The share link is invalid or has expired. Ask the sender for a fresh link."}
            </p>
          </div>
        ) : data ? (
          <BriefingView briefing={data} isPublic />
        ) : null}
      </main>

      <footer className="border-t border-border px-5 py-6 text-center text-xs text-muted-foreground">
        Shared read-only view · Editorial judgment, scores and rankings are produced by the research
        model and presented unaltered.
      </footer>
    </div>
  );
}
