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
    global_tasks: List[ActionItem] = []
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
        """Llama al modelo para un fragmento y devuelve StructuredResponse."""
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
                        "parameters": StructuredResponse.model_json_schema()
                    }
                }],
                tool_choice={"type": "function", "function": {"name": "format_meeting_summary"}}
            )
            tool_call = resp.choices[0].message.tool_calls[0]
            import json as _json
            json_dict = _json.loads(tool_call.function.arguments)
            json_dict = repair_json_structure(json_dict)
            return StructuredResponse.model_validate(json_dict)
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
        # Merge tasks and objectives
        try:
            if isinstance(partial_res.tasks_and_objectives, list) and partial_res.tasks_and_objectives:
                print(f"[DEBUG llamada_gpt.py] Fragment {idx+1} generated {len(partial_res.tasks_and_objectives)} tasks/objectives")
                global_tasks.extend(partial_res.tasks_and_objectives)
            else:
                print(f"[DEBUG llamada_gpt.py] Fragment {idx+1} generated NO tasks/objectives")
        except Exception as e:
            print(f"[DEBUG llamada_gpt.py] Exception merging tasks: {e}")
            pass
        print(f"[GPT-struct] Fragmento {idx+1} listo – Total puntos: {len(global_main_points)}, Total tasks: {len(global_tasks)}")

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

    final_structured_response = StructuredResponse(
        metadata=metadata_final,
        main_points=global_main_points,
        detailed_summary=global_detailed_summary,
        tasks_and_objectives=global_tasks
    )

    print(f"[DEBUG llamada_gpt.py] Final response has {len(global_tasks)} tasks/objectives")

    with open("resumen.json", "w", encoding="utf-8") as f:
        f.write(final_structured_response.model_dump_json(indent=2, exclude_none=True))
    print("Resumen estructurado completo guardado en 'resumen.json'.")

    # Saltamos la lógica antigua tras esta sección (desde "if final_structured_response.main_points:"... )
    return  # Fin de la función gpt una vez guardado resumen.json


def gpt_minutes_one_shot(transcripcion_filename: str, participants: List[str], provider=None):
    """Generate a structured minutes JSON in one shot from the full transcript.

    Writes 'resumen_minutes.json' with the same schema as StructuredResponse.
    """
    structured_client = instructor.patch(create_chat_client(provider))
    model = get_default_model(provider)

    try:
        with open(transcripcion_filename, "r", encoding="utf-8") as f:
            full_text = f.read()
    except FileNotFoundError:
        print(f"[GPT-minutes] Transcript file {transcripcion_filename} not found.")
        empty = StructuredResponse(
            metadata=Metadata(title="Acta de Reunión"),
            main_points=[],
            detailed_summary={},
            tasks_and_objectives=[]
        )
        with open("resumen_minutes.json", "w", encoding="utf-8") as fw:
            fw.write(empty.model_dump_json(indent=2, exclude_none=True))
        return

    # Compute last timestamp and estimated total minutes
    def _last_mmss_and_minutes(text: str) -> tuple[str, int]:
        mmss = "00:00"
        seconds = 0
        try:
            for m in re.finditer(r"\[(\d{2}):(\d{2})\]", text):
                mm = int(m.group(1)); ss = int(m.group(2))
                seconds = mm * 60 + ss
                mmss = f"{mm:02d}:{ss:02d}"
        except Exception:
            pass
        return mmss, max(0, seconds // 60)

    final_ts, total_min = _last_mmss_and_minutes(full_text)
    min_points = max(4, total_min // 5 + 1)

    # Build prompts
    system_main = prompts.structured_summary_system_prompt(participants)
    system_extra = prompts.structured_summary_dynamic_prompt(final_ts, total_min, min_points)
    user_prompt = prompts.structured_summary_user_prompt_full(full_text)

    # Call LLM with tool schema to enforce JSON format
    try:
        resp = structured_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_main},
                {"role": "system", "content": system_extra},
                {"role": "user", "content": user_prompt},
            ],
            tools=[{
                "type": "function",
                "function": {
                    "name": "format_meeting_summary",
                    "description": "Formats the meeting transcript into a structured summary.",
                    "parameters": StructuredResponse.model_json_schema()
                }
            }],
            tool_choice={"type": "function", "function": {"name": "format_meeting_summary"}}
        )

        tool_call = resp.choices[0].message.tool_calls[0]
        import json as _json
        json_dict = _json.loads(tool_call.function.arguments)

        # Minimal repair to ensure expected shapes
        if not isinstance(json_dict.get("metadata"), dict):
            json_dict["metadata"] = {"title": "Acta de Reunión", "participants": participants or []}
        if not isinstance(json_dict.get("main_points"), list):
            json_dict["main_points"] = []
        if json_dict.get("detailed_summary") is None:
            json_dict["detailed_summary"] = {}
        if not isinstance(json_dict.get("tasks_and_objectives"), list):
            json_dict["tasks_and_objectives"] = []

        validated = StructuredResponse.model_validate(json_dict)
    except Exception as e:
        print(f"[GPT-minutes] Error generating one-shot minutes: {e}")
        validated = StructuredResponse(
            metadata=Metadata(title="Acta de Reunión"),
            main_points=[],
            detailed_summary={},
            tasks_and_objectives=[]
        )

    with open("resumen_minutes.json", "w", encoding="utf-8") as f:
        f.write(validated.model_dump_json(indent=2, exclude_none=True))
    print("[GPT-minutes] Acta (one-shot) guardada en 'resumen_minutes.json'.")


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
