class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frame = new Int16Array(1280);
    this.index = 0;
    this.phase = 0;
    this.sum = 0;
    this.count = 0;
  }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (const value of input) {
      this.sum += value;
      this.count++;
      this.phase += 16000;
      if (this.phase >= sampleRate) {
        this.phase -= sampleRate;
        const sample = Math.max(-1, Math.min(1, this.sum / this.count));
        this.frame[this.index++] = Math.round(sample * 32767);
        this.sum = 0;
        this.count = 0;
        if (this.index === 1280) {
          this.port.postMessage(this.frame.buffer, [this.frame.buffer]);
          this.frame = new Int16Array(1280);
          this.index = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("jarvis-pcm", PCMProcessor);
