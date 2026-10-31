import { useEffect, useState } from "react";
import TextWithLinks from "./TextWithLinks";

type Task = {
  id: string;
  tool: string;
  arguments: Record<string, unknown>;
  status: string;
  result: string;
};
type RecordItem = { id: string; content: string; due_at: string | null };
type Tool = {
  name: string;
  description: string;
  approval: boolean;
  schema: {
    required?: string[];
    properties: Record<
      string,
      { type: string; enum?: string[]; title: string; format?: string }
    >;
  };
};
type Settings = {
  mode: string;
  ollama_model: string;
  openai_model: string;
  theme: string;
  memory_enabled: boolean;
  search_provider: string;
  openai_configured: boolean;
  brave_configured: boolean;
  workspace: string;
  applications: Record<string, string | null>;
};

async function call<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  });
  const value = await response.json();
  if (!response.ok || value.error)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : (value.error ?? "Request failed"),
    );
  return value as T;
}

export default function WorkspacePanel({
  onSettingsChange,
  section,
}: {
  onSettingsChange: (mode: string) => void;
  section?: string;
}) {
  const [tab, setTab] = useState("tasks");
  useEffect(() => {
    if (section) setTab(section);
  }, [section]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [tool, setTool] = useState("system_info");
  const [args, setArgs] = useState<Record<string, string>>({});
  const [settings, setSettings] = useState<Settings | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [openaiKey, setOpenaiKey] = useState("");
  const [braveKey, setBraveKey] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [content, setContent] = useState("");
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const [now, setNow] = useState(Date.now());
  const [dueReminders, setDueReminders] = useState<RecordItem[]>([]);
  const selected = tools.find((t) => t.name === tool);

  useEffect(() => {
    let active = true;
    void Promise.all([
      call<Settings>("/settings"),
      call<Tool[]>("/tools"),
      call<{ models: string[] }>("/models"),
    ])
      .then(([s, t, m]) => {
        if (active) {
          setSettings(s);
          setTools(t);
          setModels(m.models);
          document.documentElement.dataset.theme = s.theme;
        }
      })
      .catch((err) => {
        if (active) setError(String(err.message));
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const [t, r, reminders] = await Promise.all([
          call<Task[]>("/tasks"),
          ["memory", "note", "reminder", "todo", "schedule"].includes(tab)
            ? call<RecordItem[]>(`/records/${tab}`)
            : Promise.resolve([]),
          call<RecordItem[]>("/records/reminder"),
        ]);
        if (active) {
          setTasks(t);
          setRecords(r);
          setNow(Date.now());
          setDueReminders(
            reminders.filter(
              (item) => item.due_at && Date.parse(item.due_at) <= Date.now(),
            ),
          );
        }
      } catch (err) {
        if (active)
          setError(
            err instanceof Error ? err.message : "Workspace unavailable",
          );
      } finally {
        if (active) timer = setTimeout(() => void refresh(), 5000);
      }
    }
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [tab]);

  async function perform(action: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function decide(id: string, approve: boolean) {
    const result = await call<{ status: string; result?: unknown }>(
      `/tasks/${id}/decision`,
      "POST",
      { approve },
    );
    setNotice(`Task ${result.status}`);
    setTasks(await call<Task[]>("/tasks"));
    if (result.result) setResult(JSON.stringify(result.result, null, 2));
  }

  async function propose(name: string, arguments_: Record<string, unknown>) {
    const definition = tools.find((item) => item.name === name);
    const normalized = Object.fromEntries(
      Object.entries(arguments_)
        .filter(([, value]) => value !== "")
        .map(([key, value]) => {
          const type = definition?.schema.properties[key]?.type;
          if (type === "array" && typeof value === "string")
            return [
              key,
              value.trim().startsWith("[")
                ? JSON.parse(value)
                : value
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
            ];
          if (type === "integer" && typeof value === "string")
            return [key, Number(value)];
          return [key, value];
        }),
    );
    const result = await call("/tools", "POST", {
      name,
      arguments: normalized,
      mode: settings?.mode ?? "offline",
    });
    setResult(JSON.stringify(result, null, 2));
    setTasks(await call<Task[]>("/tasks"));
    setNotice("Request processed. Review any pending action in Tasks.");
  }

  async function saveSettings() {
    if (!settings) return;
    const {
      mode,
      ollama_model,
      openai_model,
      theme,
      memory_enabled,
      search_provider,
    } = settings;
    await call("/settings", "PUT", {
      mode,
      ollama_model,
      openai_model,
      theme,
      memory_enabled,
      search_provider,
    });
    if (openaiKey) {
      await call("/settings/keys/openai", "PUT", { key: openaiKey });
      setOpenaiKey("");
    }
    if (braveKey) {
      await call("/settings/keys/brave", "PUT", { key: braveKey });
      setBraveKey("");
    }
    setSettings(await call<Settings>("/settings"));
    document.documentElement.dataset.theme = theme;
    onSettingsChange(mode);
    setNotice("Settings saved. Keys use Windows Credential Manager.");
  }

  const pending = tasks.filter((t) => t.status === "pending").length;
  return (
    <section className="panel workspace-panel">
      <nav aria-label="Workspace sections">
        {[
          ["tasks", `Tasks${pending ? ` (${pending})` : ""}`],
          ["tools", "Actions"],
          ["memory", "Memories"],
          ["note", "Notes"],
          ["todo", "To-do"],
          ["schedule", "Schedule"],
          ["reminder", "Reminders"],
          ["settings", "Settings"],
        ].map(([id, label]) => (
          <button
            key={id}
            aria-pressed={tab === id}
            onClick={() => {
              setTab(id);
              setResult("");
              setError("");
              setNotice("");
            }}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="workspace-body">
        {dueReminders.length > 0 && (
          <div className="reminder-banner" role="alert">
            <strong>Reminder due</strong>
            {dueReminders.map((item) => (
              <p key={item.id}>{item.content}</p>
            ))}
            <button onClick={() => setTab("reminder")}>View reminders</button>
          </div>
        )}
        {tab === "tasks" && (
          <>
            <h2>Task activity</h2>

            {tasks.length === 0 && <p>No tasks yet.</p>}
            {tasks.map((task) => (
              <article className="task-card" key={task.id}>
                <div>
                  <strong>{task.tool.replaceAll("_", " ")}</strong>
                  <span>{task.status}</span>
                </div>
                <dl>
                  {Object.entries(task.arguments).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key.replaceAll("_", " ")}</dt>
                      <dd>{String(value)}</dd>
                    </div>
                  ))}
                </dl>
                {task.status === "pending" && (
                  <div className="task-buttons">
                    <button
                      disabled={busy}
                      onClick={() => void perform(() => decide(task.id, true))}
                    >
                      Approve and run
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => void perform(() => decide(task.id, false))}
                    >
                      Reject
                    </button>
                  </div>
                )}
                {task.result && <pre>{task.result}</pre>}
              </article>
            ))}
          </>
        )}
        {tab === "tools" && (
          <>
            <h2>Actions</h2>
            <p>
              Files stay in {settings?.workspace ?? "the JARVIS workspace"}.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void perform(() => propose(tool, args));
              }}
            >
              <label>
                Action
                <select
                  value={tool}
                  onChange={(e) => {
                    setTool(e.target.value);
                    setArgs({});
                  }}
                >
                  {tools.map((t) => (
                    <option key={t.name} value={t.name}>
                      {t.name.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </label>
              <p>{selected?.description}</p>
              {Object.entries(selected?.schema.properties ?? {}).map(
                ([key, schema]) => (
                  <label key={key}>
                    {schema.title}
                    {schema.enum ? (
                      <select
                        required={selected?.schema.required?.includes(key)}
                        value={args[key] ?? ""}
                        onChange={(e) =>
                          setArgs((previous) => ({
                            ...previous,
                            [key]: e.target.value,
                          }))
                        }
                      >
                        <option value="">Choose…</option>
                        {schema.enum.map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    ) : (
                      <textarea
                        required={selected?.schema.required?.includes(key)}
                        value={args[key] ?? ""}
                        maxLength={key === "content" ? 40000 : 2000}
                        onChange={(e) =>
                          setArgs((previous) => ({
                            ...previous,
                            [key]: e.target.value,
                          }))
                        }
                        placeholder={
                          schema.format === "date-time"
                            ? "2026-10-30T18:00:00+05:30"
                            : key === "path"
                              ? "Relative path, e.g. AI Projects"
                              : ""
                        }
                      />
                    )}
                  </label>
                ),
              )}
              <button disabled={busy}>
                {selected?.approval ? "Review action" : "Run read-only action"}
              </button>
            </form>
          </>
        )}
        {["memory", "note", "reminder", "todo", "schedule"].includes(tab) && (
          <>
            <h2>
              {tab === "memory"
                ? "Memories you choose to keep"
                : tab === "note"
                  ? "Your notes"
                  : "Your reminders"}
            </h2>
            <p>
              {tab === "memory"
                ? "Only approved memories are stored. Enable retrieval in Settings to use them in conversation. Never save passwords or API keys."
                : tab === "reminder"
                  ? "Due reminders appear here while JARVIS is open. Missed reminders remain visible after restart."
                  : "Notes are stored locally in SQLite."}
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void perform(async () => {
                  await propose(
                    tab === "memory"
                      ? "save_memory"
                      : tab === "note"
                        ? "save_note"
                        : tab === "todo"
                          ? "save_todo"
                          : tab === "schedule"
                            ? "schedule_event"
                            : "set_reminder",
                    {
                      content,
                      ...(["reminder", "schedule"].includes(tab)
                        ? { due_at: new Date(due).toISOString() }
                        : {}),
                    },
                  );
                  setContent("");
                });
              }}
            >
              <label>
                Content
                <textarea
                  required
                  value={content}
                  maxLength={2000}
                  onChange={(e) => setContent(e.target.value)}
                />
              </label>
              {["reminder", "schedule"].includes(tab) && (
                <label>
                  Remind me at
                  <input
                    type="datetime-local"
                    required
                    value={due}
                    onChange={(e) => setDue(e.target.value)}
                  />
                </label>
              )}
              <button disabled={busy}>Review new {tab}</button>
            </form>
            {records.map((record) => (
              <article key={record.id} className="record-card">
                <p>{record.content}</p>
                {record.due_at && (
                  <strong
                    className={Date.parse(record.due_at) <= now ? "due" : ""}
                  >
                    {Date.parse(record.due_at) <= now ? "DUE · " : ""}
                    {new Date(record.due_at).toLocaleString()}
                  </strong>
                )}
                <div>
                  <button
                    disabled={busy}
                    onClick={() => {
                      const value = window.prompt(
                        "Edit saved content",
                        record.content,
                      );
                      if (value?.trim())
                        void perform(async () => {
                          await call(`/records/${tab}/${record.id}`, "PUT", {
                            content: value,
                            due_at: record.due_at,
                          });
                          setRecords(
                            await call<RecordItem[]>(`/records/${tab}`),
                          );
                        });
                    }}
                  >
                    Edit
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => {
                      if (
                        window.confirm("Permanently delete this saved record?")
                      )
                        void perform(async () => {
                          await call(`/records/${record.id}`, "DELETE");
                          setRecords(
                            await call<RecordItem[]>(`/records/${tab}`),
                          );
                        });
                    }}
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </>
        )}
        {tab === "settings" && settings && (
          <>
            <h2>Make JARVIS yours.</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void perform(saveSettings);
              }}
            >
              <div className="settings-grid">
                <label>
                  Default AI mode
                  <select
                    value={settings.mode}
                    onChange={(e) =>
                      setSettings({ ...settings, mode: e.target.value })
                    }
                  >
                    <option value="offline">Offline · local only</option>
                    <option value="hybrid">Hybrid · cloud then local</option>
                    <option value="online">Online · OpenAI</option>
                  </select>
                </label>
                <label>
                  Ollama model
                  <input
                    list="local-models"
                    required
                    value={settings.ollama_model}
                    onChange={(e) =>
                      setSettings({ ...settings, ollama_model: e.target.value })
                    }
                  />
                  <datalist id="local-models">
                    {models.map((m) => (
                      <option key={m} value={m} />
                    ))}
                  </datalist>
                </label>
                <label>
                  OpenAI model
                  <input
                    required
                    value={settings.openai_model}
                    onChange={(e) =>
                      setSettings({ ...settings, openai_model: e.target.value })
                    }
                  />
                </label>
                <label>
                  Theme
                  <select
                    value={settings.theme}
                    onChange={(e) =>
                      setSettings({ ...settings, theme: e.target.value })
                    }
                  >
                    <option value="dark">Midnight</option>
                    <option value="dim">Deep navy</option>
                  </select>
                </label>
                <label>
                  OpenAI key ·{" "}
                  {settings.openai_configured ? "configured" : "not configured"}
                  <input
                    type="password"
                    autoComplete="off"
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    placeholder="Leave blank to keep current key"
                  />
                </label>
                <label>
                  Search provider
                  <select
                    value={settings.search_provider}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        search_provider: e.target.value,
                      })
                    }
                  >
                    <option value="duckduckgo">DuckDuckGo · no key</option>
                    <option value="brave">Brave · API key required</option>
                  </select>
                </label>
                <label>
                  Brave Search key ·{" "}
                  {settings.brave_configured ? "configured" : "not configured"}
                  <input
                    type="password"
                    autoComplete="off"
                    value={braveKey}
                    onChange={(e) => setBraveKey(e.target.value)}
                    placeholder="Required for live web search"
                  />
                </label>
              </div>
              <label className="save-toggle">
                <input
                  type="checkbox"
                  checked={settings.memory_enabled}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      memory_enabled: e.target.checked,
                    })
                  }
                />
                Retrieve relevant approved memories in chat
              </label>
              <p>
                API keys are stored by Windows Credential Manager. .env values
                remain a startup fallback. Offline mode prevents internet tools.
                Voice controls manage microphone, language, device, and volume
                for the current session.
              </p>
              <button disabled={busy}>Save settings</button>
            </form>
            <details>
              <summary>Installed approved applications</summary>
              {Object.entries(settings.applications).map(([name, path]) => (
                <p key={name}>
                  {name}: {path ?? "Not found"}
                </p>
              ))}
            </details>
          </>
        )}
        {busy && <p role="status">Processing…</p>}
        {notice && (
          <p role="status" className="chat-notice">
            {notice}
          </p>
        )}
        {error && (
          <p role="alert" className="chat-error">
            {error}
          </p>
        )}
        {result && (
          <pre className="action-result">
            <TextWithLinks text={result} />
          </pre>
        )}
      </div>
    </section>
  );
}
