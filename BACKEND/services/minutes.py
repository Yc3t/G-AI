import re
from datetime import datetime
from typing import Any, Dict


def _last_timestamp_seconds(transcript_text: str) -> int:
    try:
        lines = [ln.strip() for ln in (transcript_text or '').split('\n') if ln.strip()]
        for ln in reversed(lines):
            m = re.match(r'\[(\d{2}):(\d{2})\]', ln)
            if m:
                return int(m.group(1)) * 60 + int(m.group(2))
    except Exception:
        pass
    return 0


def compose_minutes(meeting_doc: Dict[str, Any], summary_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Compose a normalized minutes object from meeting doc and structured summary.

    meeting_doc: DB document with keys like id, titulo, fecha_de_subida, transcripcion, participants/participantes
    summary_obj: dict with keys metadata, main_points, detailed_summary, action_items
    """
    minutes: Dict[str, Any] = {
        "metadata": {},
        "participants": [],
        "key_points": [],
        "details": {},
        "custom_sections": [],
        "tasks_and_objectives": []
    }

    # metadata
    title = None
    try:
        md = summary_obj.get('metadata') if isinstance(summary_obj, dict) else None
        if isinstance(md, dict):
            title = md.get('title')
    except Exception:
        title = None
    if not title:
        title = meeting_doc.get('titulo') or 'Acta de Reunión'
    minutes['metadata']['title'] = title

    fecha = meeting_doc.get('fecha_de_subida')
    try:
        if isinstance(fecha, datetime):
            minutes['metadata']['date'] = fecha.isoformat()
        else:
            minutes['metadata']['date'] = str(fecha) if fecha else None
    except Exception:
        minutes['metadata']['date'] = None

    minutes['metadata']['meeting_id'] = meeting_doc.get('id')

    transcript_text = meeting_doc.get('transcripcion') or ''
    if isinstance(transcript_text, str) and transcript_text.strip():
        minutes['metadata']['duration_seconds'] = _last_timestamp_seconds(transcript_text)

    # participants
    if isinstance(meeting_doc.get('participants'), list):
        for p in meeting_doc.get('participants'):
            if isinstance(p, dict) and p.get('name'):
                entry = {"name": p['name']}
                if p.get('email'):
                    entry['email'] = p['email']
                minutes['participants'].append(entry)
    elif isinstance(meeting_doc.get('participantes'), list):
        for n in meeting_doc.get('participantes'):
            n_str = str(n).strip()
            if n_str:
                minutes['participants'].append({"name": n_str})

    # fallback: if still empty, pull from summary metadata participants
    try:
        if not minutes['participants']:
            md = summary_obj.get('metadata') if isinstance(summary_obj, dict) else None
            if isinstance(md, dict):
                md_participants = md.get('participants')
                if isinstance(md_participants, list):
                    for n in md_participants:
                        n_str = str(n).strip()
                        if n_str:
                            minutes['participants'].append({"name": n_str})
    except Exception:
        pass

    # key points
    mps = summary_obj.get('main_points') if isinstance(summary_obj, dict) else None
    if isinstance(mps, list):
        for mp in mps:
            if not isinstance(mp, dict):
                continue
            minutes['key_points'].append({
                'id': mp.get('id'),
                'title': mp.get('title'),
                'time': mp.get('time')
            })

    # details
    det = summary_obj.get('detailed_summary') if isinstance(summary_obj, dict) else None
    if isinstance(det, dict):
        minutes['details'] = {
            k: {
                'content': (v.get('content') if isinstance(v, dict) else ''),
                'key_timestamps': (v.get('key_timestamps') if isinstance(v, dict) else [])
            }
            for k, v in det.items()
        }

    # custom sections
    custom_secs = summary_obj.get('custom_sections') if isinstance(summary_obj, dict) else None
    if isinstance(custom_secs, list):
        for cs in custom_secs:
            if isinstance(cs, dict) and cs.get('id'):
                minutes['custom_sections'].append({
                    'id': cs.get('id'),
                    'title': cs.get('title', ''),
                    'content': cs.get('content', '')
                })

    # tasks and objectives (only task + description)
    try:
        tao = summary_obj.get('tasks_and_objectives') if isinstance(summary_obj, dict) else None
        print(f"[DEBUG minutes.py] tasks_and_objectives from summary_obj: {tao}")
        if isinstance(tao, list):
            print(f"[DEBUG minutes.py] tasks_and_objectives is a list with {len(tao)} items")
            for item in tao:
                if not isinstance(item, dict):
                    continue
                task = str(item.get('task', '')).strip()
                if not task:
                    continue
                minutes['tasks_and_objectives'].append({
                    'task': task,
                    'description': str(item.get('description', '')).strip()
                })
            print(f"[DEBUG minutes.py] Final tasks_and_objectives in minutes: {minutes['tasks_and_objectives']}")
        else:
            print(f"[DEBUG minutes.py] tasks_and_objectives is NOT a list, type: {type(tao)}")
    except Exception as e:
        print(f"[DEBUG minutes.py] Exception extracting tasks_and_objectives: {e}")
        pass

    return minutes


