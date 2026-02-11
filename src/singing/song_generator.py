"""
Song Generator - bruker GPT-4o-mini til å generere lyrics + melodi fra fri-tekst.
"""

import json
import os
import re
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du skriver korte, morsomme norske barnesanger for anda Ulrika. Rim er viktig!

REGLER:
1. Strukturen er ALLTID: vers1, refreng, vers2, refreng, vers3, refreng (6 deler i "verses")
2. Hvert vers har 2 korte linjer. Refrenget har 2 korte linjer. Linjene MÅ rime (parrim).
3. Hver stavelse = én note. Hvert vers trenger 10-14 noter. Refrenget trenger 8-12 noter.
4. MINIMUM 60 noter totalt. Bruk "lyric" for stavelsen til hver note.
5. Noter: C4-G5, duration 0.5 eller 1.0 beats. Tempo 110-120 BPM.
6. Akkordene MÅ dekke ALLE beats fra start til slutt av alle noter+pauser.
7. Hold tekstlinjene KORTE (5-8 ord per linje). Korte ord = bedre sang.

Returner KUN JSON:
{"title":"X","tempo_bpm":115,"key":"C","verses":[{"type":"verse","lyrics":"linje1\\nlinje2","notes":[{"note":"C4","duration":1.0,"lyric":"En"},{"note":"D4","duration":0.5,"lyric":"li-"},{"note":"E4","duration":0.5,"lyric":"ten"}]},{"type":"chorus","lyrics":"refreng","notes":[{"note":"G4","duration":1.0,"lyric":"Kvakk"}]}],"chords":[{"chord":"C","beat":0,"duration":4},{"chord":"G","beat":4,"duration":4}]}"""


class SongGenerator:
    def __init__(self, api_key: str = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate(self, prompt: str) -> dict:
        """Generer sang fra fri-tekst."""
        logger.info(f"📝 Genererer sang: '{prompt}'")

        last_error = None
        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                    max_tokens=4000,
                )

                raw = response.choices[0].message.content
                finish = response.choices[0].finish_reason

                if not raw or finish == "length":
                    logger.warning(f"  ⚠️ Respons kuttet (finish={finish}, len={len(raw) if raw else 0})")
                    # Prøv å lukke uavsluttet JSON
                    if raw:
                        raw = self._close_truncated_json(raw)

                song_data = json.loads(raw)
                song_data = self._normalize(song_data)
                self._validate(song_data)
                break
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                last_error = e
                logger.warning(f"  ⚠️ Forsøk {attempt+1}: {e}")
                if raw:
                    logger.warning(f"  Nøkler: {list(json.loads(raw).keys()) if raw.startswith('{') else raw[:200]}")
                    # Logg første vers-struktur for debugging
                    try:
                        d = json.loads(raw)
                        if "verses" in d and d["verses"]:
                            logger.warning(f"  Vers 0 nøkler: {list(d['verses'][0].keys())}")
                    except:
                        pass
                if attempt == 0:
                    continue
                raise last_error

        logger.info(
            f"  → '{song_data['title']}' | "
            f"{song_data['tempo_bpm']} BPM | "
            f"{sum(len(v.get('notes',[])) for v in song_data['verses'])} noter"
        )

        return song_data

    def _close_truncated_json(self, raw: str) -> str:
        """Forsøk å lukke JSON som ble kuttet av max_tokens."""
        # Tell opp ubalanserte brackets
        opens = raw.count('{') + raw.count('[')
        closes = raw.count('}') + raw.count(']')
        if opens <= closes:
            return raw

        # Fjern siste uferdige element (etter siste komma)
        last_comma = raw.rfind(',')
        if last_comma > 0:
            raw = raw[:last_comma]

        # Lukk alle åpne brackets
        stack = []
        for ch in raw:
            if ch in '{[':
                stack.append('}' if ch == '{' else ']')
            elif ch in '}]':
                if stack:
                    stack.pop()

        raw += ''.join(reversed(stack))
        return raw

    def _normalize(self, data: dict) -> dict:
        """Normaliser GPT-output til forventet format.
        Håndterer vanlige variasjoner i GPT-svar."""

        # Noen ganger nester GPT alt under en "song" nøkkel
        if "song" in data and isinstance(data["song"], dict):
            data = data["song"]

        # Sjekk alternative nøkler for verses
        if "verses" not in data:
            for alt in ["sections", "parts", "song_parts", "structure"]:
                if alt in data and isinstance(data[alt], list):
                    data["verses"] = data[alt]
                    break

        # Sjekk alternative nøkler for noter i hvert vers
        if "verses" in data:
            for verse in data["verses"]:
                if "notes" not in verse or not verse["notes"]:
                    for alt in ["melody", "note_sequence", "pitches", "note_data"]:
                        if alt in verse and isinstance(verse[alt], list):
                            verse["notes"] = verse[alt]
                            break

                # Hvis lyrics fins men ingen notes, lag placeholder-noter
                if ("notes" not in verse or not verse["notes"]) and "lyrics" in verse:
                    words = verse["lyrics"].replace("\n", " ").split()
                    notes_list = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
                    verse["notes"] = [
                        {"note": notes_list[i % len(notes_list)], "duration": 0.75, "lyric": w}
                        for i, w in enumerate(words)
                    ]
                    logger.warning(f"  ⚠️ Genererte {len(verse['notes'])} placeholder-noter fra lyrics")

        return data

    def _validate(self, data: dict):
        """Valider sang-strukturen."""
        required = ["title", "tempo_bpm", "verses", "chords"]
        for key in required:
            if key not in data:
                raise ValueError(f"Mangler '{key}' i sang-data")

        total_notes = 0
        total_beats = 0
        for i, verse in enumerate(data["verses"]):
            if "notes" not in verse or not verse["notes"]:
                raise ValueError(f"Vers {i} mangler noter")
            total_notes += len(verse["notes"])
            total_beats += sum(float(n.get("duration", 1.0)) for n in verse["notes"])

        if total_notes < 30:
            raise ValueError(f"For få noter: {total_notes} (minimum 30)")

        tempo = data.get("tempo_bpm", 120)
        est_duration = total_beats * 60.0 / tempo
        logger.info(f"  ✓ Validert: {total_notes} noter, {total_beats:.0f} beats, "
                     f"~{est_duration:.0f}s melodi, {len(data['chords'])} akkorder")
