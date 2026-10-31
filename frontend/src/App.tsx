import { readApiJson } from "./apiResponse";
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  AudioLines,
  Bell,
  BrainCircuit,
  ChevronRight,
  Command,
  Cpu,
  FolderOpen,
  LayoutGrid,
  ListChecks,
  Mic,
  RefreshCw,
  Settings2,
  Square,
  Wifi,
  Zap,
} from "lucide-react";
import ChatPanel from "./ChatPanel";

type Health = {
  deployment?: string;
  status: string;
  name: string;
  version: string;
  phase: number;
  mode: string;
  openai_configured: boolean;
  capabilities: Record<string, boolean>;
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [assistantState, setAssistantState] = useState("idle");
  const [workspaceSection, setWorkspaceSection] = useState<string | null>(null);
  const [system, setSystem] = useState<{
    cpu_percent: number;
    ram_percent: number;
    ram_available_gb: number;
  } | null>(null);
  const reducedMotion = useReducedMotion();

  async function checkConnection(signal?: AbortSignal) {
    setLoading(true);
    try {
      const response = await fetch("/api/health", {
        signal: signal ?? AbortSignal.timeout(5000),
      });
      const result = await readApiJson(response);
      if (!response.ok) throw new Error(`Backend returned ${response.status}`);
      setHealth(result as Health);
      setError("");
    } catch (err) {
      if (signal?.aborted) return;
      setHealth(null);
      setError(err instanceof Error ? err.message : "Unable to reach backend");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void checkConnection(controller.signal);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const response = await fetch("/api/system", {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Telemetry unavailable");
        const value = await readApiJson(response);
        if (!stopped) setSystem(value);
      } catch {
        if (!stopped) setSystem(null);
      } finally {
        if (!stopped) timer = setTimeout(() => void poll(), 5000);
      }
    }
    void poll();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, []);

  const voiceActive = ["listening", "armed", "speaking", "connecting"].includes(
    assistantState,
  );
  const stateLabel =
    assistantState === "idle"
      ? "Standing by"
      : assistantState === "armed"
        ? "Wake listening"
        : assistantState;
  const navigation = [
    { id: null, name: "Assistant", icon: AudioLines },
    { id: "tasks", name: "Tasks", icon: ListChecks },
    { id: "tools", name: "Actions", icon: LayoutGrid },
    { id: "memory", name: "Memories", icon: BrainCircuit },
    { id: "note", name: "Notes", icon: FolderOpen },
    { id: "reminder", name: "Reminders", icon: Bell },
  ];
  return (
    <div className="app-shell">
      <aside className="navigation-rail" aria-label="Main navigation">
        <a className="rail-logo" href="/" aria-label="JARVIS home">
          <Command size={23} />
        </a>
        <nav>
          {navigation.map(({ id, name, icon: Icon }) => (
            <button
              key={name}
              className={workspaceSection === id ? "selected" : ""}
              disabled={health?.deployment === "cloud" && id !== null}
              aria-label={name}
              title={name}
              aria-pressed={workspaceSection === id}
              onClick={() => setWorkspaceSection(id)}
            >
              <Icon size={20} />
              <span className="sr-only">{name}</span>
            </button>
          ))}
        </nav>
        <button
          className="rail-settings"
          disabled={health?.deployment === "cloud"}
          aria-label="Settings"
          title="Settings"
          onClick={() => setWorkspaceSection("settings")}
        >
          <Settings2 size={20} />
        </button>
        <span
          className="rail-presence"
          aria-label={health ? "System connected" : "System disconnected"}
          data-connected={!!health}
        />
      </aside>
      <div className="workspace-shell">
        <header className="topbar">
          <a className="brand" href="/" aria-label="JARVIS home">
            JARVIS<span>AI</span>
          </a>
          <div className="breadcrumb">
            Workspace
            <ChevronRight size={12} />
            <span>Assistant</span>
          </div>
          <div className="topbar-right">
            <span
              className={`connection ${health ? "connected" : ""}`}
              role="status"
            >
              <i />
              {health ? "System online" : "Disconnected"}
            </span>
            <button
              className="icon-button"
              disabled={loading}
              aria-label="Refresh connection"
              title="Refresh connection"
              onClick={() => void checkConnection()}
            >
              <RefreshCw size={15} className={loading ? "spin" : ""} />
            </button>
          </div>
        </header>
        <main className="command-deck">
          <section
            className="intelligence-stage"
            aria-label="JARVIS assistant core"
          >
            <div className="stage-heading">
              <span className="eyebrow">
                <i />
                PERSONAL INTELLIGENCE
              </span>
              <span className="stage-index">01 / CORE</span>
            </div>
            <div className="hero-copy">
              <h1>
                At your service<span>.</span>
              </h1>
              <p>
                {health
                  ? "Your world. A little more connected."
                  : "Reconnect to continue."}
              </p>
            </div>
            <div className={`core-container state-${assistantState}`}>
              <span className="core-corner corner-tl" />
              <span className="core-corner corner-tr" />
              <span className="core-corner corner-bl" />
              <span className="core-corner corner-br" />
              <motion.svg
                className="hud-ring ring-outer"
                viewBox="0 0 400 400"
                aria-hidden="true"
                animate={reducedMotion ? {} : { rotate: 360 }}
                transition={{ duration: 120, repeat: Infinity, ease: "linear" }}
              >
                <circle
                  cx="200"
                  cy="200"
                  r="188"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1"
                  strokeDasharray="1 8"
                />
                {Array.from({ length: 60 }, (_, i) => (
                  <line
                    key={i}
                    x1="200"
                    y1="14"
                    x2="200"
                    y2={i % 5 === 0 ? "25" : "19"}
                    transform={`rotate(${i * 6} 200 200)`}
                    stroke="currentColor"
                    strokeWidth={i % 5 === 0 ? 2 : 1}
                  />
                ))}
                <circle
                  cx="200"
                  cy="200"
                  r="173"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1"
                  strokeDasharray="110 160 30 40"
                />
              </motion.svg>
              <motion.svg
                className="hud-ring ring-inner"
                viewBox="0 0 400 400"
                aria-hidden="true"
                animate={reducedMotion ? {} : { rotate: -360 }}
                transition={{ duration: 65, repeat: Infinity, ease: "linear" }}
              >
                <circle
                  cx="200"
                  cy="200"
                  r="158"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeDasharray="125 90 40 60"
                />
                <circle
                  cx="200"
                  cy="200"
                  r="149"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth=".5"
                />
              </motion.svg>
              <div className="core-aura" />
              <div className="neural-orb">
                <div className="orb-meridian meridian-one" />
                <div className="orb-meridian meridian-two" />
                <div className="orb-equator" />
                <AudioLines size={52} strokeWidth={1.1} />
              </div>
              <span className="core-marker marker-left">
                NEURAL
                <br />
                INTERFACE
              </span>
              <span className="core-marker marker-right">
                {health ? "LINK ACTIVE" : "NO LINK"}
                <br />
                J.A.R.V.I.S.
              </span>
            </div>
            <div className="core-state" role="status">
              <span className={`state-dot ${assistantState}`} />
              {stateLabel}
            </div>
            <button
              className={`core-activate ${voiceActive ? "is-active" : ""}`}
              disabled={
                !health?.capabilities.voice ||
                ["thinking", "transcribing"].includes(assistantState)
              }
              onClick={() =>
                document
                  .getElementById(voiceActive ? "voice-stop" : "voice-start")
                  ?.click()
              }
            >
              {voiceActive ? <Square size={17} /> : <Mic size={18} />}
              <span>{voiceActive ? "Stop listening" : "Start listening"}</span>
            </button>
            {error && (
              <p className="error" role="alert">
                {error}{" "}
                <a href="http://127.0.0.1:8000">Open desktop companion</a>
              </p>
            )}
            <div className="system-telemetry">
              <div className="telemetry-heading">
                <Cpu size={13} />
                <span>SYSTEM TELEMETRY</span>
                <span className="live-label">LIVE</span>
              </div>
              <div className="metric-row">
                <div className="metric">
                  <span>CPU</span>
                  <strong>
                    {system ? system.cpu_percent.toFixed(1) : "—"}
                    <small>%</small>
                  </strong>
                  <div className="metric-track">
                    <i style={{ width: `${system?.cpu_percent ?? 0}%` }} />
                  </div>
                </div>
                <div className="metric">
                  <span>MEMORY</span>
                  <strong>
                    {system ? system.ram_percent.toFixed(1) : "—"}
                    <small>%</small>
                  </strong>
                  <div className="metric-track purple">
                    <i style={{ width: `${system?.ram_percent ?? 0}%` }} />
                  </div>
                </div>
                <div className="metric mode-metric">
                  <span>DEFAULT MODE</span>
                  <strong>
                    <Zap size={14} />
                    {health?.mode ?? "—"}
                  </strong>
                  <small>
                    {system
                      ? `${system.ram_available_gb} GB available`
                      : "Telemetry unavailable"}
                  </small>
                </div>
              </div>
            </div>
          </section>
          <ChatPanel
            cloud={health?.deployment === "cloud"}
            defaultMode={health?.mode}
            onStateChange={setAssistantState}
            workspaceSection={workspaceSection}
            onOpenWorkspace={setWorkspaceSection}
            onCloseWorkspace={() => setWorkspaceSection(null)}
          />
        </main>
        <footer className="status-strip">
          <span>
            <Wifi size={11} />
            {health
              ? health.deployment === "cloud"
                ? "Cloud connected · HTTPS"
                : "Connection secure · localhost"
              : "Local connection unavailable"}
          </span>
          <span>
            JARVIS<span className="footer-dot">/</span>PERSONAL AI
          </span>
        </footer>
      </div>
    </div>
  );
}
