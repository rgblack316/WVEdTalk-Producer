import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { AuthState } from "@/lib/types";

// Shared read of the current session/role. Reuses the ["auth","me"] cache so every
// component sees the same identity without an extra request.
export function useAuth() {
  const { data } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiGet<AuthState>("/auth/me"),
    staleTime: 5 * 60 * 1000,
  });
  const role = data?.user?.role ?? "";
  return {
    user: data?.user ?? null,
    role,
    isAdmin: role === "admin",
    canEdit: role === "admin" || role === "editor", // viewers are read-only
  };
}
