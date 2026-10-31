import { readApiJson } from "./apiResponse";
import { useEffect, useState } from "react";

type AudioSettings = {
  microphone_device: number | null;
  language: string;
  wake_threshold: number;
  followup_seconds: number;
  speech_volume: number;
};

export default function BackgroundSettings() {
  const [settings, setSettings] = useState<AudioSettings | null>(null);
  const [devices, setDevices] = useState<{ id: number; name: string }[]>([]);
  const [message, setMessage] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      fetch("/api/background/settings", { signal: controller.signal }).then(
        (r) => {
          if (!r.ok) throw new Error();
          return readApiJson(r);
        },
      ),
      fetch("/api/background/devices", { signal: controller.signal }).then(
        (r) => {
          if (!r.ok) throw new Error();
          return readApiJson(r);
        },
      ),
    ])
      .then(([audio, inputs]) => {
        setSettings(audio);
        setDevices(inputs);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setMessage("Audio settings unavailable.");
      });
    return () => controller.abort();
  }, []);
  if (!settings) return <small>{message || "Loading audio settings…"}</small>;
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void fetch("/api/background/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(settings),
        })
          .then((r) => {
            if (!r.ok) throw new Error();
            setMessage("Saved");
          })
          .catch(() => setMessage("Could not save audio settings."));
      }}
    >
      <div className="voice-options">
        <label>
          Language
          <select
            value={settings.language}
            onChange={(e) =>
              setSettings({ ...settings, language: e.target.value })
            }
          >
            <option value="auto">Auto · English / Tamil</option>
            <option value="en">English</option>
            <option value="ta">Tamil · தமிழ்</option>
          </select>
        </label>
        <label>
          Microphone
          <select
            value={settings.microphone_device ?? ""}
            onChange={(e) =>
              setSettings({
                ...settings,
                microphone_device:
                  e.target.value === "" ? null : Number(e.target.value),
              })
            }
          >
            <option value="">System default</option>
            {devices.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Wake threshold
          <input
            type="number"
            min="0.1"
            max="0.95"
            step="0.05"
            value={settings.wake_threshold}
            onChange={(e) =>
              setSettings({
                ...settings,
                wake_threshold: Number(e.target.value),
              })
            }
          />
        </label>
        <label>
          Follow-up seconds
          <input
            type="number"
            min="3"
            max="120"
            value={settings.followup_seconds}
            onChange={(e) =>
              setSettings({
                ...settings,
                followup_seconds: Number(e.target.value),
              })
            }
          />
        </label>
        <label>
          Speech volume
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={settings.speech_volume}
            onChange={(e) =>
              setSettings({
                ...settings,
                speech_volume: Number(e.target.value),
              })
            }
          />
        </label>
      </div>
      <button type="submit">Save audio</button>{" "}
      <small role="status">{message}</small>
    </form>
  );
}
