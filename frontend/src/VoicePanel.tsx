import { readApiJson } from "./apiResponse";
import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Radio, Volume2 } from "lucide-react";
import BackgroundSettings from "./BackgroundSettings";

type Props = {
  onTranscript: (text: string) => Promise<string | undefined>;
  mode: string;
  onStateChange?: (state: string) => void;
};
type State =
  | "idle"
  | "connecting"
  | "listening"
  | "armed"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "error";

function wavBlob(frames: Int16Array[]): Blob {
  const length = frames.reduce((sum, frame) => sum + frame.length, 0);
  const buffer = new ArrayBuffer(44 + length * 2);
  const view = new DataView(buffer);
  const word = (offset: number, value: string) =>
    [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  word(0, "RIFF");
  view.setUint32(4, 36 + length * 2, true);
  word(8, "WAVE");
  word(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true);
  view.setUint32(28, 32000, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  word(36, "data");
  view.setUint32(40, length * 2, true);
  let offset = 44;
  for (const frame of frames)
    for (const value of frame) {
      view.setInt16(offset, value, true);
      offset += 2;
    }
  return new Blob([buffer], { type: "audio/wav" });
}

async function checked(response: Response) {
  if (!response.ok) {
    const body = await readApiJson(response).catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Voice request failed (${response.status})`,
    );
  }
  return response;
}

export default function VoicePanel({
  onTranscript,
  mode,
  onStateChange,
}: Props) {
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [language, setLanguage] = useState("en");
  const [volume, setVolume] = useState(0.8);
  const [wake, setWake] = useState(false);
  const [device, setDevice] = useState("");
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voice, setVoice] = useState("piper");
  const [native, setNative] = useState<{
    running: boolean;
    state: string;
    paused: boolean;
    level: number;
    error: string;
  } | null>(null);
  const [transcript, setTranscript] = useState("");
  const [level, setLevel] = useState(0);
  const [levels, setLevels] = useState<number[]>(Array(36).fill(0));
  const [available, setAvailable] = useState({
    stt: false,
    tts: false,
    wake: false,
  });
  const live = useRef(false);
  const currentState = useRef<State>("idle");
  const stream = useRef<MediaStream | null>(null);
  const context = useRef<AudioContext | null>(null);
  const node = useRef<AudioWorkletNode | null>(null);
  const socket = useRef<WebSocket | null>(null);
  const peer = useRef<RTCPeerConnection | null>(null);
  const player = useRef<HTMLAudioElement | null>(null);
  const request = useRef<AbortController | null>(null);
  const frames = useRef<Int16Array[]>([]);
  const heardSpeech = useRef(false);
  const silence = useRef(0);
  const preRoll = useRef<Int16Array[]>([]);
  const callback = useRef(onTranscript);
  callback.current = onTranscript;
  const generation = useRef(0);
  const wakeMode = useRef(false);
  const micTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const useNative = native?.running && !live.current;
  const shownState = useNative ? native.state : state;
  const active = useNative
    ? !native.paused
    : !["idle", "error"].includes(state);
  const volumeRef = useRef(volume);
  volumeRef.current = volume;

  function transition(next: State) {
    currentState.current = next;
    setState(next);
  }
  useEffect(() => {
    onStateChange?.(shownState);
  }, [shownState, onStateChange]);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const response = await fetch("/api/background/status", {
          signal: AbortSignal.timeout(3000),
        });
        if (response.ok && !cancelled) {
          const value = await readApiJson(response);
          setNative(value);
          if (value.running && !live.current) {
            setLevel(value.level ?? 0);
            setLevels((previous) => [...previous.slice(1), value.level ?? 0]);
          }
        }
      } catch {
        /* Native process is optional in browser-only mode. */
      }
      if (!cancelled) timer = setTimeout(() => void refresh(), 1000);
    }
    void refresh();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);
  async function nativeCommand(action: string) {
    try {
      const response = await checked(
        await fetch("/api/background/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        }),
      );
      setNative(await readApiJson(response));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Background command failed",
      );
    }
  }

  function interrupt() {
    if (player.current) {
      player.current.pause();
      player.current.src = "";
      player.current = null;
    }
    window.speechSynthesis?.cancel();
  }

  function stop() {
    generation.current++;
    if (micTimer.current) clearTimeout(micTimer.current);
    live.current = false;
    request.current?.abort();
    socket.current?.close();
    socket.current = null;
    peer.current?.close();
    peer.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    node.current?.disconnect();
    node.current = null;
    void context.current?.close();
    context.current = null;
    interrupt();
    frames.current = [];
    preRoll.current = [];
    setLevel(0);
    setLevels(Array(36).fill(0));
    transition("idle");
  }

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/voice/status", { signal: controller.signal })
      .then(checked)
      .then((r) => readApiJson(r))
      .then(setAvailable)
      .catch(() => {});
    function update() {
      setVoices(window.speechSynthesis?.getVoices() ?? []);
    }
    update();
    window.speechSynthesis?.addEventListener("voiceschanged", update);
    return () => {
      controller.abort();
      window.speechSynthesis?.removeEventListener("voiceschanged", update);
      stop();
    };
    // Resource handles live in refs and stop() deliberately reads their latest values.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (player.current) player.current.volume = volume;
  }, [volume]);

  async function speak(text: string, run: number) {
    if (!text || run !== generation.current) return;
    transition("speaking");
    if (voice !== "piper") {
      const chosen = voices.find((v) => v.voiceURI === voice);
      if (!chosen || (mode === "offline" && !chosen.localService))
        throw new Error(
          "Select an installed local system voice for offline speech.",
        );
      await new Promise<void>((resolve, reject) => {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.voice = chosen;
        utterance.lang = language === "ta" ? "ta-IN" : "en-US";
        utterance.volume = volume;
        utterance.onend = () => resolve();
        utterance.onerror = (e) =>
          e.error === "interrupted" || e.error === "canceled"
            ? resolve()
            : reject(new Error(`System speech failed: ${e.error}`));
        window.speechSynthesis.speak(utterance);
      });
    } else {
      const response = await checked(
        await fetch("/api/voice/speak", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text.slice(0, 3000) }),
          signal: request.current?.signal,
        }),
      );
      const url = URL.createObjectURL(await response.blob());
      if (run !== generation.current) {
        URL.revokeObjectURL(url);
        return;
      }
      const audio = new Audio(url);
      audio.volume = volumeRef.current;
      player.current = audio;
      try {
        await audio.play();
        await new Promise<void>((resolve, reject) => {
          audio.onended = () => resolve();
          audio.onerror = () => reject(new Error("Audio playback failed"));
          audio.onpause = () => resolve();
        });
      } finally {
        URL.revokeObjectURL(url);
        if (player.current === audio) player.current = null;
      }
    }
  }

  async function finish() {
    if (
      !frames.current.length ||
      ["transcribing", "thinking"].includes(currentState.current)
    )
      return;
    const run = generation.current;
    const audio = wavBlob(frames.current);
    frames.current = [];
    heardSpeech.current = false;
    silence.current = 0;
    transition("transcribing");
    request.current = new AbortController();
    try {
      const response = await checked(
        await fetch(`/api/voice/transcribe?language=${language}`, {
          method: "POST",
          headers: { "Content-Type": "audio/wav" },
          body: audio,
          signal: request.current.signal,
        }),
      );
      const result = (await readApiJson(response)) as { text: string };
      if (run !== generation.current) return;
      const text = result.text.replace(/^hey\s+jarvis[,\s]*/i, "").trim();
      setTranscript(text);
      if (text) {
        transition("thinking");
        const reply = await callback.current(text);
        if (run === generation.current && reply) await speak(reply, run);
      }
      if (run === generation.current) {
        if (wakeMode.current && live.current) transition("armed");
        else stop();
      }
    } catch (err) {
      if (run !== generation.current) return;
      stop();
      transition("error");
      setError(err instanceof Error ? err.message : "Voice processing failed");
    }
  }

  async function start(realtime = false) {
    if (native?.running && !realtime) {
      await nativeCommand("activate");
      return;
    }
    stop();
    setError("");
    setTranscript("");
    transition("connecting");
    const run = generation.current;
    wakeMode.current = wake && !realtime;
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error("Microphone access requires localhost or HTTPS.");
      const acquisition = navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: device ? { exact: device } : undefined,
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
        },
      });
      void acquisition.then(
        (acquired) => {
          if (run !== generation.current)
            acquired.getTracks().forEach((track) => track.stop());
        },
        () => {},
      );
      const acquired = await Promise.race([
        acquisition,
        new Promise<MediaStream>((_, reject) => {
          micTimer.current = setTimeout(
            () =>
              reject(
                new Error(
                  "Microphone permission is pending. Allow microphone access in your browser, then try again.",
                ),
              ),
            30000,
          );
        }),
      ]);
      if (micTimer.current) clearTimeout(micTimer.current);
      if (run !== generation.current) {
        acquired.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = acquired;
      live.current = true;
      setDevices(
        (await navigator.mediaDevices.enumerateDevices()).filter(
          (item) => item.kind === "audioinput",
        ),
      );
      stream.current.getAudioTracks().forEach((track) => {
        track.onended = () => {
          stop();
          setError("Microphone disconnected. Reconnect it and start again.");
        };
      });
      if (realtime) {
        if (mode === "offline")
          throw new Error("Cloud Realtime is unavailable in offline mode.");
        const pc = new RTCPeerConnection();
        peer.current = pc;
        const audio = new Audio();
        audio.autoplay = true;
        audio.volume = volume;
        player.current = audio;
        pc.ontrack = (event) => {
          audio.srcObject = event.streams[0];
          void audio
            .play()
            .catch(() => setError("Click the page to allow audio playback."));
        };
        stream.current
          .getTracks()
          .forEach((track) => pc.addTrack(track, stream.current!));
        const channel = pc.createDataChannel("oai-events");
        channel.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "input_audio_buffer.speech_started")
              transition("listening");
            if (data.type === "response.created") transition("thinking");
            if (data.type === "response.output_audio_transcript.delta") {
              transition("speaking");
              setTranscript((previous) => previous + data.delta);
            }
            if (data.type === "response.done") transition("listening");
            if (data.type === "error")
              setError("Realtime reported an error. Check API configuration.");
          } catch {
            setError("Invalid Realtime event");
          }
        };
        pc.onconnectionstatechange = () => {
          if (
            ["failed", "disconnected", "closed"].includes(pc.connectionState) &&
            live.current
          ) {
            stop();
            setError("Realtime disconnected. Start again to reconnect.");
          }
        };
        await pc.setLocalDescription(await pc.createOffer());
        const response = await checked(
          await fetch(`/api/voice/realtime?mode=${mode}`, {
            method: "POST",
            headers: { "Content-Type": "application/sdp" },
            body: pc.localDescription!.sdp,
          }),
        );
        if (run !== generation.current) return;
        await pc.setRemoteDescription({
          type: "answer",
          sdp: await response.text(),
        });
        transition("listening");
        return;
      }
      if (wakeMode.current) {
        const ws = new WebSocket(
          `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/voice/wake`,
        );
        socket.current = ws;
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.error) {
            stop();
            setError(data.error);
            return;
          }
          if (
            data.wake &&
            ["armed", "speaking"].includes(currentState.current)
          ) {
            generation.current++;
            request.current?.abort();
            interrupt();
            frames.current = [...preRoll.current];
            heardSpeech.current = false;
            silence.current = 0;
            transition("listening");
          }
        };
        ws.onclose = () => {
          if (live.current && socket.current === ws) {
            stop();
            setError("Wake connection closed. Start again to reconnect.");
          }
        };
      }
      context.current = new AudioContext({ sampleRate: 16000 });
      await context.current.audioWorklet.addModule("/pcm-worklet.js");
      const source = context.current.createMediaStreamSource(stream.current);
      const worklet = new AudioWorkletNode(context.current, "jarvis-pcm");
      node.current = worklet;
      worklet.port.onmessage = (event) => {
        if (!live.current) return;
        const frame = new Int16Array(event.data as ArrayBuffer);
        let sum = 0;
        for (const value of frame) sum += (value / 32768) ** 2;
        const rms = Math.sqrt(sum / frame.length);
        setLevel(Math.min(1, rms * 12));
        setLevels((previous) => [...previous.slice(1), Math.min(1, rms * 12)]);
        preRoll.current = [...preRoll.current.slice(-4), frame];
        if (
          socket.current?.readyState === WebSocket.OPEN &&
          ["armed", "speaking"].includes(currentState.current)
        )
          socket.current.send(frame.buffer);
        if (currentState.current !== "listening") return;
        frames.current.push(frame);
        if (rms > 0.015) {
          heardSpeech.current = true;
          silence.current = 0;
        } else silence.current++;
        if (
          (heardSpeech.current && silence.current > 10) ||
          frames.current.length >= 750
        )
          void finish();
      };
      source.connect(worklet);
      worklet.connect(context.current.destination);
      await context.current.resume();
      frames.current = [];
      heardSpeech.current = false;
      silence.current = 0;
      transition(wakeMode.current ? "armed" : "listening");
    } catch (err) {
      if (run !== generation.current) return;
      stop();
      transition("error");
      setError(err instanceof Error ? err.message : "Microphone access failed");
    }
  }

  return (
    <section
      className="voice-panel"
      id="voice-controls"
      aria-label="Voice controls"
    >
      <div className="voice-heading">
        <Radio size={14} />
        <strong>VOICE CHANNEL</strong>
        <span role="status" className={active ? "voice-live" : ""}>
          {shownState === "standby"
            ? "Wake listening"
            : shownState === "armed"
              ? "Wake listening"
              : shownState === "idle"
                ? "Ready"
                : shownState}
        </span>
      </div>
      <div className="voice-console">
        <div
          className={`waveform ${active ? "is-live" : ""}`}
          aria-label="Live microphone waveform"
        >
          {levels.map((value, index) => (
            <i key={index} style={{ height: `${Math.max(3, value * 34)}px` }} />
          ))}
        </div>
        <div className="voice-actions">
          <button
            id="voice-start"
            className="voice-start"
            disabled={!available.stt || (active && !native?.running)}
            onClick={() => void start()}
          >
            <Mic size={15} />
            {native?.running
              ? native.paused
                ? "Resume voice"
                : "Speak now"
              : wake
                ? "Wake listening"
                : "Start voice"}
          </button>
          <button
            id="voice-stop"
            className="voice-stop"
            disabled={!active}
            onClick={() =>
              native?.running ? void nativeCommand("pause") : stop()
            }
            aria-label="Stop and mute microphone"
          >
            <MicOff size={15} />
          </button>
          {state === "listening" && (
            <button onClick={() => void finish()}>Finish</button>
          )}
        </div>
      </div>
      <details className="voice-settings">
        <summary>
          Voice options
          <span>
            {language === "ta" ? "தமிழ்" : "EN"} ·{" "}
            {voice === "piper" ? "Local" : "System"}
          </span>
        </summary>
        {native?.running ? (
          <BackgroundSettings />
        ) : (
          <>
            <div className="voice-options">
              <label>
                Language
                <select
                  value={language}
                  disabled={active}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  <option value="en">English</option>
                  <option value="ta">Tamil · தமிழ்</option>
                </select>
              </label>
              <label>
                Microphone
                <select
                  value={device}
                  disabled={active}
                  onChange={(e) => setDevice(e.target.value)}
                >
                  <option value="">System default</option>
                  {devices.map((d) => (
                    <option key={d.deviceId} value={d.deviceId}>
                      {d.label || "Microphone"}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Voice
                <select
                  value={voice}
                  disabled={active}
                  onChange={(e) => setVoice(e.target.value)}
                >
                  <option value="piper">Piper · English</option>
                  {voices
                    .filter((v) => mode !== "offline" || v.localService)
                    .map((v) => (
                      <option key={v.voiceURI} value={v.voiceURI}>
                        {v.name} · {v.lang}
                        {v.localService ? " · local" : " · network"}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            <div className="voice-preferences">
              <label>
                <input
                  type="checkbox"
                  checked={wake}
                  disabled={active || !available.wake}
                  onChange={(e) => setWake(e.target.checked)}
                />
                Wake word · continuous listening
              </label>
              <label>
                <Volume2 size={14} />
                <input
                  aria-label="Audio volume"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={volume}
                  onChange={(e) => setVolume(Number(e.target.value))}
                />
              </label>
              <button
                disabled={mode === "offline" || active}
                onClick={() => void start(true)}
              >
                Cloud Realtime
              </button>
            </div>
            {language === "ta" && (
              <small>Tamil playback requires an installed Tamil voice.</small>
            )}
          </>
        )}
      </details>
      {!available.stt && (
        <small className="voice-model-notice">
          Local speech is unavailable. Check voice model setup.
        </small>
      )}
      <div className="audio-meter" aria-label="Microphone level">
        <div style={{ width: `${level * 100}%` }} />
      </div>
      {transcript && <p className="voice-transcript">{transcript}</p>}
      {(error || native?.error) && (
        <p role="alert" className="chat-error">
          {error || native?.error}
        </p>
      )}
    </section>
  );
}
