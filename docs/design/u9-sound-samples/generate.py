"""Muestras U9 sintetizadas desde cero; sin grabaciones ni dependencias externas.

Licencia: GPLv3, como el proyecto (ver ../../../LICENSE).
Ejecutar con Python 3.11+: python docs/design/u9-sound-samples/generate.py
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import wave
from pathlib import Path

RATE = 48000
OUTPUT = Path(__file__).resolve().parent


def lowpass(values: list[float], cutoff: float) -> list[float]:
    alpha = 1 - math.exp(-2 * math.pi * cutoff / RATE)
    previous = 0.0
    result = []
    for value in values:
        previous += alpha * (value - previous)
        result.append(previous)
    return result


def noise(count: int, seed: int, low: float, high: float) -> list[float]:
    rng = random.Random(seed)
    source = [rng.uniform(-1, 1) for _ in range(count)]
    upper = lowpass(source, high)
    lower = lowpass(upper, low)
    return [a - b for a, b in zip(upper, lower, strict=True)]


def resonator(t: float, frequency: float, decay: float) -> float:
    if t < 0:
        return 0.0
    return math.sin(2 * math.pi * frequency * t) * math.exp(-t / decay)


def make_sample(kind: str, duration: float, seed: int) -> list[float]:
    count = round(RATE * duration)
    cutoff = {"roce": 3400, "clic": 4600, "toque": 1800}[kind]
    texture = noise(count, seed, 350, cutoff)
    result = []
    for i, grain in enumerate(texture):
        t = i / RATE
        if kind == "roce":
            # Fricción corta con dos cambios de presión, sin tono electrónico.
            envelope = math.sin(math.pi * i / (count - 1)) ** 1.4
            pressure = 0.72 + 0.18 * math.sin(2 * math.pi * 31 * t)
            value = grain * envelope * pressure
        elif kind == "clic":
            # Plástico hueco: ataque y un segundo encastre más débil a los 19 ms.
            value = grain * math.exp(-t / 0.007) * 0.65
            for delay, gain in ((0.0, 1.0), (0.019, 0.38)):
                value += gain * (
                    0.50 * resonator(t - delay, 1250, 0.006)
                    + 0.25 * resonator(t - delay, 2180, 0.004)
                    + 0.22 * resonator(t - delay, 480, 0.010)
                )
        else:
            # Golpe amortiguado: cuerpo grave y textura de papel mate.
            value = (
                0.7 * resonator(t, 310, 0.011)
                + 0.20 * resonator(t, 740, 0.007)
                + grain * math.exp(-t / 0.013) * 0.55
            )
        # Entrada/salida a cero para evitar discontinuidades ajenas al timbre.
        attack = min(1.0, t / 0.0015)
        release = min(1.0, (count - 1 - i) / (RATE * 0.010))
        result.append(value * attack * release)

    # Igual RMS como punto de partida; la sonoridad percibida se elige escuchando.
    rms = math.sqrt(sum(x * x for x in result) / count)
    gain = min(10 ** (-29 / 20) / rms, 10 ** (-14 / 20) / max(map(abs, result)))
    return [value * gain for value in result]


def write_wav(path: Path, values: list[float]) -> bytes:
    pcm = struct.pack(f"<{len(values)}h", *(round(value * 32767) for value in values))
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes(pcm)
    return path.read_bytes()


def main() -> None:
    manifest = []
    for index, (kind, duration) in enumerate(
        (("roce", 0.120), ("clic", 0.100), ("toque", 0.090)), 1
    ):
        sample = make_sample(kind, duration, seed=900 + index)
        name = f"{index:02d}-{kind}"
        raw = write_wav(OUTPUT / f"{name}.wav", sample)
        audition = [0.0] * round(RATE * 0.25)
        for _ in range(3):
            audition.extend(sample)
            audition.extend([0.0] * round(RATE * 0.70))
        write_wav(OUTPUT / f"{name}-escucha.wav", audition)
        manifest.append(
            {
                "file": f"{name}.wav",
                "audition": f"{name}-escucha.wav",
                "duration_ms": round(1000 * duration),
                "sample_rate": RATE,
                "channels": 1,
                "pcm_bits": 16,
                "peak_dbfs": round(20 * math.log10(max(map(abs, sample))), 2),
                "rms_dbfs": round(
                    20 * math.log10(math.sqrt(sum(x * x for x in sample) / len(sample))), 2
                ),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
