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


def compose_minutes(meeting_doc: Dict[str, Any], minutes_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Compose a normalized minutes object from meeting doc and one-shot generated minutes.

    meeting_doc: DB document with keys like id, titulo, fecha_de_subida, transcripcion, participants/participantes
    minutes_obj: dict from generate_minutes() with keys objective, metadata, main_points, details, tasks_and_objectives
    """
    minutes: Dict[str, Any] = {
        "metadata": {},
        "participants": [],
        "key_points": [],
        "details": {},
        "tasks_and_objectives": []
    }

    # objective
    try:
        obj = str(minutes_obj.get('objective', '') or '').strip()
        if obj:
            minutes['objective'] = obj
    except Exception:
        pass

    # metadata - prefer generated title, fallback to DB
    title = None
    try:
        md = minutes_obj.get('metadata') if isinstance(minutes_obj, dict) else None
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

    # participants - prefer from DB (richer data with emails), fallback to generated
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

    # fallback: if still empty, pull from generated minutes metadata participants
    try:
        if not minutes['participants']:
            md = minutes_obj.get('metadata') if isinstance(minutes_obj, dict) else None
            if isinstance(md, dict):
                md_participants = md.get('participants')
                if isinstance(md_participants, list):
                    for n in md_participants:
                        n_str = str(n).strip()
                        if n_str:
                            minutes['participants'].append({"name": n_str})
    except Exception:
        pass

    # key points - directly from generated minutes
    mps = minutes_obj.get('main_points') if isinstance(minutes_obj, dict) else None
    if isinstance(mps, list):
        for mp in mps:
            if not isinstance(mp, dict):
                continue
            minutes['key_points'].append({
                'id': mp.get('id'),
                'title': mp.get('title'),
                'time': mp.get('time')
            })

    # details - directly from generated minutes
    try:
        det = minutes_obj.get('details') if isinstance(minutes_obj, dict) else None
        if isinstance(det, dict):
            minutes['details'] = {
                k: {
                    'title': (v.get('title') if isinstance(v, dict) else ''),
                    'content': (v.get('content') if isinstance(v, dict) else '')
                }
                for k, v in det.items()
            }
        elif isinstance(det, list):
            # Convert list to dict keyed by index if needed
            converted: Dict[str, Any] = {}
            for idx, item in enumerate(det):
                if isinstance(item, dict):
                    key = str(item.get('id') or f'detail_{idx}')
                    converted[key] = {
                        'title': item.get('title', ''),
                        'content': item.get('content', '')
                    }
            minutes['details'] = converted
    except Exception:
        pass

    # tasks and objectives - directly from generated minutes
    try:
        tao = minutes_obj.get('tasks_and_objectives') if isinstance(minutes_obj, dict) else None
        print(f"[DEBUG minutes.py] tasks_and_objectives from minutes_obj: {tao}")
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

