import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowUp,
  LoaderCircle,
  MessageSquare,
  Plus,
  Trash2,
} from "lucide-react";
import VoicePanel from "./VoicePanel";
import WorkspacePanel from "./WorkspacePanel";
import TextWithLinks from "./TextWithLinks";

type Message = { role: "user" | "assistant"; content: string };
type SavedConversation = { id: string; title: string; created_at: string };
type Reply = {
  text: string;
  provider: string;
  model: string;
  fallback: boolean;
  conversation_id: string | null;
  history_notice: string | null;
};

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    signal: AbortSignal.timeout(100000),
  });
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  return body as T;
}

export default function ChatPanel({
  defaultMode,
  onStateChange,
}: {
  defaultMode?: string;
  onStateChange?: (state: string) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [save, setSave] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedConversation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [provider, setProvider] = useState("No provider used yet");
  const [showHistory, setShowHistory] = useState(false);
  const [toolsEnabled, setToolsEnabled] = useState(false);
  const transcript = useRef<HTMLDivElement>(null);
  const inFlight = useRef(false);
  const modeChosen = useRef(false);

  useEffect(() => {
    if (defaultMode && !modeChosen.current) setMode(defaultMode);
  }, [defaultMode]);

  useEffect(() => {
    transcript.current?.scrollTo({ top: transcript.current.scrollHeight });
  }, [messages, busy]);
  useEffect(() => {
    onStateChange?.(busy ? "thinking" : "idle");
  }, [busy, onStateChange]);

  async function refreshHistory() {
    try {
      setSaved(await api<SavedConversation[]>("/conversations"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "History unavailable");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    await sendMessage(text.trim());
  }

  async function sendMessage(current: string): Promise<string | undefined> {
    if (!current || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    setText("");
    setMessages((previous) => [
      ...previous,
      { role: "user", content: current },
    ]);
    try {
      const result = await api<Reply>("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: current,
          history: messages.slice(-20),
          mode,
          save_history: save,
          conversation_id: conversationId,
          tools_enabled: toolsEnabled,
        }),
      });
      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: result.text },
      ]);
      setProvider(
        `${result.provider} / ${result.model}${result.fallback ? " · cloud unavailable, local fallback" : ""}`,
      );
      if (result.conversation_id) setConversationId(result.conversation_id);
      setNotice(result.history_notice ?? "");
      if (showHistory) void refreshHistory();
      return result.text;
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI request failed");
      setMessages((previous) => previous.slice(0, -1));
      setText(current);
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  }

  function newConversation() {
    setMessages([]);
    setConversationId(null);
    setError("");
    setNotice("");
    setProvider("No provider used yet");
  }

  async function openConversation(id: string) {
    try {
      setMessages(await api<Message[]>(`/conversations/${id}`));
      setConversationId(id);
      setError("");
      setNotice("Loaded saved conversation.");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load conversation",
      );
    }
  }

  async function removeConversation(id: string) {
    if (
      !window.confirm(
        "Permanently delete this saved conversation from JARVIS history?",
      )
    )
      return;
    try {
      await api(`/conversations/${id}`, { method: "DELETE" });
      if (conversationId === id) newConversation();
      await refreshHistory();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to delete conversation",
      );
    }
  }

  return (
    <section className="panel chat-panel">
      <VoicePanel
        onTranscript={sendMessage}
        mode={mode}
        onStateChange={onStateChange}
      />
      <div className="panel-top">
        <span>
          <MessageSquare size={14} /> CONVERSATION
        </span>
        <div className="chat-actions">
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setShowHistory(!showHistory);
              if (!showHistory) void refreshHistory();
            }}
          >
            History
          </button>
          <button type="button" disabled={busy} onClick={newConversation}>
            <Plus size={13} />
            New chat
          </button>
        </div>
      </div>
      <div className="chat-options">
        <label>
          Mode{" "}
          <select
            value={mode}
            disabled={busy}
            onChange={(e) => {
              modeChosen.current = true;
              setMode(e.target.value);
            }}
          >
            <option value="hybrid">Hybrid</option>
            <option value="online">Online · OpenAI</option>
            <option value="offline">Offline · Ollama</option>
          </select>
        </label>
        <label className="save-toggle">
          <input
            type="checkbox"
            checked={save}
            disabled={busy}
            onChange={(e) => {
              setSave(e.target.checked);
              if (!e.target.checked) setConversationId(null);
            }}
          />{" "}
          Save future turns locally
        </label>
      </div>
      <label className="agent-toggle">
        <input
          type="checkbox"
          checked={toolsEnabled}
          disabled={busy}
          onChange={(e) => setToolsEnabled(e.target.checked)}
        />{" "}
        Enable agent tools for this conversation · changes require approval
      </label>
      {showHistory && (
        <div className="history-list">
          <small>
            Saved locally · saving is off by default · avoid sharing secrets
          </small>
          {saved.length === 0 && <p>No saved conversations.</p>}
          {saved.map((item) => (
            <div key={item.id}>
              <button
                disabled={busy}
                onClick={() => void openConversation(item.id)}
              >
                {item.title}
              </button>
              <button
                disabled={busy}
                aria-label={`Delete ${item.title}`}
                onClick={() => void removeConversation(item.id)}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
      <div
        className="transcript"
        ref={transcript}
        aria-live="polite"
        aria-busy={busy}
      >
        {messages.length === 0 && (
          <div className="chat-empty">
            <h2>A conversation, on your terms.</h2>
            <p>
              Speak or type in English or Tamil. Local AI is configured with
              Ollama.
            </p>
            <small>
              Enable agent tools to request actions. Review proposed changes in
              Tasks.
            </small>
          </div>
        )}
        {messages.map((message, index) => (
          <article className={`message ${message.role}`} key={index}>
            <strong>{message.role === "user" ? "YOU" : "JARVIS"}</strong>
            <div>
              <TextWithLinks text={message.content} />
            </div>
          </article>
        ))}
        {busy && (
          <div className="thinking" role="status">
            <LoaderCircle className="spin" size={15} /> Waiting for{" "}
            {mode === "offline" ? "local model" : "AI provider"}…
          </div>
        )}
      </div>
      {error && (
        <div className="chat-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="chat-notice" role="status">
          {notice}
        </div>
      )}
      <form onSubmit={(e) => void submit(e)}>
        <label className="sr-only" htmlFor="chat-message">
          Message JARVIS
        </label>
        <textarea
          id="chat-message"
          value={text}
          maxLength={8000}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          placeholder="Message JARVIS…"
          rows={2}
        />
        <button aria-label="Send message" disabled={busy || !text.trim()}>
          <ArrowUp size={18} />
        </button>
      </form>
      <div className="provider-label">
        {provider} · {save ? "History opted in" : "Unsaved conversation"}
      </div>
      <WorkspacePanel
        onSettingsChange={(newMode) => {
          modeChosen.current = true;
          setMode(newMode);
        }}
      />
    </section>
  );
}
