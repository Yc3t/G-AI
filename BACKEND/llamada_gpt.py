import os
import json
import re
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from .llm_client import create_chat_client, get_default_model
from . import prompts

load_dotenv()


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


# Minutes models
class MinutesMetadata(BaseModel):
    title: str
    participants: List[str] = []


class MinutesMainPoint(BaseModel):
    id: str
    title: str
    time: Optional[str] = None


class MinutesDetailItem(BaseModel):
    title: str = ""
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
            rest = sentences[1:2]
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
        
        minutes_data = MinutesResponse.model_validate(parsed_json)

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
                for k, v in minutes_data.details.items():
                    if isinstance(v, dict):
                        existing_details[str(k)] = {
                            "title": str(v.get("title", "")),
                            "content": str(v.get("content", "")),
                        }
                    else:
                        try:
                            existing_details[str(k)] = {
                                "title": getattr(v, "title", ""),
                                "content": getattr(v, "content", ""),
                            }
                        except Exception:
                            pass

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
                    if content_len < 80:
                        need_detail = True

                if need_detail:
                    segment_text = extract_segment_lines(lines, start_sec, next_sec)
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
                        if "- " not in detail_content:
                            detail_content = "- " + detail_content.replace("\n", "\n- ")
                        existing_details[mp_id] = {
                            "title": mp_title,
                            "content": detail_content,
                        }
                    except Exception:
                        pass

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