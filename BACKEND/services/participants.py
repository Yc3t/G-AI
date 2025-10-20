import os
import uuid
from typing import Any, Dict, List

from BACKEND.llamada_whisper import transcribe_audio_simple
from BACKEND.llamada_gpt import extract_names_from_text
from BACKEND.db import list_contacts


def transcribe_name_clip(upload_folder: str, audio_file) -> Dict[str, str]:
    """Save a short clip, transcribe, and extract a suggested name.

    Returns { 'transcript': str, 'suggested_name': str }
    """
    temp_path = os.path.join(upload_folder, f"temp_name_{uuid.uuid4().hex}.webm")
    audio_file.save(temp_path)
    try:
        transcript_text = transcribe_audio_simple(temp_path)
        transcript_text = (transcript_text or '').strip()
        if not transcript_text:
            return {"transcript": "", "suggested_name": ""}
        names = extract_names_from_text(transcript_text)
        suggested = names[0] if isinstance(names, list) and len(names) > 0 else transcript_text
        return {"transcript": transcript_text, "suggested_name": suggested}
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


def normalize_and_save_participants(db, reunion_id: str, incoming: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate, dedupe by email, enrich with contacts DB, and save to DB in both 'participants' and legacy 'participantes'."""
    cleaned: List[Dict[str, Any]] = []
    seen_emails = set()

    # Build contacts lookup map (name -> email)
    contacts_map = {}
    try:
        contacts = list_contacts(db)
        for contact in contacts:
            contact_name = str(contact.get('name', '')).strip().lower()
            contact_email = contact.get('email')
            if contact_name and contact_email:
                contacts_map[contact_name] = contact_email
    except Exception as e:
        print(f"Warning: Could not load contacts for enrichment: {e}")

    for item in incoming or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name', '')).strip()
        email = item.get('email')
        if not name:
            continue

        # If no email provided, try to enrich from contacts DB
        if not email:
            name_lower = name.lower()
            if name_lower in contacts_map:
                email = contacts_map[name_lower]
                print(f"Enriched participant '{name}' with email '{email}' from contacts DB")

        if email is not None:
            email = str(email).strip()
            if email:
                email_lower = email.lower()
                if email_lower in seen_emails:
                    # skip duplicate
                    continue
                if '@' not in email or len(email) < 5 or len(email) > 254:
                    raise ValueError(f"Email inválido para {name}.")
                seen_emails.add(email_lower)
            else:
                email = None
        cleaned.append({"name": name, **({"email": email} if email else {})})

    only_names = [p['name'] for p in cleaned]
    result = db.reuniones.update_one({"id": reunion_id}, {"$set": {"participants": cleaned, "participantes": only_names}})
    if result.matched_count == 0:
        raise LookupError("Reunión no encontrada.")
    return cleaned


