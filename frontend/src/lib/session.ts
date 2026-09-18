import { apiPost } from "@/lib/api";
import type { QueryClient } from "@tanstack/react-query";

// Single shared-passcode session. The httpOnly cookie is set/cleared by the backend;
// the frontend only nudges the react-query cache so the gate re-evaluates.
export async function beginSession(qc: QueryClient) {
  await qc.invalidateQueries({ queryKey: ["auth", "me"] });
}

export async function endSession() {
  try {
    await apiPost("/auth/logout");
  } finally {
    // Hard redirect: a full page load re-evaluates AuthGate from scratch with the
    // cookie already cleared, and wipes all in-memory (react-query) state — no race.
    window.location.href = "/";
  }
}
