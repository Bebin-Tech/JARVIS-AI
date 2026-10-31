import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Volume2 } from "lucide-react";

type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: { results: { transcript: string }[][] }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};
export default function CloudVoice({
  onTranscript,
  onStateChange,
}: {
  onTranscript: (text: string) => Promise<string | undefined>;
  onStateChange?: (state: string) => void;
}) {
  const [state, setState] = useState("idle");
  const [language, setLanguage] = useState("en-US");
  const [error, setError] = useState("");
  const [transcript, setTranscript] = useState("");
  const [spoken, setSpoken] = useState(true);
  const recognition = useRef<Recognition | null>(null);
  const generation = useRef(0);
  const supported = Boolean(
    (window as SpeechWindow).SpeechRecognition ||
    (window as SpeechWindow).webkitSpeechRecognition,
  );
  useEffect(() => {
    onStateChange?.(state);
  }, [state, onStateChange]);
  useEffect(
    () => () => {
      generation.current++;
      recognition.current?.abort();
      window.speechSynthesis?.cancel();
    },
    [],
  );
  function stop() {
    generation.current++;
    recognition.current?.abort();
    recognition.current = null;
    window.speechSynthesis?.cancel();
    setState("idle");
  }
  function start() {
    stop();
    setError("");
    setTranscript("");
    const Constructor =
      (window as SpeechWindow).SpeechRecognition ||
      (window as SpeechWindow).webkitSpeechRecognition;
    if (!Constructor) {
      setError(
        "Voice recognition is unavailable in this browser. Open this site in Chrome or Edge, or type your message.",
      );
      return;
    }
    const run = generation.current;
    const input = new Constructor();
    recognition.current = input;
    input.lang = language;
    input.continuous = false;
    input.interimResults = false;
    let received = false;
    input.onresult = (event) => {
      if (run !== generation.current) return;
      received = true;
      const text = event.results[0]?.[0]?.transcript?.trim();
      if (!text) {
        setState("idle");
        return;
      }
      setTranscript(text);
      setState("thinking");
      void onTranscript(text)
        .then((reply) => {
          if (run !== generation.current) return;
          if (!reply || !spoken || !window.speechSynthesis) {
            setState("idle");
            return;
          }
          const output = new SpeechSynthesisUtterance(reply);
          output.lang = language;
          const voices = window.speechSynthesis.getVoices();
          const voice = voices.find((v) =>
            v.lang.toLowerCase().startsWith(language.slice(0, 2)),
          );
          if (voice) output.voice = voice;
          if (language === "ta-IN" && !voice) {
            setError(
              "No Tamil playback voice is available in this browser. The reply is shown in chat.",
            );
            setState("idle");
            return;
          }
          output.onend = () => {
            if (run === generation.current) setState("idle");
          };
          output.onerror = (e) => {
            if (run === generation.current) {
              setState("idle");
              if (e.error !== "canceled" && e.error !== "interrupted")
                setError(
                  "Speech playback was blocked. The reply is shown in chat.",
                );
            }
          };
          setState("speaking");
          window.speechSynthesis.speak(output);
        })
        .catch(() => {
          if (run === generation.current) {
            setError("Voice request failed. Please try again.");
            setState("idle");
          }
        });
    };
    input.onerror = (event) => {
      if (run !== generation.current) return;
      setState("idle");
      setError(
        event.error === "not-allowed"
          ? "Allow microphone access for this site, then try again."
          : event.error === "no-speech"
            ? "No speech detected. Please try again."
            : `Voice recognition failed (${event.error}). Try Chrome or Edge with internet access.`,
      );
    };
    input.onend = () => {
      if (!received && run === generation.current) setState("idle");
    };
    try {
      setState("listening");
      input.start();
    } catch {
      setState("idle");
      setError("Could not start the microphone. Please try again.");
    }
  }
  return (
    <section className="voice-panel" aria-label="Cloud voice controls">
      <div className="voice-heading">
        <Mic size={14} />
        <strong>VOICE CHANNEL</strong>
        <span role="status">{state === "idle" ? "Ready" : state}</span>
      </div>
      <div className="voice-console">
        <span>
          {state === "listening" ? "Listening…" : "Cloud conversation"}
        </span>
        <div className="voice-actions">
          <button
            id="voice-start"
            className="voice-start"
            disabled={state !== "idle" || !supported}
            onClick={start}
          >
            <Mic size={15} />
            Start voice
          </button>
          {state === "listening" && (
            <button onClick={() => recognition.current?.stop()}>Finish</button>
          )}
          <button
            id="voice-stop"
            className="voice-stop"
            disabled={state === "idle"}
            onClick={stop}
            aria-label="Stop and mute microphone"
          >
            <MicOff size={15} />
          </button>
        </div>
      </div>
      <details className="voice-settings">
        <summary>
          Voice options
          <span>{language === "ta-IN" ? "தமிழ்" : "EN"} · Browser</span>
        </summary>
        <div className="voice-options">
          <label>
            Language
            <select
              value={language}
              disabled={state !== "idle"}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="en-US">English</option>
              <option value="ta-IN">Tamil · தமிழ்</option>
            </select>
          </label>
          <label>
            <input
              type="checkbox"
              checked={spoken}
              onChange={(e) => setSpoken(e.target.checked)}
            />
            <Volume2 size={14} />
            Speak replies
          </label>
        </div>
      </details>
      <small>
        Voice uses your browser’s speech service after you press Start. No
        standby recording.
      </small>
      {!supported && (
        <p className="chat-notice">
          Use Chrome or Edge for voice recognition. Text chat works here.
        </p>
      )}
      {transcript && <p className="voice-transcript">{transcript}</p>}
      {error && (
        <p role="alert" className="chat-error">
          {error}
        </p>
      )}
    </section>
  );
}
