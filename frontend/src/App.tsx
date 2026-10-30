import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  ArrowUpRight,
  Check,
  Cpu,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import ChatPanel from "./ChatPanel";

type Health = {
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
      if (!response.ok) throw new Error(`Backend returned ${response.status}`);
      setHealth((await response.json()) as Health);
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
        const value = await response.json();
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

  return (
    <div className="app-shell">
      <header>
        <a className="brand" href="/" aria-label="JARVIS home">
          <span className="brand-icon">J</span>JARVIS
          <span className="brand-tag">PERSONAL INTELLIGENCE</span>
        </a>
        <span
          className={`connection ${health ? "connected" : ""}`}
          role="status"
        >
          <i />
          {health ? "LOCAL BACKEND CONNECTED" : "BACKEND DISCONNECTED"}
        </span>
      </header>
      <main>
        <div className="eyebrow">YOUR WORKSPACE / PERSONAL INTELLIGENCE</div>
        <div className="title-row">
          <div>
            <h1>Intelligence starts here.</h1>
            <p>Your local workspace for cloud and on-device conversation.</p>
          </div>
          <span className="version">BUILD 0.1.0</span>
        </div>
        <div className="dashboard">
          <section
            className="core-panel"
            aria-label="Assistant initialization status"
          >
            <div className="panel-top">
              <span>
                <Activity size={14} /> ASSISTANT CORE
              </span>
              <span className="phase">LOCAL AI</span>
            </div>
            <div className="core-container">
              <motion.div
                className="orbital outer"
                animate={reducedMotion ? {} : { rotate: 360 }}
                transition={{ duration: 70, repeat: Infinity, ease: "linear" }}
              />
              <motion.div
                className="orbital inner"
                animate={reducedMotion ? {} : { rotate: -360 }}
                transition={{ duration: 50, repeat: Infinity, ease: "linear" }}
              />
              <div className={`core state-${assistantState}`}>
                <span>J</span>
                <small>{assistantState.toUpperCase()}</small>
              </div>
              <div className="orbit-label">LOCAL · PRIVATE · MODULAR</div>
            </div>
            <h2>{health ? "Systems online" : "Awaiting connection"}</h2>
            <p className="core-description">
              {health
                ? "Your local service is ready. Speak or type below. Your local AI and speech engines are ready."
                : "Start the Python backend to connect your workspace."}
            </p>
            <button disabled={loading} onClick={() => void checkConnection()}>
              <RefreshCw size={16} className={loading ? "spin" : ""} />
              {loading ? "Checking connection…" : "Check connection"}
            </button>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <div className="core-footer">
              <ShieldCheck size={14} /> Microphone starts on request · Actions
              require approval
            </div>
          </section>
          <aside>
            <section className="panel status-panel">
              <div className="panel-top">
                <span>
                  <Cpu size={14} /> SYSTEM STATUS
                </span>
              </div>
              <dl>
                <div>
                  <dt>CPU usage</dt>
                  <dd>
                    {system
                      ? `${system.cpu_percent.toFixed(1)}%`
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>RAM usage</dt>
                  <dd>
                    {system
                      ? `${system.ram_percent.toFixed(1)}% · ${system.ram_available_gb} GB free`
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Backend</dt>
                  <dd className={health ? "cyan" : ""}>
                    {health ? "Connected" : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Configured mode</dt>
                  <dd>{health?.mode ?? "—"}</dd>
                </div>
                <div>
                  <dt>OpenAI key</dt>
                  <dd>
                    {health
                      ? health.openai_configured
                        ? "Configured"
                        : "Not configured"
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt>Voice engine</dt>
                  <dd>Local Whisper + Piper</dd>
                </div>
                <div>
                  <dt>Automation</dt>
                  <dd>Approval required</dd>
                </div>
              </dl>
            </section>
            <section className="panel">
              <div className="panel-top">
                <span>
                  <ShieldCheck size={14} /> BUILT AROUND YOUR PRIVACY
                </span>
              </div>
              <p>
                Localhost access only. API secrets stay on the backend. No audio
                capture, model requests, or computer actions run on startup.
              </p>
            </section>
          </aside>
        </div>
        <ChatPanel
          defaultMode={health?.mode}
          onStateChange={setAssistantState}
        />
        <section className="setup panel">
          <div>
            <div className="eyebrow">DEVELOPMENT CHECKPOINT</div>
            <h2>Local intelligence · Voice & actions</h2>
            <p>
              Start voice or enable agent tools. Review changes in the Tasks
              panel.
            </p>
          </div>
          <div className="setup-steps">
            <span>
              <Check size={15} /> Local backend + live telemetry
            </span>
            <span>
              <Check size={15} /> OpenAI + Ollama adapters
            </span>
            <span>
              <Check size={15} /> Opt-in SQLite conversation history
            </span>
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
            >
              Explore local API <ArrowUpRight size={15} />
            </a>
          </div>
        </section>
      </main>
      <footer>
        <span>JARVIS AI / WINDOWS PERSONAL ASSISTANT</span>
        <span>DEVELOPMENT RELEASE · LOCAL AI + VOICE + APPROVED TOOLS</span>
      </footer>
    </div>
  );
}
