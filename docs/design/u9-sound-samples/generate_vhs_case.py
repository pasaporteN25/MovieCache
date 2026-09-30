"""Exploración de sacar/abrir una caja VHS. GPLv3; síntesis sin grabaciones.

Reutiliza utilidades locales de generate.py; sólo necesita Python estándar.
"""

from __future__ import annotations

import hashlib
import json
import math
import random

from generate import OUTPUT, RATE, lowpass, noise, resonator, write_wav


def bump(t: float, start: float, duration: float) -> float:
    phase = (t - start) / duration
    return math.sin(math.pi * phase) ** 1.3 if 0 < phase < 1 else 0.0


def shell(t: float) -> float:
    return (
        resonator(t, 410, 0.018)
        + 0.45 * resonator(t, 1130, 0.010)
        + 0.20 * resonator(t, 2370, 0.005)
    )


def finish(values: list[float]) -> list[float]:
    values = lowpass(values, 6500)
    mean = sum(values) / len(values)
    values = [
        (x - mean) * min(1.0, i / 96, (len(values) - 1 - i) / 480) for i, x in enumerate(values)
    ]
    rms = math.sqrt(sum(x * x for x in values) / len(values))
    gain = min(10 ** (-26 / 20) / rms, 10 ** (-12 / 20) / max(map(abs, values)))
    return [x * gain for x in values]


def pull() -> list[float]:
    count = round(RATE * 0.44)
    friction = noise(count, 921, 180, 3900)
    pressure = lowpass(noise(count, 922, 8, 95), 75)
    values = []
    for i, grain in enumerate(friction):
        t = i / RATE
        # Arranque breve, deslizamiento irregular y borde que se libera al final.
        rubbing = bump(t, 0.018, 0.33) + 0.4 * bump(t, 0.25, 0.12)
        value = grain * rubbing * max(0.25, 0.8 + pressure[i] * 4)
        value += 0.12 * shell(t - 0.024) + 0.15 * shell(t - 0.355)
        values.append(value)
    return finish(values)


def opening() -> list[float]:
    count = round(RATE * 0.56)
    friction = noise(count, 931, 420, 4800)
    rng = random.Random(932)
    # La bisagra cede a pequeños saltos irregulares; evita un chirrido tonal sostenido.
    ticks = []
    moment = 0.125
    while moment < 0.43:
        ticks.append((moment, rng.uniform(0.035, 0.105)))
        moment += rng.uniform(0.009, 0.028)
    values = []
    for i, grain in enumerate(friction):
        t = i / RATE
        value = 0.20 * grain * bump(t, 0.005, 0.075)
        # Lengüeta que destraba, rebote del plástico y flexión de las dos tapas.
        value += 0.95 * shell(t - 0.075) + 0.38 * shell(t - 0.089)
        value += grain * (0.32 * bump(t, 0.105, 0.19) + 0.17 * bump(t, 0.27, 0.19))
        for onset, gain in ticks:
            value += gain * shell(t - onset)
        value += 0.20 * shell(t - 0.455)
        values.append(value)
    return finish(values)


def main() -> None:
    take_out = pull()
    open_case = opening()
    sequence = take_out + [0.0] * round(RATE * 0.22) + open_case
    manifest = []
    for name, sample in (
        ("04-sacar-vhs", take_out),
        ("05-abrir-caja", open_case),
        ("06-sacar-y-abrir", sequence),
    ):
        raw = write_wav(OUTPUT / f"{name}.wav", sample)
        audition = [0.0] * round(RATE * 0.25)
        for _ in range(2):
            audition.extend(sample)
            audition.extend([0.0] * round(RATE * 0.9))
        write_wav(OUTPUT / f"{name}-escucha.wav", audition)
        manifest.append(
            {
                "file": f"{name}.wav",
                "audition": f"{name}-escucha.wav",
                "duration_ms": round(1000 * len(sample) / RATE),
                "peak_dbfs": round(20 * math.log10(max(map(abs, sample))), 2),
                "rms_dbfs": round(
                    20 * math.log10(math.sqrt(sum(x * x for x in sample) / len(sample))), 2
                ),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    (OUTPUT / "manifest-vhs-case.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
