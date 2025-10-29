import os
import json
from datetime import datetime
from typing import Any

from BACKEND.llamada_whisper import transcribe_audio_structured
from BACKEND.llamada_gpt import gpt, gpt_minutes_one_shot


def _build_transcript_with_timestamps(structured_json_path: str) -> str:
    """Given the path to a structured transcription JSON, build a [MM:SS] text."""
    texto_con_timestamps = ""
    with open(structured_json_path, 'r', encoding='utf-8') as f:
        transc_data = json.load(f)
        for seg in transc_data.get('segments', []):
            start = seg.get('start', 0)
            texto_con_timestamps += f"[{int(start//60):02d}:{int(start%60):02d}] {seg.get('text','').strip()}\n"
    return texto_con_timestamps


def _cargar_json(path: str, estructura_base: dict | None = None) -> dict:
    if estructura_base is None:
        estructura_base = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return estructura_base


def _extract_participant_names(reunion_doc: dict[str, Any]) -> list[str]:
    # Prefer new 'participants' field with objects
    names: list[str] = []
    try:
        if isinstance(reunion_doc.get('participants'), list):
            names = [p.get('name', '').strip() for p in reunion_doc['participants'] if isinstance(p, dict) and p.get('name')]
    except Exception:
        names = []
    if not names:
        old = reunion_doc.get('participantes', [])
        if isinstance(old, list):
            names = [str(n).strip() for n in old if str(n).strip()]
    return names


def process_audio_and_generate_summary(db, audio_file_path: str, reunion_id: str, uploads_folder: str, provider=None) -> None:
    """Full pipeline: transcribe, build transcript text, run GPT, update DB."""
    # 1. Fetch meeting doc and participants
    reunion_doc = db.reuniones.find_one({"id": reunion_id})
    if not reunion_doc:
        raise RuntimeError(f"No se encontró la reunión con ID {reunion_id}")

    participants = _extract_participant_names(reunion_doc)

    # 2. Transcribe audio into structured JSON
    ruta_transcripcion = transcribe_audio_structured(audio_file_path)

    # 3. Build transcript with timestamps
    texto_con_timestamps = _build_transcript_with_timestamps(ruta_transcripcion)

    # 4. Save temp transcript for GPT
    temp_gpt_input_file = os.path.join(uploads_folder, f"transcript_{reunion_id}.txt")
    with open(temp_gpt_input_file, 'w', encoding='utf-8') as f:
        f.write(texto_con_timestamps)

    # 5. Run GPT (chunked) to produce resumen.json for summary tab
    gpt(temp_gpt_input_file, participants=participants, provider=provider)

    # 5b. Run GPT (one-shot) to produce resumen_minutes.json for minutes (acta)
    gpt_minutes_one_shot(temp_gpt_input_file, participants=participants, provider=provider)

    # 6. Load both summaries and update DB
    acta_data = _cargar_json('resumen.json', {})
    minutes_data = _cargar_json('resumen_minutes.json', {})
    db.reuniones.update_one(
        {"id": reunion_id},
        {"$set": {
            "transcripcion": texto_con_timestamps,
            "resumen": json.dumps(acta_data, ensure_ascii=False),
            "resumen_minutes": json.dumps(minutes_data, ensure_ascii=False)
        }}
    )

    # 7. Cleanup temp files
    try:
        if os.path.exists('resumen.json'):
            os.remove('resumen.json')
        if os.path.exists('resumen_minutes.json'):
            os.remove('resumen_minutes.json')
        if os.path.exists(temp_gpt_input_file):
            os.remove(temp_gpt_input_file)
    except Exception:
        pass


