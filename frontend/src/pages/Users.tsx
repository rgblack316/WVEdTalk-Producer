import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UserPlus, Trash2, ShieldCheck, KeyRound, Copy, Users as UsersIcon } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiGet, apiPost, apiDelete, ApiError } from "@/lib/api";
import type { AuthState, CreatedUser, User } from "@/lib/types";

function errMsg(e: unknown) {
  return e instanceof ApiError
    ? String((e.body as { detail?: string })?.detail ?? e.message)
    : String(e);
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? ""
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function Users() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("editor");
  const [cred, setCred] = useState<CreatedUser | null>(null);

  const { data: me } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiGet<AuthState>("/auth/me"),
    staleTime: 5 * 60 * 1000,
  });

  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => apiGet<User[]>("/users"),
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["users"] });

  const addUser = useMutation({
    mutationFn: () => apiPost<CreatedUser>("/users", { email: email.trim(), role }),
    onSuccess: (c) => {
      setCred(c);
      setEmail("");
      setRole("editor");
      refresh();
      toast.success(`User ${c.user.email} created`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const changeRole = useMutation({
    mutationFn: (v: { id: string; role: string }) =>
      apiPost<User>(`/users/${v.id}/role`, { role: v.role }),
    onSuccess: () => {
      refresh();
      toast.success("Role updated");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const resetPassword = useMutation({
    mutationFn: (id: string) => apiPost<CreatedUser>(`/users/${id}/reset-password`),
    onSuccess: (c) => {
      setCred(c);
      toast.success(`New temporary password generated for ${c.user.email}`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const removeUser = useMutation({
    mutationFn: (id: string) => apiDelete<{ ok: boolean }>(`/users/${id}`),
    onSuccess: () => {
      refresh();
      toast.success("User removed");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const copyTemp = () => {
    if (cred) {
      navigator.clipboard.writeText(cred.temp_password);
      toast.success("Temporary password copied");
    }
  };

  const list = users ?? [];

  return (
    <DeskLayout>
      <div className="mb-8">
        <p className="text-xs tracking-[0.2em] text-accent uppercase">Access Control</p>
        <h2 className="font-heading text-3xl font-bold tracking-tight">Users</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Manage who can sign in to the desk. Admins manage users; editors get every feature except
          user management; viewers can only read the work — no runs, no tagging, no changes.
        </p>
      </div>

      {/* One-time credential display after create / reset */}
      {cred && (
        <div
          className="mb-6 rounded-md border border-accent bg-accent/10 p-4"
          data-testid="temp-password-box"
        >
          <p className="text-sm font-semibold text-foreground">
            Temporary password for {cred.user.email}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Shown once — copy it now and share it with the user. They can change it in Settings after
            signing in.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <code
              className="rounded-sm border border-border bg-background px-3 py-1.5 font-mono text-sm"
              data-testid="temp-password-value"
            >
              {cred.temp_password}
            </code>
            <Button size="sm" variant="secondary" onClick={copyTemp} data-testid="copy-temp-password">
              <Copy className="size-4" /> Copy
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setCred(null)}>
              Dismiss
            </Button>
          </div>
        </div>
      )}

      <div className="grid gap-8 md:grid-cols-3">
        {/* Add user */}
        <section
          className="rounded-md border border-border bg-card p-5 md:col-span-1"
          data-testid="add-user-panel"
        >
          <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
            <UserPlus className="size-4 text-primary" /> Invite a user
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            A one-time temporary password is generated for you to share.
          </p>
          <form
            className="mt-4 space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (email.trim()) addUser.mutate();
            }}
          >
            <Input
              type="email"
              placeholder="person@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              data-testid="new-user-email-input"
            />
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger data-testid="new-user-role-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="editor">Editor</SelectItem>
                <SelectItem value="viewer">Viewer</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
              </SelectContent>
            </Select>
            <Button
              type="submit"
              className="w-full"
              disabled={addUser.isPending || !email.trim()}
              data-testid="create-user-button"
            >
              Create user
            </Button>
          </form>
        </section>

        {/* User list */}
        <section
          className="rounded-md border border-border bg-card p-5 md:col-span-2"
          data-testid="users-panel"
        >
          <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
            <UsersIcon className="size-4 text-primary" /> Accounts
          </h3>
          {isLoading ? (
            <div className="py-10 text-center text-sm text-muted-foreground">Loading users…</div>
          ) : (
            <ul className="mt-4 space-y-2" data-testid="users-list">
              {list.map((u) => {
                const isSelf = u.id === me?.user?.id;
                return (
                  <li
                    key={u.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-border bg-background px-3 py-2.5"
                    data-testid={`user-row-${u.email}`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium">{u.email}</span>
                        {u.role === "admin" && (
                          <Badge variant="secondary" className="gap-1">
                            <ShieldCheck className="size-3" /> Admin
                          </Badge>
                        )}
                        {isSelf && (
                          <span className="text-xs text-muted-foreground">(you)</span>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        Added {formatDate(u.created_at)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Select
                        value={u.role}
                        onValueChange={(r) => changeRole.mutate({ id: u.id, role: r })}
                      >
                        <SelectTrigger
                          className="h-8 w-28"
                          data-testid={`role-select-${u.email}`}
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="editor">Editor</SelectItem>
                          <SelectItem value="viewer">Viewer</SelectItem>
                          <SelectItem value="admin">Admin</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        title="Reset password"
                        aria-label={`Reset password for ${u.email}`}
                        onClick={() => resetPassword.mutate(u.id)}
                        data-testid={`reset-password-${u.email}`}
                      >
                        <KeyRound className="size-4" />
                      </Button>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        title="Delete user"
                        aria-label={`Delete ${u.email}`}
                        disabled={isSelf}
                        onClick={() => removeUser.mutate(u.id)}
                        data-testid={`delete-user-${u.email}`}
                      >
                        <Trash2 className="size-4 text-muted-foreground hover:text-destructive" />
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </DeskLayout>
  );
}
