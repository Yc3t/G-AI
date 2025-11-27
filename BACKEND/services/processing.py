import os
import json
from datetime import datetime
from typing import Any

from BACKEND.llamada_whisper import transcribe_audio_structured
from BACKEND.llamada_gpt import generate_minutes
from BACKEND.services.minutes import compose_minutes


def _build_transcript_with_timestamps(structured_json_path: str) -> str:
    """Given the path to a structured transcription JSON, build a [MM:SS] text."""
    texto_con_timestamps = ""
    with open(structured_json_path, 'r', encoding='utf-8') as f:
        transc_data = json.load(f)
        for seg in transc_data.get('segments', []):
            start = seg.get('start', 0)
            texto_con_timestamps += f"[{int(start//60):02d}:{int(start%60):02d}] {seg.get('text','').strip()}\n"
    return texto_con_timestamps


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
    """Full pipeline: transcribe, build transcript text, run GPT for minutes, update DB."""
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

    # 5. Generate minutes (one-shot, no chunking)
    print("[Processing] Generando acta (one-shot)...")
    minutes_raw = generate_minutes(texto_con_timestamps, participants=participants, provider=provider)
    meeting_context = dict(reunion_doc or {})
    meeting_context['transcripcion'] = texto_con_timestamps
    normalized_minutes = compose_minutes(meeting_context, minutes_raw)

    db.reuniones.update_one(
        {"id": reunion_id},
        {"$set": {
            "transcripcion": texto_con_timestamps,
            "minutes": json.dumps(normalized_minutes, ensure_ascii=False)
        }}
    )

    # 6. Cleanup temp files
    try:
        if os.path.exists(temp_gpt_input_file):
            os.remove(temp_gpt_input_file)
    except Exception:
        pass


