import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import instructor

from .llm_client import create_chat_client, get_default_model
from . import prompts

load_dotenv()

# Pydantic Models for structured output
class Metadata(BaseModel):
    title: str
    participants: List[str] = []  # List of participants in the meeting

    # date, duration, processed_at will be handled/added by app.py


class MainPoint(BaseModel):
    title: str
    id: str
    time: Optional[str] = None  # Format: "MM:SS"


class KeyTimestamp(BaseModel):
    description: str
    time: Optional[str] = None  # Format: "MM:SS"


class DetailedSummaryItem(BaseModel):
    title: str
    content: str
    key_timestamps: List[KeyTimestamp]
    start_time: Optional[str] = None  # Format: "MM:SS"

class ActionItem(BaseModel):
    task: str = Field(..., description="Título de la tarea u objetivo.")
    description: str = Field(default="", description="Descripción breve de la tarea u objetivo.")

class StructuredResponse(BaseModel):
    metadata: Metadata
    main_points: List[MainPoint]
    detailed_summary: Optional[Dict[str, DetailedSummaryItem]] = None
    # New: tasks and objectives extracted from the transcript
    tasks_and_objectives: List[ActionItem] = []

# Summary-only schema (no tasks) for structured summary generation
class StructuredSummaryNoTasks(BaseModel):
    metadata: Metadata
    main_points: List[MainPoint]
    detailed_summary: Optional[Dict[str, DetailedSummaryItem]] = None


def dividir_texto(texto, tamano_max=6000):
    """
    Divide el texto en fragmentos sin cortar palabras.
    """
    palabras = texto.split()
    fragmentos = []
    fragmento_actual = ""
    for palabra in palabras:
        if len(fragmento_actual) + len(palabra) + 1 <= tamano_max:
            fragmento_actual += palabra + " "
        else:
            fragmentos.append(fragmento_actual.strip())
            fragmento_actual = palabra + " "
    if fragmento_actual:
        fragmentos.append(fragmento_actual.strip())
    return fragmentos


def resumir_fragmento(fragmento, client=None, provider=None):
    """
    Resume el fragmento sin contexto previo.
    """
    if client is None:
        client = create_chat_client(provider)
    
    model = get_default_model(provider)
    messages = prompts.fragment_summary_messages(fragmento)
    
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )
    resumen_texto = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            resumen_texto += chunk.choices[0].delta.content
    return resumen_texto.strip()


def resumir_fragmento_con_contexto(fragmento, contexto, client=None, provider=None):
    """
    Resume el fragmento utilizando el resumen (contexto) previo para lograr continuidad.
    """
    if client is None:
        client = create_chat_client(provider)
    
    model = get_default_model(provider)
    messages = prompts.fragment_summary_with_context_messages(fragmento, contexto)
    
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )
    resumen_texto = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            resumen_texto += chunk.choices[0].delta.content
    return resumen_texto.strip()


def resumir_fragmento_final(fragmento, contexto, client=None, provider=None):
    """
    Resume el último fragmento utilizando el resumen previo para cerrar el resumen ejecutivo de manera coherente.
    """
    if client is None:
        client = create_chat_client(provider)
    
    model = get_default_model(provider)
    messages = prompts.fragment_summary_final_messages(fragmento, contexto)
    
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )
    resumen_texto = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            resumen_texto += chunk.choices[0].delta.content
    return resumen_texto.strip()


def time_to_sec(t: str) -> int:
    """Convert 'MM:SS' string to total seconds (int). Return 0 on failure."""
    try:
        minutes, seconds = t.split(":")
        return int(minutes) * 60 + int(seconds)
    except Exception:
        return 0


def extract_segment_lines(lines: List[str], start_sec: int, end_sec: int) -> str:
    """Return joined lines whose timestamp (at beginning of line) is within [start_sec, end_sec)."""
    seg_lines = []
    for ln in lines:
        if not ln.strip():
            continue
        if ln[0] != "[":
            continue  # skip malformed
        ts_str = ln[1:6]  # [MM:SS]
        sec = time_to_sec(ts_str)
        if start_sec <= sec < end_sec:
            seg_lines.append(ln)
    return "\n".join(seg_lines)


# The 'transcripcion' parameter will be the filename of the transcript *with inline timestamps*
def gpt(transcripcion_filename: str, participants: List[str], provider=None):
    # Create clients for structured and regular chat completions
    chat_client = create_chat_client(provider)
    structured_client = instructor.patch(create_chat_client(provider))
    model = get_default_model(provider)
    # Read the content of the transcript file (which now includes inline timestamps)
    try:
        with open(transcripcion_filename, "r", encoding="utf-8") as f:
            transcription_text_with_timestamps = f.read()
    except FileNotFoundError:
        print(f"Error: Transcript file {transcripcion_filename} not found.")
        # Create an empty resumen.json or handle error as appropriate
        # For now, let's create a default empty structure if file is not found.
        default_response = StructuredResponse(
            metadata=Metadata(title="Error: Transcript not found"),
            main_points=[],
            detailed_summary={}
        )
        with open("resumen.json", "w", encoding="utf-8") as f_err:
            f_err.write(default_response.model_dump_json(indent=2, exclude_none=True))
        print("Created empty/error resumen.json due to missing transcript file.")
        # Also, the rest of the function (chunking for resumen2.json) will fail.
        # This part needs rethinking if transcripcion_filename is missing.
        # For now, we just return as resumen.json is the primary goal.
        return

    # === Procesamiento en fragmentos para no exceder límites de tokens ===
    MAX_CHARS_PER_CHUNK = 8000
    transcript_chunks = dividir_texto(transcription_text_with_timestamps, tamano_max=MAX_CHARS_PER_CHUNK)
    print(f"[GPT-struct] Transcripción dividida en {len(transcript_chunks)} fragmentos para resumen estructurado.")

    # Listas globales para acumular todos los datos necesarios
    global_main_points: List[MainPoint] = []
    global_detailed_summary: Dict[str, DetailedSummaryItem] = {}
    metadata_final: Optional[Metadata] = None

    dynamic_length_prompt = (
        f"La duración total detectada de la reunión es de aproximadamente {time_to_sec(transcription_text_with_timestamps[-5:]) // 60} "
        f"minutos (timestamp final: {transcription_text_with_timestamps[-5:]}). Debes generar **al menos {max(3, time_to_sec(transcription_text_with_timestamps[-5:]) // 600 + 1)} puntos "
        f"principales** en 'main_points', distribuidos a lo largo de toda la línea de tiempo, de modo que el "
        f"último 'main_points.time' no esté a más de 2 minutos de {transcription_text_with_timestamps[-5:]}. Asegúrate de que cada punto "
        f"principal tenga su correspondiente entrada detallada en 'detailed_summary'."
    )
    dynamic_length_prompt_local = dynamic_length_prompt  # alias to ensure closure visibility

    # Get system prompt for structured summary
    system_prompt_struct = prompts.structured_summary_system_prompt(participants)
    system_prompt_local = system_prompt_struct  # para cierre

    def repair_json_structure(jd: dict):
        """Ensure required fields present and correct types for validation"""
        # Ensure metadata exists
        jd.setdefault("metadata", {}).setdefault("title", "(Sin título)")
        # main_points list
        if not isinstance(jd.get("main_points", []), list):
            jd["main_points"] = []
        
        # Ensure tasks_and_objectives is list of {task, description}
        tao = jd.get("tasks_and_objectives")
        if tao is None:
            jd["tasks_and_objectives"] = []
        elif not isinstance(tao, list):
            jd["tasks_and_objectives"] = []
        else:
            fixed_tao = []
            for it in tao:
                if isinstance(it, dict):
                    raw_task = str(it.get("task", "")).strip()
                    raw_desc = str(it.get("description", "")).strip()
                    # Fallback: derive task from description when missing
                    if not raw_task and raw_desc:
                        raw_task = (raw_desc[:80] + ("…" if len(raw_desc) > 80 else ""))
                    fixed_tao.append({
                        "task": raw_task,
                        "description": raw_desc
                    })
            jd["tasks_and_objectives"] = [it for it in fixed_tao if it.get("task")]
        
        # detailed_summary conversion
        ds = jd.get("detailed_summary")
        if ds is None:
            jd["detailed_summary"] = {}
            ds = jd["detailed_summary"]
        if isinstance(ds, list):
            new_ds = {}
            for idx, item in enumerate(ds):
                if isinstance(item, dict):
                    item_id = item.get("id", f"item_{idx}")
                    new_ds[item_id] = item
            jd["detailed_summary"] = new_ds
            ds = jd["detailed_summary"]
        # Now ds is dict
        for item_id, item in ds.items():
            if not isinstance(item, dict):
                ds[item_id] = {"title": "", "content": str(item), "key_timestamps": []}
                item = ds[item_id]
            item.setdefault("title", "")
            item.setdefault("content", "")
            kts = item.get("key_timestamps", [])
            if isinstance(kts, list):
                fixed_kts = []
                for kt in kts:
                    if isinstance(kt, dict):
                        fixed_kts.append({"description": kt.get("description", kt.get("time", "")), "time": kt.get("time")})
                    else:  # string timestamp
                        fixed_kts.append({"description": str(kt), "time": None})
                item["key_timestamps"] = fixed_kts
            else:
                item["key_timestamps"] = []
        return jd

    def call_gpt_structured(chunk_text: str, first_chunk: bool, previous_main_points: list):
        """Llama al modelo para un fragmento y devuelve StructuredSummaryNoTasks."""
        if first_chunk:
            extra_system = dynamic_length_prompt_local
        else:
            # Provide context of what was already covered to avoid repetition
            extra_system = prompts.followup_structured_prompt_with_context(previous_main_points)

        user_prompt = prompts.structured_summary_user_prompt(chunk_text)
        try:
            resp = structured_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt_local},
                    {"role": "system", "content": extra_system},
                    {"role": "user", "content": user_prompt}
                ],
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "format_meeting_summary",
                        "description": "Formats the meeting transcript into a structured summary.",
                        "parameters": StructuredSummaryNoTasks.model_json_schema()
                    }
                }],
                tool_choice={"type": "function", "function": {"name": "format_meeting_summary"}}
            )
            tool_call = resp.choices[0].message.tool_calls[0]
            import json as _json
            json_dict = _json.loads(tool_call.function.arguments)
            json_dict = repair_json_structure(json_dict)
            return StructuredSummaryNoTasks.model_validate(json_dict)
        except Exception as ce:
            print(f"[GPT-struct] Error obteniendo resumen de fragmento: {ce}")
            return None

    # Helpers for deduplication and stable IDs
    def _normalize_text(s: str) -> str:
        try:
            s = s or ""
            s = s.lower()
            s = re.sub(r"\s+", " ", s).strip()
            s = re.sub(r"[\.,;:!¡¿\?\-\(\)\[\]\{\}\"'`]+", "", s)
            return s
        except Exception:
            return str(s or "").lower().strip()

    def _time_to_seconds(value: Optional[str]) -> int:
        if not value:
            return 10**9
        try:
            match = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", value)
            if not match:
                return 10**9
            minutes, seconds = match.groups()
            return int(minutes) * 60 + int(seconds)
        except Exception:
            return 10**9

    def _strip_bullet_prefix(text: str) -> str:
        text = (text or "").lstrip()
        if text.startswith("-") or text.startswith("*"):
            text = text[1:]
        return text.strip()

    def _merge_content(base: str, new: str) -> str:
        base_lines = [ln for ln in (base or "").splitlines() if ln.strip()]
        seen = {_normalize_text(_strip_bullet_prefix(ln)) for ln in base_lines}
        merged = list(base_lines)
        for ln in (new or "").splitlines():
            if not ln.strip():
                continue
            norm = _normalize_text(_strip_bullet_prefix(ln))
            if norm in seen:
                continue
            merged.append(ln)
            seen.add(norm)
        if merged:
            return "\n".join(merged)
        new_lines = [ln for ln in (new or "").splitlines() if ln.strip()]
        return "\n".join(new_lines)

    def _merge_detail_items(
        target: Optional[DetailedSummaryItem],
        source: Optional[DetailedSummaryItem],
    ) -> Optional[DetailedSummaryItem]:
        if target is None:
            return source
        if source is None:
            return target

        target.content = _merge_content(target.content or "", source.content or "")

        if source.start_time:
            if not target.start_time or _time_to_seconds(source.start_time) < _time_to_seconds(target.start_time):
                target.start_time = source.start_time

        target.key_timestamps = list(target.key_timestamps or [])
        existing_ts = {
            ((kt.time or "").strip(), _normalize_text(kt.description or ""))
            for kt in target.key_timestamps
        }
        for ts in source.key_timestamps or []:
            key = ((ts.time or "").strip(), _normalize_text(ts.description or ""))
            if key in existing_ts:
                continue
            target.key_timestamps.append(ts)
            existing_ts.add(key)

        return target

    used_ids: set[str] = set()
    seen_main_point_keys: set[str] = set()

    # Procesar cada fragmento
    for idx, ch in enumerate(transcript_chunks):
        print(f"[GPT-struct] Procesando fragmento {idx+1}/{len(transcript_chunks)}…")
        
        # Prepare context: pass current main points as context for next chunk
        previous_points_for_context = [{"title": mp.title, "id": mp.id} for mp in global_main_points]
        
        partial_res = call_gpt_structured(ch, first_chunk=(idx == 0), previous_main_points=previous_points_for_context)
        if partial_res is None:
            continue
        if idx == 0:
            metadata_final = partial_res.metadata
        # Merge main points with deduplication and stable unique IDs
        # Refresh used_ids from what we already have
        used_ids.update([mp.id for mp in global_main_points])
        used_ids.update(list(global_detailed_summary.keys()))

        # Build a filtered list of main points and a remapped details dict
        filtered_main_points: List[MainPoint] = []
        remapped_details: Dict[str, DetailedSummaryItem] = {}

        # Work on a copy of details for safety
        incoming_details: Dict[str, DetailedSummaryItem] = {}
        try:
            if partial_res.detailed_summary:
                incoming_details = dict(partial_res.detailed_summary)
        except Exception:
            incoming_details = {}

        def _ensure_unique_id(base: str) -> str:
            base = base or "item"
            candidate = base
            suffix = 1
            while candidate in used_ids:
                candidate = f"{base}_{suffix}"
                suffix += 1
            used_ids.add(candidate)
            return candidate

        for mp in partial_res.main_points:
            # Generate a normalized key to detect duplicates across chunks: title + time
            norm_title = _normalize_text(mp.title)
            norm_time = (mp.time or "").strip()
            mp_key = f"{norm_title}|{norm_time}"
            if mp_key in seen_main_point_keys:
                # Skip duplicated main point
                continue

            # Ensure ID uniqueness; if changed, remap its detail as well
            original_id = mp.id
            if not original_id or original_id in used_ids:
                new_id = _ensure_unique_id(original_id or f"pt_{len(global_main_points)+len(filtered_main_points)+1}")
                mp.id = new_id
            else:
                used_ids.add(original_id)

            # Add main point
            filtered_main_points.append(mp)
            seen_main_point_keys.add(mp_key)

            # Attach its detail if provided
            try:
                detail = incoming_details.get(original_id if original_id in incoming_details else mp.id)
                if detail is not None:
                    remapped_details[mp.id] = detail
            except Exception:
                pass

        # Apply merges
        if filtered_main_points:
            global_main_points.extend(filtered_main_points)
        if remapped_details:
            # Ensure no key collisions remain
            for did, ditem in remapped_details.items():
                if did in global_detailed_summary:
                    # Should not happen due to used_ids, but guard anyway
                    new_did = _ensure_unique_id(did)
                    global_detailed_summary[new_did] = ditem
                    # Also fix the corresponding main point ID if needed
                    for mp in global_main_points:
                        if mp.id == did:
                            mp.id = new_did
                            break
                else:
                    global_detailed_summary[did] = ditem
        print(f"[GPT-struct] Fragmento {idx+1} listo – Total puntos: {len(global_main_points)}")

    def _dedupe_main_points_and_details():
        nonlocal global_main_points
        signature_to_mp: Dict[str, MainPoint] = {}
        deduped_main_points: List[MainPoint] = []

        for mp in global_main_points:
            signature = _normalize_text(mp.title)
            if not signature:
                signature = (mp.id or "").lower()

            existing_mp = signature_to_mp.get(signature)
            detail = global_detailed_summary.get(mp.id)

            if existing_mp:
                if mp.time:
                    if (not existing_mp.time) or (_time_to_seconds(mp.time) < _time_to_seconds(existing_mp.time)):
                        existing_mp.time = mp.time

                merged_detail = _merge_detail_items(global_detailed_summary.get(existing_mp.id), detail)
                if merged_detail is not None:
                    global_detailed_summary[existing_mp.id] = merged_detail

                if detail and mp.id != existing_mp.id:
                    global_detailed_summary.pop(mp.id, None)
                continue

            signature_to_mp[signature] = mp
            deduped_main_points.append(mp)

        valid_ids = {mp.id for mp in deduped_main_points}
        for did in list(global_detailed_summary.keys()):
            if did not in valid_ids:
                global_detailed_summary.pop(did, None)

        global_main_points = deduped_main_points

    _dedupe_main_points_and_details()

    # After processing all chunks, deduplicate repeated bullet content across detailed_summary items
    def _dedupe_detailed_content_across_items():
        try:
            seen_bullets_global: set[str] = set()
            for mp in global_main_points:
                item = global_detailed_summary.get(mp.id)
                if not item or not getattr(item, 'content', None):
                    continue
                raw = item.content or ""
                lines = [ln for ln in raw.split("\n") if ln.strip()]
                new_lines: list[str] = []
                local_seen: set[str] = set()
                for ln in lines:
                    s = ln.strip()
                    core = _strip_bullet_prefix(s)
                    norm = _normalize_text(core)
                    if norm in seen_bullets_global or norm in local_seen:
                        continue
                    seen_bullets_global.add(norm)
                    local_seen.add(norm)
                    new_lines.append(ln)
                if not new_lines and lines:
                    # Keep at least one line to avoid empty content
                    new_lines = [lines[0]]
                item.content = "\n".join(new_lines)
        except Exception:
            pass

    _dedupe_detailed_content_across_items()

    if not global_main_points:
        raise Exception("No se generaron main_points en ninguno de los fragmentos.")

    # Ensure participants are present in metadata
    try:
        if metadata_final is None:
            metadata_final = Metadata(title="Acta de Reunión")
        # Inject participants if missing or empty
        if not getattr(metadata_final, 'participants', None):
            if isinstance(participants, list) and participants:
                metadata_final.participants = participants
    except Exception:
        pass

    final_structured_response = {
        "metadata": metadata_final.model_dump(exclude_none=True) if metadata_final else {"title": "Acta de Reunión"},
        "main_points": [mp.model_dump(exclude_none=True) for mp in global_main_points],
        "detailed_summary": {
            k: v.model_dump(exclude_none=True) for k, v in (global_detailed_summary or {}).items()
        }
    }

    with open("resumen.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(final_structured_response, ensure_ascii=False, indent=2))
    print("Resumen estructurado completo guardado en 'resumen.json'.")

    # Saltamos la lógica antigua tras esta sección (desde "if final_structured_response.main_points:"... )
    return  # Fin de la función gpt una vez guardado resumen.json


def extract_names_from_text(transcript_text: str, provider=None) -> list[str]:
    print("[GPT] Iniciando extracción de nombres...")
    
    client = create_chat_client(provider)
    model = get_default_model(provider)
    messages = prompts.participant_extraction_messages(transcript_text)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        parsed_json = json.loads(content)
        participant_names = parsed_json.get("participants", [])
        cleaned_names = [str(name).strip() for name in participant_names if isinstance(name, str) and name.strip()]
        print(f"[GPT] Nombres extraídos: {cleaned_names}")
        return cleaned_names
    except Exception as e:
        print(f"Error al extraer nombres con GPT: {e}")
        return []


# Pydantic models for one-shot minutes generation
class MinutesMetadata(BaseModel):
    title: str
    participants: List[str] = []


class MinutesMainPoint(BaseModel):
    id: str
    title: str
    time: Optional[str] = None  # Format: "MM:SS"


class MinutesDetailItem(BaseModel):
    title: str
    content: str = Field(default="", description="Cadena unica con viñetas separadas por \\n")


class MinutesActionItem(BaseModel):
    task: str = Field(..., description="Título de la tarea u objetivo.")
    description: str = Field(default="", description="Descripción breve de la tarea u objetivo.")


class MinutesResponse(BaseModel):
    objective: Optional[str] = ""
    metadata: MinutesMetadata
    main_points: List[MinutesMainPoint]
    details: Optional[Dict[str, MinutesDetailItem]] = None
    tasks_and_objectives: List[MinutesActionItem] = []


def generate_minutes(transcript_text: str, participants: List[str], provider=None) -> dict:
    """
    One-shot minutes generation: generates detailed minutes with main points, details, and tasks.
    Returns a dict with the minutes structure, does NOT use chunking.
    """
    print("[GPT-minutes] Iniciando generación de acta detallada (one-shot)...")
    
    client = create_chat_client(provider)
    model = get_default_model(provider)

    participant_aliases: List[str] = []
    for name in (participants or []):
        try:
            if not name:
                continue
            cleaned = str(name).strip()
            if not cleaned:
                continue
            participant_aliases.append(cleaned)
            parts = [p for p in re.split(r"\s+", cleaned) if len(p) > 2]
            participant_aliases.extend(parts)
        except Exception:
            continue

    def _sanitize_text(value: Optional[str]) -> str:
        if not value:
            return ""
        sanitized = value
        for alias in participant_aliases:
            if not alias:
                continue
            pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
            sanitized = pattern.sub("un participante", sanitized)
        sanitized = re.sub(r"(un participante)(\s+un participante)+", r"\1", sanitized, flags=re.IGNORECASE)
        return sanitized

    def _limit_bullets(value: Optional[str], max_bullets: int = 3) -> str:
        if not value:
            return ""
        lines = [ln.rstrip() for ln in value.splitlines() if ln.strip()]
        bullets: List[str] = []
        current: List[str] = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("-"):
                if current:
                    bullets.append("\n".join(current))
                current = [stripped]
            else:
                if current:
                    current.append(stripped)
                else:
                    current = [f"- {stripped}"]
        if current:
            bullets.append("\n".join(current))
        if not bullets:
            return value
        trimmed = bullets[:max_bullets]
        cleaned = []
        for block in trimmed:
            sentences = block.split("\n")
            head = sentences[0].rstrip()
            rest = sentences[1:2]  # allow at most one sub bullet line
            cleaned.append("\n".join([head, *rest]).strip())
        return "\n".join(cleaned)
    
    system_prompt = prompts.minutes_generation_system_prompt(participants)
    user_prompt = prompts.minutes_generation_user_prompt(transcript_text)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        parsed_json = json.loads(content)
        
        # Repair details structure if it's a list instead of dict
        try:
            det = parsed_json.get("details")
            if isinstance(det, list):
                new_det = {}
                for idx, item in enumerate(det):
                    if isinstance(item, dict):
                        key = item.get("id") or f"detail_{idx}"
                        new_det[str(key)] = {
                            "title": item.get("title", ""),
                            "content": item.get("content", "")
                        }
                parsed_json["details"] = new_det
        except Exception:
            pass
        
        # Validate and clean the response
        minutes_data = MinutesResponse.model_validate(parsed_json)

        # Fallback: ensure details exist and are sufficiently detailed per main point
        try:
            lines = transcript_text.splitlines()

            def _last_ts_seconds(ls: List[str]) -> int:
                for ln in reversed(ls):
                    m = re.match(r'^\[(\d{2}):(\d{2})\]', ln.strip())
                    if m:
                        return int(m.group(1)) * 60 + int(m.group(2))
                return 10**9

            last_sec = _last_ts_seconds(lines)

            existing_details: Dict[str, Dict[str, str]] = {}
            if isinstance(minutes_data.details, dict):
                # Normalize to simple dict[str, dict]
                for k, v in minutes_data.details.items():
                    if isinstance(v, dict):
                        existing_details[str(k)] = {
                            "title": str(v.get("title", "")),
                            "content": str(v.get("content", "")),
                        }
                    else:
                        # Pydantic model MinutesDetailItem
                        try:
                            existing_details[str(k)] = {
                                "title": getattr(v, "title", ""),
                                "content": getattr(v, "content", ""),
                            }
                        except Exception:
                            pass

            # Build/fill details
            for idx, mp in enumerate(minutes_data.main_points or []):
                mp_id = mp.id
                mp_title = mp.title or ""
                start_sec = time_to_sec(mp.time or "00:00")
                next_sec = last_sec
                if idx + 1 < len(minutes_data.main_points):
                    next_sec = max(start_sec + 1, time_to_sec(minutes_data.main_points[idx + 1].time or "00:00"))

                need_detail = False
                curr = existing_details.get(mp_id)
                if not curr:
                    need_detail = True
                else:
                    content_len = len((curr.get("content") or "").strip())
                    if content_len < 80:  # too short
                        need_detail = True

                if need_detail:
                    segment_text = extract_segment_lines(lines, start_sec, next_sec)
                    # If empty segment, fallback to a small window after start
                    if not segment_text.strip():
                        segment_text = "\n".join(lines[:300])
                    try:
                        detail_msgs = prompts.minutes_details_messages(mp_title, segment_text)
                        detail_resp = client.chat.completions.create(
                            model=model,
                            messages=detail_msgs,
                        )
                        detail_content = (detail_resp.choices[0].message.content or "").strip()
                        detail_content = _limit_bullets(detail_content, max_bullets=3)
                        # Basic guard to ensure bullet formatting
                        if "- " not in detail_content:
                            detail_content = "- " + detail_content.replace("\n", "\n- ")
                        existing_details[mp_id] = {
                            "title": mp_title,
                            "content": detail_content,
                        }
                    except Exception:
                        # Leave as is if generation fails
                        pass

            # Build final result dict
            result = minutes_data.model_dump(exclude_none=True)
            if existing_details:
                for entry in existing_details.values():
                    entry["title"] = _sanitize_text(entry.get("title"))
                    entry["content"] = _limit_bullets(_sanitize_text(entry.get("content")), max_bullets=3)
                result["details"] = existing_details

            if result.get("objective"):
                result["objective"] = _sanitize_text(result.get("objective"))

            for item in result.get("tasks_and_objectives", []):
                item["task"] = _sanitize_text(item.get("task"))
                item["description"] = _sanitize_text(item.get("description"))

            details_count = len(existing_details)
            print(f"[GPT-minutes] Generado: {len(minutes_data.main_points)} puntos principales, {details_count} detalles, {len(minutes_data.tasks_and_objectives)} tareas/objetivos")

            return result
        except Exception:
            # If fallback fails, return the validated output
            result = minutes_data.model_dump(exclude_none=True)
            if result.get("objective"):
                result["objective"] = _sanitize_text(result.get("objective"))

            if result.get("details"):
                for entry in result["details"].values():
                    entry["title"] = _sanitize_text(entry.get("title"))
                    entry["content"] = _limit_bullets(_sanitize_text(entry.get("content")), max_bullets=3)

            if result.get("tasks_and_objectives"):
                for item in result["tasks_and_objectives"]:
                    item["task"] = _sanitize_text(item.get("task"))
                    item["description"] = _sanitize_text(item.get("description"))

            details_count = len(result.get("details") or {})
            print(f"[GPT-minutes] Generado: {len(minutes_data.main_points)} puntos principales, {details_count} detalles, {len(minutes_data.tasks_and_objectives)} tareas/objetivos")
            return result
        
    except Exception as e:
        print(f"[GPT-minutes] Error generando acta: {e}")
        import traceback
        traceback.print_exc()
        # Return a minimal valid structure on error
        return {
            "objective": "",
            "metadata": {
                "title": "Acta de Reunión",
                "participants": participants
            },
            "main_points": [],
            "details": {},
            "tasks_and_objectives": []
        }