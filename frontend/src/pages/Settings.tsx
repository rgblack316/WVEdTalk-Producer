import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Mail, Eye, Trash2, Send, Gauge, ShieldCheck, Timer, KeyRound, Users, Link2, Code2, Copy, CalendarClock, History } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { apiGet, apiPost, apiDelete, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { AuthState, DeskConfig, RunLogEntry, Subscriber } from "@/lib/types";

const DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const pad = (n: number) => String(n).padStart(2, "0");
const TZ_OPTIONS = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Phoenix",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "America/Puerto_Rico",
  "UTC",
  "Europe/London",
  "Europe/Paris",
  "Asia/Kolkata",
  "Asia/Tokyo",
  "Australia/Sydney",
];

function errMsg(e: unknown) {
  return e instanceof ApiError
    ? String((e.body as { detail?: string })?.detail ?? e.message)
    : String(e);
}

export default function Settings() {
  const qc = useQueryClient();
  const { canEdit } = useAuth();
  const [email, setEmail] = useState("");
  const [term, setTerm] = useState("");
  const [current, setCurrent] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirm, setConfirm] = useState("");
  const [dailyTime, setDailyTime] = useState("22:00");
  const [weeklyDow, setWeeklyDow] = useState(4);
  const [weeklyTime, setWeeklyTime] = useState("16:00");
  const [tz, setTz] = useState("America/New_York");

  const { data, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<DeskConfig>("/settings"),
  });

  const { data: auth } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiGet<AuthState>("/auth/me"),
    staleTime: 5 * 60 * 1000,
  });
  const isAdmin = auth?.user?.role === "admin";

  const { data: runLog } = useQuery({
    queryKey: ["run-log"],
    queryFn: () => apiGet<RunLogEntry[]>("/run-log"),
    refetchInterval: 60000,
  });

  useEffect(() => {
    if (data) {
      setDailyTime(`${pad(data.daily_hour)}:${pad(data.daily_minute)}`);
      setWeeklyDow(data.weekly_dow);
      setWeeklyTime(`${pad(data.weekly_hour)}:${pad(data.weekly_minute)}`);
      setTz(data.timezone);
    }
  }, [data]);

  const { data: subscribers } = useQuery({
    queryKey: ["subscribers"],
    queryFn: () => apiGet<Subscriber[]>("/subscribers"),
    refetchInterval: 30000,
    refetchOnWindowFocus: true,
  });
  const activeSubscribers = subscribers?.filter((s) => s.active).length ?? 0;

  const removeSubscriber = useMutation({
    mutationFn: (e: string) => apiDelete<{ ok: boolean }>(`/subscribers/${encodeURIComponent(e)}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscribers"] });
      toast.success("Subscriber removed");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const copySignupLink = () => {
    navigator.clipboard.writeText(`${window.location.origin}/subscribe`);
    toast.success("Public signup link copied");
  };

  const embedOrigin = typeof window !== "undefined" ? window.location.origin : "";
  const embedCode = `<!-- WVEdTalk News Desk signup -->
<div style="max-width:420px;font-family:Arial,Helvetica,sans-serif">
  <form onsubmit="var e=this.email.value;var s=this.querySelector('.wvedtalk-msg');fetch('${embedOrigin}/api/public/embed-subscribe',{method:'POST',mode:'no-cors',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'email='+encodeURIComponent(e)});s.textContent='Thanks! You are subscribed to the WVEdTalk daily briefing.';this.reset();return false;">
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <input name="email" type="email" required placeholder="you@example.com" style="flex:1;min-width:200px;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:14px" />
      <button type="submit" style="background:#16305e;color:#fff;border:0;border-radius:6px;padding:10px 18px;font-size:14px;font-weight:bold;cursor:pointer">Subscribe</button>
    </div>
    <p class="wvedtalk-msg" style="margin:8px 0 0;font-size:13px;color:#16305e"></p>
  </form>
  <p style="margin:6px 0 0;font-size:11px;color:#8a8a8a">Powered by WVEdTalk News Desk</p>
</div>`;

  const copyEmbed = () => {
    navigator.clipboard.writeText(embedCode);
    toast.success("Embed code copied");
  };

  const submitEmbedCode = `<!-- WVEdTalk News Desk story submission -->
<div style="max-width:420px;font-family:Arial,Helvetica,sans-serif">
  <form onsubmit="var f=this;var s=f.querySelector('.wvedtalk-msg');fetch('${embedOrigin}/api/public/embed-submit-story',{method:'POST',mode:'no-cors',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'url='+encodeURIComponent(f.url.value)+'&name='+encodeURIComponent(f.pname.value)+'&email='+encodeURIComponent(f.email.value)+'&website='+encodeURIComponent(f.website.value)});s.textContent='Thanks! Your story has been submitted for the desk to consider.';f.reset();return false;">
    <input name="url" type="url" required placeholder="Link to the story" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:14px;margin-bottom:8px" />
    <input name="pname" type="text" required placeholder="Your name" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:14px;margin-bottom:8px" />
    <input name="email" type="email" required placeholder="you@example.com" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:14px;margin-bottom:8px" />
    <input name="website" type="text" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute;left:-9999px;height:0;width:0;opacity:0" />
    <button type="submit" style="background:#16305e;color:#fff;border:0;border-radius:6px;padding:10px 18px;font-size:14px;font-weight:bold;cursor:pointer">Submit story</button>
    <p class="wvedtalk-msg" style="margin:8px 0 0;font-size:13px;color:#16305e"></p>
  </form>
  <p style="margin:6px 0 0;font-size:11px;color:#8a8a8a">Powered by WVEdTalk News Desk</p>
</div>`;

  const copySubmitEmbed = () => {
    navigator.clipboard.writeText(submitEmbedCode);
    toast.success("Submit-form embed code copied");
  };

  const invalidate = (cfg: DeskConfig) => qc.setQueryData(["config"], cfg);

  const addRecipient = useMutation({
    mutationFn: (e: string) => apiPost<DeskConfig>("/settings/recipients", { email: e }),
    onSuccess: (cfg) => {
      invalidate(cfg);
      setEmail("");
      toast.success("Recipient added");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const removeRecipient = useMutation({
    mutationFn: (e: string) => apiDelete<DeskConfig>(`/settings/recipients/${encodeURIComponent(e)}`),
    onSuccess: (cfg) => invalidate(cfg),
    onError: (e) => toast.error(errMsg(e)),
  });

  const addTerm = useMutation({
    mutationFn: (t: string) => apiPost<DeskConfig>("/settings/watch-terms", { term: t }),
    onSuccess: (cfg) => {
      invalidate(cfg);
      setTerm("");
      toast.success("Watch term added");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const removeTerm = useMutation({
    mutationFn: (t: string) => apiDelete<DeskConfig>(`/settings/watch-terms/${encodeURIComponent(t)}`),
    onSuccess: (cfg) => invalidate(cfg),
    onError: (e) => toast.error(errMsg(e)),
  });

  const sendNow = useMutation({
    mutationFn: () => apiPost<{ sent: number }>("/settings/send-digest"),
    onSuccess: (r) => toast.success(`Digest sent to ${r.sent} recipient${r.sent === 1 ? "" : "s"}`),
    onError: (e) => toast.error(errMsg(e)),
  });

  const setLength = useMutation({
    mutationFn: (value: string) => apiPost<DeskConfig>("/settings/script-length", { value }),
    onSuccess: (cfg) => {
      invalidate(cfg);
      toast.success("Script length preference saved");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const setAutoLock = useMutation({
    mutationFn: (minutes: number) => apiPost<DeskConfig>("/settings/auto-lock", { minutes }),
    onSuccess: (cfg) => {
      invalidate(cfg);
      toast.success("Auto-lock preference saved");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const saveSchedule = useMutation({
    mutationFn: () => {
      const [dh, dm] = dailyTime.split(":").map(Number);
      const [wh, wm] = weeklyTime.split(":").map(Number);
      return apiPost<DeskConfig>("/settings/schedule", {
        timezone: tz,
        daily_hour: dh,
        daily_minute: dm,
        weekly_dow: weeklyDow,
        weekly_hour: wh,
        weekly_minute: wm,
      });
    },
    onSuccess: (cfg) => {
      invalidate(cfg);
      qc.invalidateQueries({ queryKey: ["schedule-next"] });
      toast.success("Schedule updated");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const changePassword = useMutation({
    mutationFn: () =>
      apiPost<{ ok: boolean }>("/settings/password", {
        current_password: current,
        new_password: newPass,
      }),
    onSuccess: () => {
      setCurrent("");
      setNewPass("");
      setConfirm("");
      toast.success("Password changed.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const recipients = data?.recipients ?? [];
  const terms = data?.watch_terms ?? [];
  const length = data?.script_length ?? "standard";
  const autoLock = data?.auto_lock_minutes ?? 0;

  const LENGTHS: { id: string; label: string; hint: string }[] = [
    { id: "concise", label: "Concise", hint: "~10–13 min" },
    { id: "standard", label: "Standard", hint: "~15–20 min" },
    { id: "full", label: "Full", hint: "~20–26 min" },
  ];
  const LOCK_OPTIONS: { minutes: number; label: string }[] = [
    { minutes: 0, label: "Off" },
    { minutes: 5, label: "5 min" },
    { minutes: 15, label: "15 min" },
    { minutes: 30, label: "30 min" },
    { minutes: 60, label: "60 min" },
  ];
  const passwordValid = current.trim() && newPass.trim().length >= 8 && newPass === confirm;

  return (
    <DeskLayout>
      <div className="mb-8">
        <p className="text-xs tracking-[0.2em] text-accent uppercase">Settings</p>
        <h2 className="font-heading text-3xl font-bold tracking-tight">Desk settings</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Manage who receives the morning email digest and which topics or counties the desk should
          flag on every edition.
        </p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading settings…</div>
      ) : (
        <div className="grid gap-8 md:grid-cols-2">
          {/* Account: my password + auto-lock */}
          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="security-panel"
          >
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <ShieldCheck className="size-4 text-primary" /> My account
            </h3>
            {auth?.user && (
              <p className="mt-1 text-xs text-muted-foreground" data-testid="account-identity">
                Signed in as <span className="font-medium text-foreground">{auth.user.email}</span> ·{" "}
                <Badge variant="secondary">{auth.user.role}</Badge>
              </p>
            )}
            <div className="mt-4 grid gap-6 md:grid-cols-2">
              {/* Change password */}
              <div>
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <KeyRound className="size-4 text-primary" /> Change password
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Update your own password. You'll stay signed in on this browser.
                </p>
                <form
                  className="mt-3 space-y-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (passwordValid) changePassword.mutate();
                  }}
                >
                  <Input
                    type="password"
                    autoComplete="current-password"
                    placeholder="Current password"
                    value={current}
                    onChange={(e) => setCurrent(e.target.value)}
                    data-testid="current-password-input"
                  />
                  <Input
                    type="password"
                    autoComplete="new-password"
                    placeholder="New password (min 8 characters)"
                    value={newPass}
                    onChange={(e) => setNewPass(e.target.value)}
                    data-testid="new-password-input"
                  />
                  <Input
                    type="password"
                    autoComplete="new-password"
                    placeholder="Confirm new password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    data-testid="confirm-password-input"
                  />
                  {confirm && newPass !== confirm && (
                    <p className="text-xs text-destructive">Passwords don't match.</p>
                  )}
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!passwordValid || changePassword.isPending}
                    data-testid="change-password-button"
                  >
                    Update password
                  </Button>
                </form>
              </div>

              {/* Auto-lock (shared config — editors only) */}
              {canEdit && (
              <div>
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <Timer className="size-4 text-accent" /> Auto-lock on inactivity
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Sign this browser out automatically after a period with no activity — useful on
                  shared machines.
                </p>
                <div className="mt-3 flex flex-wrap gap-2" data-testid="auto-lock-options">
                  {LOCK_OPTIONS.map((o) => (
                    <button
                      key={o.minutes}
                      onClick={() => setAutoLock.mutate(o.minutes)}
                      disabled={setAutoLock.isPending}
                      data-testid={`auto-lock-${o.minutes}`}
                      className={`rounded-sm border px-3 py-1.5 text-sm transition-colors duration-150 ${
                        autoLock === o.minutes
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background hover:border-primary/50"
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
              </div>
              )}
            </div>
          </section>

          {/* Weekly script length */}
          {canEdit && (
          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="script-length-panel"
          >
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Gauge className="size-4 text-primary" /> WVEdTalk script length
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Nudge the weekly episode toward a shorter or fuller target. It's only a target — a quiet
              week still yields a shorter episode, and no important story is cut to hit a length.
            </p>
            <div className="mt-4 flex flex-wrap gap-2" data-testid="script-length-options">
              {LENGTHS.map((l) => (
                <button
                  key={l.id}
                  onClick={() => setLength.mutate(l.id)}
                  disabled={setLength.isPending}
                  data-testid={`script-length-${l.id}`}
                  className={`rounded-sm border px-4 py-2 text-left transition-colors duration-150 ${
                    length === l.id
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background hover:border-primary/50"
                  }`}
                >
                  <span className="block text-sm font-semibold">{l.label}</span>
                  <span className={`block text-xs ${length === l.id ? "text-primary-foreground/80" : "text-muted-foreground"}`}>
                    {l.hint}
                  </span>
                </button>
              ))}
            </div>
          </section>
          )}

          {/* Automatic run schedule (admin only) */}
          {isAdmin && (
          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="schedule-panel"
          >
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <CalendarClock className="size-4 text-primary" /> Automatic run schedule
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              When the desk runs on its own, in the home timezone you choose below. The header shows
              the next run converted to your browser's local time.
            </p>
            <div className="mt-4 grid gap-6 md:grid-cols-2">
              <div>
                <label htmlFor="daily-time" className="text-sm font-semibold">
                  Daily briefing
                </label>
                <p className="mt-1 text-xs text-muted-foreground">Runs every day at this time.</p>
                <input
                  id="daily-time"
                  type="time"
                  value={dailyTime}
                  onChange={(e) => setDailyTime(e.target.value)}
                  className="mt-2 rounded-sm border border-border bg-background px-3 py-2 text-sm"
                  data-testid="daily-time-input"
                />
              </div>
              <div>
                <span className="text-sm font-semibold">Weekly script</span>
                <p className="mt-1 text-xs text-muted-foreground">
                  Runs once a week on this day and time.
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <select
                    value={weeklyDow}
                    onChange={(e) => setWeeklyDow(Number(e.target.value))}
                    className="rounded-sm border border-border bg-background px-3 py-2 text-sm"
                    data-testid="weekly-dow-select"
                    aria-label="Weekly run day"
                  >
                    {DOW.map((d, i) => (
                      <option key={d} value={i}>
                        {d}
                      </option>
                    ))}
                  </select>
                  <input
                    type="time"
                    value={weeklyTime}
                    onChange={(e) => setWeeklyTime(e.target.value)}
                    className="rounded-sm border border-border bg-background px-3 py-2 text-sm"
                    data-testid="weekly-time-input"
                    aria-label="Weekly run time"
                  />
                </div>
              </div>
            </div>
            <div className="mt-5">
              <label htmlFor="tz-select" className="text-sm font-semibold">
                Home timezone
              </label>
              <p className="mt-1 text-xs text-muted-foreground">
                All run times above are interpreted in this timezone (DST handled automatically). The
                header shows the next run converted to your browser's local time.
              </p>
              <select
                id="tz-select"
                value={tz}
                onChange={(e) => setTz(e.target.value)}
                className="mt-2 rounded-sm border border-border bg-background px-3 py-2 text-sm"
                data-testid="timezone-select"
              >
                {[...new Set([tz, ...TZ_OPTIONS])].map((z) => (
                  <option key={z} value={z}>
                    {z.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
            <Button
              size="sm"
              className="mt-4"
              disabled={saveSchedule.isPending}
              onClick={() => saveSchedule.mutate()}
              data-testid="save-schedule-button"
            >
              Save schedule
            </Button>
          </section>
          )}

          {/* Recent automatic runs — visible to all signed-in users */}
          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="run-history-panel"
          >
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <History className="size-4 text-primary" /> Recent runs
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              The last briefings and weekly scripts the desk produced — confirm the schedule is
              firing. Times are shown in your local timezone.
            </p>
            <ul className="mt-4 space-y-2" data-testid="run-log-list">
              {runLog && runLog.length > 0 ? (
                runLog.map((r) => (
                  <li
                    key={r.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-background px-3 py-2 text-sm"
                    data-testid={`run-log-${r.id}`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={r.status === "complete" ? "secondary" : "destructive"}>
                        {r.status}
                      </Badge>
                      <span className="font-medium">
                        {r.kind === "daily" ? "Daily briefing" : "Weekly script"}
                      </span>
                      <span className="text-muted-foreground">{r.label}</span>
                      <Badge variant="outline">{r.trigger}</Badge>
                    </div>
                    <span
                      className="text-xs text-muted-foreground"
                      data-testid={`run-log-time-${r.id}`}
                    >
                      {new Date(r.finished_at).toLocaleString()}
                    </span>
                  </li>
                ))
              ) : (
                <li className="text-sm text-muted-foreground">
                  No runs recorded yet. They'll appear here after the next scheduled or manual run.
                </li>
              )}
            </ul>
          </section>

          {canEdit && (
          <section className="rounded-md border border-border bg-card p-5" data-testid="recipients-panel">
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Mail className="size-4 text-primary" /> Email digest
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              The full briefing is emailed to everyone below the moment each 10:00 PM run finishes.
            </p>
            <form
              className="mt-4 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (email.trim()) addRecipient.mutate(email.trim());
              }}
            >
              <Input
                type="email"
                placeholder="host@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="recipient-input"
              />
              <Button type="submit" disabled={addRecipient.isPending} data-testid="add-recipient-button">
                Add
              </Button>
            </form>

            <ul className="mt-4 space-y-2" data-testid="recipients-list">
              {recipients.length === 0 && (
                <li className="text-sm text-muted-foreground">No recipients yet.</li>
              )}
              {recipients.map((r) => (
                <li
                  key={r}
                  className="flex items-center justify-between rounded-sm border border-border bg-background px-3 py-2 text-sm"
                  data-testid={`recipient-${r}`}
                >
                  <span>{r}</span>
                  <button
                    onClick={() => removeRecipient.mutate(r)}
                    className="text-muted-foreground transition-colors hover:text-destructive"
                    data-testid={`remove-recipient-${r}`}
                    aria-label={`Remove ${r}`}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </li>
              ))}
            </ul>

            <Button
              variant="secondary"
              size="sm"
              className="mt-4"
              disabled={sendNow.isPending || recipients.length === 0}
              onClick={() => sendNow.mutate()}
              data-testid="send-digest-now-button"
            >
              <Send className="size-4" /> Send latest briefing now
            </Button>
          </section>
          )}

          {/* Watchlist terms */}
          {canEdit && (
          <section className="rounded-md border border-border bg-card p-5" data-testid="watchlist-panel">
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Eye className="size-4 text-accent" /> Watchlist
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Topics, counties, or names to track. Any edition whose stories mention a term shows a
              highlighted alert at the top.
            </p>
            <form
              className="mt-4 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (term.trim()) addTerm.mutate(term.trim());
              }}
            >
              <Input
                placeholder="e.g. consolidation, McDowell County, AI"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                data-testid="watch-term-input"
              />
              <Button type="submit" disabled={addTerm.isPending} data-testid="add-watch-term-button">
                Add
              </Button>
            </form>

            <div className="mt-4 flex flex-wrap gap-2" data-testid="watch-terms-list">
              {terms.length === 0 && (
                <span className="text-sm text-muted-foreground">No watch terms yet.</span>
              )}
              {terms.map((t) => (
                <Badge
                  key={t}
                  variant="outline"
                  className="gap-1.5 py-1"
                  data-testid={`watch-term-${t}`}
                >
                  {t}
                  <button
                    onClick={() => removeTerm.mutate(t)}
                    className="text-muted-foreground transition-colors hover:text-destructive"
                    aria-label={`Remove ${t}`}
                  >
                    <Trash2 className="size-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </section>
          )}

          {/* Public subscribers (self sign-up) — visible to all, managed by editors */}
          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="subscribers-panel"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
                <Users className="size-4 text-primary" /> Public subscribers
                <Badge variant="secondary" data-testid="active-subscriber-count">
                  {activeSubscribers} active
                </Badge>
              </h3>
              {canEdit && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copySignupLink}
                  data-testid="copy-signup-link-button"
                >
                  <Link2 className="size-4" /> Copy signup link
                </Button>
              )}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              People who sign up on the public page also receive the daily briefing — each email is
              sent individually so addresses stay private, with a one-click unsubscribe link. The
              weekly WVEdTalk script stays internal; subscribers never receive it.
            </p>
            <ul className="mt-4 space-y-2" data-testid="subscribers-list">
              {subscribers && subscribers.length > 0 ? (
                subscribers.map((s) => (
                  <li
                    key={s.email}
                    className="flex items-center justify-between rounded-sm border border-border bg-background px-3 py-2 text-sm"
                    data-testid={`subscriber-${s.email}`}
                  >
                    <span className={s.active ? "" : "text-muted-foreground line-through"}>
                      {s.email}
                    </span>
                    <div className="flex items-center gap-2">
                      {!s.active && <Badge variant="outline">unsubscribed</Badge>}
                      {canEdit && (
                        <button
                          onClick={() => removeSubscriber.mutate(s.email)}
                          className="text-muted-foreground transition-colors hover:text-destructive"
                          data-testid={`remove-subscriber-${s.email}`}
                          aria-label={`Remove ${s.email}`}
                        >
                          <Trash2 className="size-4" />
                        </button>
                      )}
                    </div>
                  </li>
                ))
              ) : (
                <li className="text-sm text-muted-foreground">
                  No public subscribers yet. Share the signup link to get started.
                </li>
              )}
            </ul>
            {canEdit && (
              <div className="mt-6 border-t border-border pt-4" data-testid="embed-panel">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="flex items-center gap-1.5 text-sm font-semibold">
                    <Code2 className="size-4 text-primary" /> Embed the signup form on another site
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={copyEmbed}
                    data-testid="copy-embed-code-button"
                  >
                    <Copy className="size-4" /> Copy embed code
                  </Button>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Paste this HTML into any web page. Visitors who subscribe are added to your
                  subscribers list and receive the daily briefing — no account needed.
                </p>
                <textarea
                  readOnly
                  value={embedCode}
                  onFocus={(e) => e.currentTarget.select()}
                  className="mt-3 h-40 w-full rounded-sm border border-border bg-background p-3 font-mono text-xs"
                  data-testid="embed-code-textarea"
                />
                <p className="mt-3 text-xs tracking-[0.14em] text-accent uppercase">Live preview</p>
                <div
                  className="mt-2 rounded-sm border border-dashed border-border p-4"
                  data-testid="embed-preview"
                  dangerouslySetInnerHTML={{ __html: embedCode }}
                />
              </div>
            )}
            {canEdit && (
              <div className="mt-6 border-t border-border pt-4" data-testid="submit-embed-panel">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="flex items-center gap-1.5 text-sm font-semibold">
                    <Code2 className="size-4 text-primary" /> Embed the "Submit a story" form on another site
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={copySubmitEmbed}
                    data-testid="copy-submit-embed-button"
                  >
                    <Copy className="size-4" /> Copy embed code
                  </Button>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Paste this HTML into any web page. Readers who submit a story link are added to the
                  Submissions dashboard and subscribed to the daily briefing — no account needed. A hidden
                  honeypot blocks basic bots.
                </p>
                <textarea
                  readOnly
                  value={submitEmbedCode}
                  onFocus={(e) => e.currentTarget.select()}
                  className="mt-3 h-40 w-full rounded-sm border border-border bg-background p-3 font-mono text-xs"
                  data-testid="submit-embed-code-textarea"
                />
                <p className="mt-3 text-xs tracking-[0.14em] text-accent uppercase">Live preview</p>
                <div
                  className="mt-2 rounded-sm border border-dashed border-border p-4"
                  data-testid="submit-embed-preview"
                  dangerouslySetInnerHTML={{ __html: submitEmbedCode }}
                />
              </div>
            )}
          </section>
        </div>
      )}
    </DeskLayout>
  );
}
