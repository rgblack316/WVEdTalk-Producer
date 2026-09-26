import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import DeskLayout from "@/components/DeskLayout";
import BriefingView from "@/components/BriefingView";
import { apiGet, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { Briefing } from "@/lib/types";

export default function BriefingPage() {
  const { canEdit } = useAuth();
  const { date = "" } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["briefing", date],
    queryFn: () => apiGet<Briefing>(`/briefings/${date}`),
    retry: false,
  });

  return (
    <DeskLayout>
      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading briefing…</div>
      ) : data ? (
        <BriefingView briefing={data} canFlag={canEdit} />
      ) : (
        <div className="py-16 text-center" data-testid="briefing-not-found">
          <h2 className="font-heading text-2xl font-bold">Briefing unavailable</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {error instanceof ApiError && error.status === 404
              ? `No edition was published for ${date}.`
              : "This edition could not be loaded in the current environment."}
          </p>
        </div>
      )}
    </DeskLayout>
  );
}
