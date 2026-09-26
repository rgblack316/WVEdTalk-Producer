import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Newspaper } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import BriefingView from "@/components/BriefingView";
import { buttonVariants } from "@/components/ui/button";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { Briefing } from "@/lib/types";

export default function Home() {
  const { canEdit } = useAuth();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["briefing", "latest"],
    queryFn: () => apiGet<Briefing | null>("/briefings/latest"),
    refetchInterval: 60000,
  });

  return (
    <DeskLayout>
      {isLoading ? (
        <div className="py-20 text-center text-muted-foreground" data-testid="home-loading">
          Loading the desk…
        </div>
      ) : data ? (
        <BriefingView briefing={data} canFlag={canEdit} />
      ) : (
        <div className="mx-auto max-w-lg py-16 text-center" data-testid="home-empty">
          <Newspaper className="mx-auto mb-4 size-10 text-muted-foreground" />
          <h2 className="font-heading text-2xl font-bold">No briefing yet</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {isError
              ? "The desk is offline in this preview. Once the backend is live, the daily briefing appears here — or start one now."
              : "The daily edition runs automatically on the schedule set in Settings. Start the first research run now to see today's briefing across all of West Virginia."}
          </p>
          <Link to="/archive" className={buttonVariants({ variant: "default" }) + " mt-6"} data-testid="home-empty-cta">
            View archive
          </Link>
        </div>
      )}
    </DeskLayout>
  );
}
