import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Bot, Mail, Server, ShieldCheck, Send, Power } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { Integrations } from "@/lib/types";

const errText = (e: unknown) =>
  e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e);

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-card p-5">
      <div className="mb-3 flex items-center gap-2">
        {icon}
        <h4 className="font-heading text-base font-bold">{title}</h4>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs tracking-wide text-muted-foreground uppercase">{label}</span>
      {children}
    </label>
  );
}

// Admin-only Integrations manager: AI provider + key + model, Resend, SMTP fallback, Turnstile,
// and the runs/digests enable switches. Secrets are write-only — saved values show masked.
export default function IntegrationsPanel() {
  const { isAdmin } = useAuth();
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["integrations"],
    queryFn: () => apiGet<Integrations>("/settings/integrations"),
    enabled: isAdmin,
  });
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [testEmail, setTestEmail] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (data) {
      setForm({
        llm_provider: data.llm_provider,
        llm_model: data.llm_model,
        email_provider: data.email_provider,
        email_from: data.email_from,
        public_url: data.public_url,
        email_from_name: data.email_from_name,
        email_reply_to: data.email_reply_to,
        smtp_host: data.smtp_host,
        smtp_port: data.smtp_port,
        smtp_username: data.smtp_username,
        smtp_starttls: data.smtp_starttls,
        turnstile_site_key: data.turnstile_site_key,
      });
    }
  }, [data]);

  if (!isAdmin) return null;
  if (isLoading || !data)
    return (
      <div className="my-6 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Loading integrations…
      </div>
    );

  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  const save = async (patch: Record<string, unknown>) => {
    setBusy("save");
    try {
      await apiPost("/settings/integrations", patch);
      await refetch();
      toast.success("Integrations saved");
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy("");
    }
  };

  const testAi = async () => {
    setBusy("ai");
    try {
      const r = await apiPost<{ ok: boolean; error?: string; model?: string }>("/settings/integrations/test-ai");
      r.ok ? toast.success(`AI OK (${r.model})`) : toast.error(r.error || "AI test failed");
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy("");
    }
  };

  const testMail = async (provider?: string) => {
    if (!testEmail.trim()) return toast.error("Enter a test recipient address");
    setBusy("mail");
    try {
      const r = await apiPost<{ ok: boolean; error?: string }>("/settings/integrations/test-email", {
        email: testEmail.trim(),
        provider,
      });
      r.ok ? toast.success("Test email sent") : toast.error(r.error || "Email test failed");
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy("");
    }
  };

  const savedBadge = (set_: boolean, mask: string) =>
    set_ ? (
      <Badge variant="outline" className="border-emerald-500/50 text-emerald-600 dark:text-emerald-400">
        saved {mask}
      </Badge>
    ) : (
      <Badge variant="outline" className="text-muted-foreground">not set</Badge>
    );

  return (
    <section className="my-8 space-y-4" data-testid="integrations-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-heading text-xl font-bold">Integrations</h3>
        <div className="flex items-center gap-2">
          <Button
            variant={data.runs_enabled ? "default" : "outline"}
            size="sm"
            disabled={busy !== ""}
            onClick={() => save({ runs_enabled: !data.runs_enabled })}
            data-testid="toggle-runs"
          >
            <Power className="size-4" /> Scheduled runs {data.runs_enabled ? "on" : "off"}
          </Button>
          <Button
            variant={data.digests_enabled ? "default" : "outline"}
            size="sm"
            disabled={busy !== ""}
            onClick={() => save({ digests_enabled: !data.digests_enabled })}
            data-testid="toggle-digests"
          >
            <Power className="size-4" /> Email digests {data.digests_enabled ? "on" : "off"}
          </Button>
        </div>
      </div>

      <Section icon={<Bot className="size-4 text-primary" />} title="AI / Research model">
        <Field label="Provider">
          <select
            className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
            value={String(form.llm_provider ?? "gemini")}
            onChange={(e) => set("llm_provider", e.target.value)}
            data-testid="llm-provider-select"
          >
            <option value="gemini">Google Gemini (Search grounding)</option>
            <option value="openai">OpenAI (web search)</option>
          </select>
        </Field>
        <Field label="Model">
          <Input value={String(form.llm_model ?? "")} onChange={(e) => set("llm_model", e.target.value)} data-testid="llm-model-input" />
        </Field>
        <Field label={`Gemini API key ${""}`}>
          <div className="flex items-center gap-2">
            <Input type="password" placeholder="Paste to set / replace" onChange={(e) => set("gemini_api_key", e.target.value)} data-testid="gemini-key-input" />
            {savedBadge(data.gemini_api_key_set, data.gemini_api_key_mask)}
          </div>
        </Field>
        <Field label="OpenAI API key">
          <div className="flex items-center gap-2">
            <Input type="password" placeholder="Paste to set / replace" onChange={(e) => set("openai_api_key", e.target.value)} data-testid="openai-key-input" />
            {savedBadge(data.openai_api_key_set, data.openai_api_key_mask)}
          </div>
        </Field>
        <div className="flex gap-2">
          <Button size="sm" disabled={busy !== ""} onClick={() => save(form)} data-testid="save-ai">
            {busy === "save" ? <Loader2 className="size-4 animate-spin" /> : null} Save
          </Button>
          <Button size="sm" variant="outline" disabled={busy !== ""} onClick={testAi} data-testid="test-ai">
            {busy === "ai" ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />} Test AI connection
          </Button>
        </div>
      </Section>

      <Section icon={<Mail className="size-4 text-primary" />} title="Email — Resend (default)">
        <Field label="Public site URL (used for links & logo in emails — must be https)">
          <Input value={String(form.public_url ?? "")} onChange={(e) => set("public_url", e.target.value)} placeholder="https://your-tunnel-domain" data-testid="public-url-input" />
        </Field>
        <Field label="From address">
          <Input value={String(form.email_from ?? "")} onChange={(e) => set("email_from", e.target.value)} data-testid="email-from-input" />
        </Field>
        <Field label="From name">
          <Input value={String(form.email_from_name ?? "")} onChange={(e) => set("email_from_name", e.target.value)} data-testid="email-from-name-input" />
        </Field>
        <Field label="Reply-to (optional)">
          <Input value={String(form.email_reply_to ?? "")} onChange={(e) => set("email_reply_to", e.target.value)} />
        </Field>
        <Field label="Resend API key">
          <div className="flex items-center gap-2">
            <Input type="password" placeholder="Paste to set / replace" onChange={(e) => set("resend_api_key", e.target.value)} data-testid="resend-key-input" />
            {savedBadge(data.resend_api_key_set, data.resend_api_key_mask)}
          </div>
        </Field>
      </Section>

      <Section icon={<Server className="size-4 text-primary" />} title="Email — SMTP fallback">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Host">
            <Input value={String(form.smtp_host ?? "")} onChange={(e) => set("smtp_host", e.target.value)} data-testid="smtp-host-input" />
          </Field>
          <Field label="Port">
            <Input type="number" value={String(form.smtp_port ?? 587)} onChange={(e) => set("smtp_port", Number(e.target.value))} data-testid="smtp-port-input" />
          </Field>
          <Field label="Username">
            <Input value={String(form.smtp_username ?? "")} onChange={(e) => set("smtp_username", e.target.value)} />
          </Field>
          <Field label="Password">
            <Input type="password" placeholder={data.smtp_password_set ? "saved" : "Paste to set"} onChange={(e) => set("smtp_password", e.target.value)} />
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={!!form.smtp_starttls} onChange={(e) => set("smtp_starttls", e.target.checked)} /> Use STARTTLS
        </label>
      </Section>

      <Section icon={<ShieldCheck className="size-4 text-primary" />} title="Turnstile (public form CAPTCHA)">
        <Field label="Site key (public)">
          <Input value={String(form.turnstile_site_key ?? "")} onChange={(e) => set("turnstile_site_key", e.target.value)} />
        </Field>
        <Field label="Secret key">
          <div className="flex items-center gap-2">
            <Input type="password" placeholder="Paste to set / replace" onChange={(e) => set("turnstile_secret_key", e.target.value)} />
            {savedBadge(data.turnstile_secret_key_set, "")}
          </div>
        </Field>
      </Section>

      <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-secondary/30 p-4">
        <Button disabled={busy !== ""} onClick={() => save(form)} data-testid="save-integrations">
          {busy === "save" ? <Loader2 className="size-4 animate-spin" /> : null} Save all integration settings
        </Button>
        <div className="ml-auto flex items-center gap-2">
          <Input placeholder="you@example.com" value={testEmail} onChange={(e) => setTestEmail(e.target.value)} className="w-56" data-testid="test-email-input" />
          <Button size="sm" variant="outline" disabled={busy !== ""} onClick={() => testMail("resend")} data-testid="test-resend">
            {busy === "mail" ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />} Resend
          </Button>
          <Button size="sm" variant="outline" disabled={busy !== ""} onClick={() => testMail("smtp")} data-testid="test-smtp">
            <Send className="size-4" /> SMTP
          </Button>
        </div>
      </div>
    </section>
  );
}
