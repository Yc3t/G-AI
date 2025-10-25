"""
Este archivo contiene la lógica del servidor Flask que maneja:
- El servicio de las páginas HTML del frontend.
- Una API REST para interactuar con la base de datos de reuniones (MongoDB).
- La subida y procesamiento de archivos de audio.
- La conversión de formatos de audio (WebM a MP3) usando FFmpeg.
- La transcripción de audio a texto mediante un servicio externo (Whisper).
- La generación de resúmenes ejecutivos usando un modelo de lenguaje (GPT).
- La gestión de reuniones (crear, renombrar, eliminar) y la verificación de contraseñas.
"""

# =========================================================================
# 1. IMPORTACIONES DE LIBRERÍAS
# =========================================================================

# Librerías estándar de Python
import os
import json
import uuid
import re
from datetime import datetime, timedelta
from typing import Any

# Librerías de terceros (instaladas con pip)
from flask import Flask, render_template, jsonify, send_from_directory, request
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from mutagen import File as MutagenFile
import ffmpeg  # Librería para interactuar con la herramienta de línea de comandos FFmpeg
from dotenv import load_dotenv # Para cargar variables de entorno desde un archivo .env
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Módulos locales del proyecto (del backend)
from BACKEND.llamada_whisper import transcribe_audio_structured
from BACKEND.llamada_gpt import gpt
from BACKEND.db import db, añadir_reunion, create_coleccion_contactos, ensure_indexes, upsert_contact, list_contacts, delete_contact
from BACKEND.llamada_whisper import transcribe_audio_simple
from BACKEND.llamada_gpt import extract_names_from_text, gpt # gpt se usará más tarde
from BACKEND.services.minutes import compose_minutes
from BACKEND.services.emailer import SMTPEmailer
from BACKEND.services.processing import process_audio_and_generate_summary
from BACKEND.services.participants import transcribe_name_clip, normalize_and_save_participants
from BACKEND.services.pdf_generator import generate_acta_pdf
# Carga las variables de entorno al iniciar la aplicación.
load_dotenv()



# Inicialización de la aplicación Flask.
# Se especifican las carpetas para los archivos estáticos (CSS, JS) y las plantillas (HTML).
app = Flask(__name__, static_folder='FRONTEND/static', template_folder='FRONTEND/templates')

# Configuración de la carpeta donde se guardarán los archivos subidos por los usuarios.
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Definición de las extensiones de archivo permitidas para la subida.
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'webm'}
# Inicializar colecciones e índices de contactos
try:
    create_coleccion_contactos(db)
    ensure_indexes(db)
except Exception as e:
    print(f"Error preparando colección de contactos: {e}")




def allowed_file(filename: str) -> bool:
    """
    Verifica si un nombre de archivo tiene una extensión permitida por seguridad.

    Args:
        filename (str): El nombre del archivo a verificar.
    Returns:
        bool: True si la extensión es válida, False en caso contrario.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _has_db_auth_cookie() -> bool:
    # Deprecated: frontend prompts every time; cookie not used
    return False

def _convert_webm_to_mp3(webm_path: str) -> str:
    """
    Convierte un audio .webm a .mp3 usando FFmpeg.
    Esta función es crucial para estandarizar los audios grabados desde el navegador,
    añadiendo los metadatos de duración necesarios para el reproductor HTML.

    Args:
        webm_path (str): La ruta al archivo .webm de entrada.
    Returns:
        str: La ruta al nuevo archivo .mp3 creado.
    Raises:
        ffmpeg.Error: Si el proceso de conversión de FFmpeg falla.
    """
    mp3_path = os.path.splitext(webm_path)[0] + '.mp3'
    print(f"Iniciando conversión: de '{webm_path}' a '{mp3_path}'...")
    try:
        (
            ffmpeg
            .input(webm_path)
            .output(mp3_path, audio_bitrate='192k')
            .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
        )
        os.remove(webm_path)
        print("Conversión de audio exitosa.")
        return mp3_path
    except ffmpeg.Error as e:
        print('ffmpeg stdout:', e.stdout.decode('utf8', errors='ignore'))
        print('ffmpeg stderr:', e.stderr.decode('utf8', errors='ignore'))
        raise e

def cargar_json(path: str, estructura_base: dict = None) -> dict:
    """
    Carga un archivo JSON de forma segura. Si no existe o está mal formado,
    devuelve una estructura base para evitar errores.

    Args:
        path (str): Ruta al archivo JSON.
        estructura_base (dict, optional): Diccionario a devolver en caso de error.
    Returns:
        dict: El contenido del JSON o la estructura base.
    """
    if estructura_base is None:
        estructura_base = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return estructura_base


# =========================================================================
# 4. RUTAS PARA SERVIR LAS PÁGINAS HTML
# =========================================================================

@app.route('/')
@app.route('/initial.html')
def index():
    """Sirve la página de inicio de la aplicación."""
    return render_template('initial.html')

@app.route('/database')
@app.route('/database.html')
def database():
    """Sirve la página de la base de datos de reuniones."""
    return render_template('database.html')

@app.route('/reunion')
@app.route('/reunion.html')
def reunion():
    """Sirve la página de visualización de una reunión específica."""
    return render_template('reunion.html')

@app.route('/participants')
@app.route('/participants.html')
def participants_page():
    """Sirve la nueva página para identificar participantes."""
    return render_template('participants.html')


# =========================================================================
# 5. RUTAS DE LA API REST
# =========================================================================

def _process_audio_and_generate_summary(audio_file_path: str, reunion_id: str):
    """Delegates processing to service layer to keep app.py as entry point only."""
    print(f"Iniciando procesamiento para la reunión ID: {reunion_id}")
    try:
        process_audio_and_generate_summary(db, audio_file_path, reunion_id, app.config['UPLOAD_FOLDER'])
        print(f"Acta para la reunión {reunion_id} actualizada correctamente en la DB.")
    except Exception as e:
        print(f"Error crítico en _process_audio_and_generate_summary para {reunion_id}: {e}")
        db.reuniones.update_one({"id": reunion_id}, {"$set": {"resumen": json.dumps({"error": str(e)})}})

@app.route('/api/reuniones', methods=['GET'])
def get_reuniones():
    """
    Obtiene una lista de reuniones, con opción de filtrar por fecha.
    Prepara los datos para ser consumidos por el frontend (serialización).
    """
    query = {}
    date_param = request.args.get('date')
    if date_param:
        try:
            fecha_inicio = datetime.strptime(date_param, '%Y-%m-%d')
            fecha_fin = fecha_inicio + timedelta(days=1)
            query = {"fecha_de_subida": {"$gte": fecha_inicio, "$lt": fecha_fin}}
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD."}), 400
    try:
        def _last_timestamp_seconds(text: str) -> int:
            try:
                lines = [ln.strip() for ln in (text or '').split('\n') if ln.strip()]
                for ln in reversed(lines):
                    m = re.match(r'\[(\d{2}):(\d{2})\]', ln)
                    if m:
                        return int(m.group(1)) * 60 + int(m.group(2))
            except Exception:
                pass
            return 0
        reuniones = []
        for doc in db.reuniones.find(query).sort("fecha_de_subida", -1):
            doc['_id'] = str(doc['_id'])
            if 'id' not in doc: doc['id'] = doc['_id']
            # Prefer minutes title from resumen.metadata.title when available
            try:
                if isinstance(doc.get('resumen'), str) and doc['resumen'].strip():
                    _sum = json.loads(doc['resumen'])
                    md = _sum.get('metadata') if isinstance(_sum, dict) else None
                    md_title = (md or {}).get('title') if isinstance(md, dict) else None
                    if isinstance(md_title, str) and md_title.strip():
                        doc['titulo'] = md_title.strip()
                    # Derive participants count from metadata if not present elsewhere
                    try:
                        if 'participants_count' not in doc:
                            md_participants = (md or {}).get('participants') if isinstance(md, dict) else None
                            if isinstance(md_participants, list):
                                doc['participants_count'] = len([p for p in md_participants if str(p).strip()])
                    except Exception:
                        pass
            except Exception:
                pass
            if isinstance(doc.get('fecha_de_subida'), datetime):
                doc['fecha_de_subida'] = doc['fecha_de_subida'].strftime('%Y-%m-%d %H:%M')
            # Participants count from DB fields as primary source
            try:
                if isinstance(doc.get('participants'), list):
                    doc['participants_count'] = len([p for p in doc['participants'] if isinstance(p, dict) and p.get('name')])
                elif isinstance(doc.get('participantes'), list):
                    doc['participants_count'] = len([n for n in doc['participantes'] if str(n).strip()])
            except Exception:
                pass
            # Duration seconds from transcript last timestamp
            try:
                if 'duration_seconds' not in doc and isinstance(doc.get('transcripcion'), str) and doc['transcripcion'].strip():
                    doc['duration_seconds'] = _last_timestamp_seconds(doc['transcripcion'])
            except Exception:
                pass
            reuniones.append(doc)
        return jsonify(reuniones)
    except Exception as e:
        print(f"Error en /api/reuniones: {e}")
        return jsonify({"error": "Error interno del servidor al buscar reuniones."}), 500

@app.route('/api/reunion/<reunion_id>', methods=['GET'])
def get_reunion_by_id(reunion_id: str):
    """
    Obtiene los detalles completos de una única reunión por su ID.
    MODIFICADO: Ahora es tolerante a datos incompletos durante el procesamiento.
    """
    try:
        reunion_doc = db.reuniones.find_one({"id": reunion_id})
        if not reunion_doc:
            return jsonify({"error": "Reunión no encontrada"}), 404

        # Determinar si el análisis está completo.
        is_processed = bool(reunion_doc.get('resumen') and reunion_doc.get('transcripcion'))

        summary_data = {}
        if reunion_doc.get('resumen'):
            try:
                summary_data = json.loads(reunion_doc['resumen'])
                # Debug: Check if tasks_and_objectives exist in summary
                print(f"[DEBUG app.py] Summary has tasks_and_objectives: {summary_data.get('tasks_and_objectives', 'NOT FOUND')}")
            except (json.JSONDecodeError, TypeError):
                summary_data = {} # Si hay un error, devuelve objeto vacío

        # If meeting doc has no participants but summary metadata has them, expose them
        try:
            if not reunion_doc.get('participants') and not reunion_doc.get('participantes'):
                md = summary_data.get('metadata') if isinstance(summary_data, dict) else None
                md_participants = (md or {}).get('participants') if isinstance(md, dict) else None
                if isinstance(md_participants, list) and md_participants:
                    # Do not persist; just present in API response via minutes and participants_out
                    pass
        except Exception:
            pass

        transcript_text = reunion_doc.get('transcripcion', '')
        segments = []
        if transcript_text:
            for i, line in enumerate(transcript_text.split('\n')):
                if line.strip():
                    match = re.match(r'\[(\d{2}):(\d{2})\]\s*(.*)', line.strip())
                    start_time = int(match.group(1)) * 60 + int(match.group(2)) if match else 0
                    text = match.group(3) if match else line.strip()
                    segments.append({"id": i, "start": start_time, "text": text})

        # Build minutes (on-the-fly)
        minutes_obj = compose_minutes(reunion_doc, summary_data)
        print(f"[DEBUG app.py] Minutes composed. tasks_and_objectives in minutes: {minutes_obj.get('tasks_and_objectives', 'NOT FOUND')}")
        
        # Preparar participantes (nuevo campo 'participants') enriquecidos con emails desde contactos
        participants_out = []
        try:
            if isinstance(reunion_doc.get('participants'), list):
                participants_out = [
                    {"name": p.get('name'), "email": p.get('email')} 
                    for p in reunion_doc.get('participants') if isinstance(p, dict) and p.get('name')
                ]
            elif isinstance(reunion_doc.get('participantes'), list):
                participants_out = [{"name": str(n).strip()} for n in reunion_doc.get('participantes') if str(n).strip()]
            # Fallback from summary metadata if DB has none
            if not participants_out:
                md = summary_data.get('metadata') if isinstance(summary_data, dict) else None
                md_participants = (md or {}).get('participants') if isinstance(md, dict) else None
                if isinstance(md_participants, list):
                    participants_out = [{"name": str(n).strip()} for n in md_participants if str(n).strip()]
            # Enrich with contacts emails
            try:
                contacts = {c.get('name','').strip().lower(): c.get('email') for c in list_contacts(db)}
                for p in participants_out:
                    key = str(p.get('name','')).strip().lower()
                    if key and not p.get('email'):
                        email = contacts.get(key)
                        if email:
                            p['email'] = email
            except Exception:
                pass
        except Exception:
            participants_out = []

        # Devuelve el estado junto con los datos
        return jsonify({
            "id": reunion_doc.get('id'),
            "titulo": reunion_doc.get('titulo'),
            "audio_filename": os.path.basename(reunion_doc.get('audio_path', '')) if reunion_doc.get('audio_path') else None,
            "summary_data": summary_data,
            "full_transcript_data": {"segments": segments},
            "participants": participants_out,
            "minutes": minutes_obj,
            "is_processed": is_processed # NUEVO: Flag para el frontend
        })

    except Exception as e:
        print(f"Error en /api/reunion/{reunion_id}: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    """
    Recibe un audio subido desde el PC, crea una entrada de reunión vacía
    y devuelve el ID para redirigir a la página de participantes.
    """
    if 'audio' not in request.files: return jsonify({"error": "No se encontró el archivo."}), 400
    file = request.files['audio']
    if file.filename == '' or not allowed_file(file.filename): return jsonify({"error": "Archivo no válido."}), 400
    
    unique_id = uuid.uuid4().hex[:8]
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}.{file_extension}")
    file.save(file_path)

    if file_extension == 'webm':
        try:
            file_path = _convert_webm_to_mp3(file_path)
        except Exception as e:
            print(f"Error convirtiendo a mp3: {e}.")
            
    reunion_data = {
        "id": unique_id, "titulo": f"Reunión de {secure_filename(file.filename)}",
        "audio_path": file_path, "fecha_de_subida": datetime.now(),
        "participantes": [], "transcripcion": None, "resumen": None
    }
    añadir_reunion(db, reunion_data)
    return jsonify({"reunion_id": unique_id, "message": "Archivo inicial guardado."}), 201


# --- NUEVAS RUTAS PARA EL FLUJO DE GRABACIÓN ---

@app.route('/upload_and_create_meeting', methods=['POST'])
def upload_and_create_meeting():
    """
    Recibe un archivo subido, lo guarda, crea la entrada en la DB y devuelve el ID.
    Esta ruta es para el flujo "subir archivo", no para "grabar".
    """
    if 'audio' not in request.files: return jsonify({"error": "No se encontró el archivo."}), 400
    file = request.files['audio']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "Archivo no válido."}), 400
    
    unique_id = uuid.uuid4().hex[:8]
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}.{file_extension}")
    file.save(file_path)

    if file_extension == 'webm':
        try:
            file_path = _convert_webm_to_mp3(file_path)
        except Exception as e: print(f"Error convirtiendo a mp3: {e}.")
            
    reunion_data = {
        "id": unique_id, "titulo": f"Reunión de {secure_filename(file.filename)}",
        "audio_path": file_path, "fecha_de_subida": datetime.now(),
        "participantes": [], "transcripcion": None, "resumen": None
    }
    añadir_reunion(db, reunion_data)
    return jsonify({"reunion_id": unique_id, "message": "Archivo inicial guardado."}), 201


# REMOVED: create_meeting_from_participants endpoint - now handled by process_final_audio


# AÑADIDO: Esta ruta es para actualizar los participantes de una reunión YA CREADA (caso de subida de archivo)
@app.route('/update_meeting_participants', methods=['POST'])
def update_meeting_participants():
    """
    Actualiza la lista de participantes de una reunión que ya existe en la DB.
    """
    data = request.get_json()
    reunion_id = data.get('reunionId')
    participants = data.get('participants')
    if not reunion_id or not isinstance(participants, list):
        return jsonify({"error": "Datos incompletos."}), 400

    db.reuniones.update_one({"id": reunion_id}, {"$set": {"participantes": participants}})

    # Lanzar el análisis del audio que ya estaba guardado
    reunion_doc = db.reuniones.find_one({"id": reunion_id})
    if reunion_doc and reunion_doc.get('audio_path'):
        # _process_audio_and_generate_summary(reunion_doc['audio_path'], reunion_id)
        print(f"Lanzando análisis para la reunión subida: {reunion_id}")
        return jsonify({"success": True, "reunion_id": reunion_id}), 200
    else:
        return jsonify({"error": "No se encontró el audio de la reunión."}), 404


@app.route('/process_final_audio', methods=['POST'])
def process_final_audio():
    """
    Recibe el audio de la reunión principal y su ID, lo asocia en la DB
    y lanza el proceso completo de análisis.
    """
    if 'audio' not in request.files: 
        return jsonify({"error": "No se encontró el archivo de audio."}), 400

    file = request.files['audio']
    if file.filename == '': 
        return jsonify({"error": "Archivo no válido."}), 400

    # Get reunion ID if provided, otherwise create new meeting
    reunion_id = request.form.get('reunionId')
    participants_str = request.form.get('participants', '')
    participants = participants_str.split(',') if participants_str else []
    participants = [p.strip() for p in participants if p.strip()]
    
    if not reunion_id:
        # Create new meeting with detected participants
        reunion_id = uuid.uuid4().hex[:8]
        # Normalize participants into objects and enrich with emails from contacts
        participants_objs = [{"name": n} for n in participants]

        # Enrich with emails from contacts DB
        try:
            contacts = {c.get('name','').strip().lower(): c.get('email') for c in list_contacts(db)}
            for p in participants_objs:
                name_lower = p.get('name', '').strip().lower()
                if name_lower and name_lower in contacts and contacts[name_lower]:
                    p['email'] = contacts[name_lower]
                    print(f"Enriched participant '{p['name']}' with email '{p['email']}' from contacts DB")
        except Exception as e:
            print(f"Warning: Could not enrich participants with contacts: {e}")

        reunion_data = {
            "id": reunion_id,
            "titulo": f"Reunión {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "fecha_de_subida": datetime.now(),
            "participantes": participants,
            "participants": participants_objs,
            "audio_path": None,
            "transcripcion": None,
            "resumen": None
        }
        añadir_reunion(db, reunion_data)
    else:
        # Update existing meeting with participants if provided
        if participants:
            participants_objs = [{"name": n} for n in participants]

            # Enrich with emails from contacts DB
            try:
                contacts = {c.get('name','').strip().lower(): c.get('email') for c in list_contacts(db)}
                for p in participants_objs:
                    name_lower = p.get('name', '').strip().lower()
                    if name_lower and name_lower in contacts and contacts[name_lower]:
                        p['email'] = contacts[name_lower]
                        print(f"Enriched participant '{p['name']}' with email '{p['email']}' from contacts DB")
            except Exception as e:
                print(f"Warning: Could not enrich participants with contacts: {e}")

            db.reuniones.update_one({"id": reunion_id}, {"$set": {"participantes": participants, "participants": participants_objs}})

    # Guardar archivo de audio con el nombre del ID de la reunión.
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{reunion_id}.{file_extension}")
    file.save(file_path)

    if file_extension == 'webm':
        try:
            file_path = _convert_webm_to_mp3(file_path)
        except Exception as e:
            print(f"Error convirtiendo a mp3: {e}.")
    
    # Actualiza el documento en la DB con la ruta del archivo.
    db.reuniones.update_one({"id": reunion_id}, {"$set": {"audio_path": file_path}})

    # Lanza el proceso de análisis en segundo plano.
    _process_audio_and_generate_summary(file_path, reunion_id)

    print(f"Audio para la reunión {reunion_id} guardado. Análisis iniciado en segundo plano.")
    return jsonify({"reunion_id": reunion_id, "message": "Procesamiento iniciado."}), 200


# MODIFICADO: Esta ruta ahora usa el flujo simplificado
@app.route('/identify_speakers', methods=['POST'])
def identify_speakers():
    """
    Recibe un audio de nombres, lo transcribe con Whisper y extrae los
    nombres usando GPT. No requiere diarization.
    """
    audio_file = request.files.get('audio_names')
    if not audio_file:
        return jsonify({"error": "No se recibió el archivo de audio con los nombres."}), 400

    # Guardar el archivo temporalmente
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_names_{uuid.uuid4().hex}.webm")
    audio_file.save(temp_path)

    try:
        # Paso 1: Transcripción simple del audio
        transcript_text = transcribe_audio_simple(temp_path)

        if "[Error" in transcript_text:
            raise Exception("La transcripción del audio de nombres falló.")
        
        # Paso 2: Usar GPT para extraer los nombres de la transcripción
        participant_names = extract_names_from_text(transcript_text)
        
        # Devolver la lista de nombres al frontend
        return jsonify({"speakers": participant_names})
    
    except Exception as e:
        print(f"Error en el flujo de identificación de hablantes: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        # Asegurarse de que el archivo temporal siempre se elimine
        if os.path.exists(temp_path):
            os.remove(temp_path)


# === PARTICIPANTS API (nuevo flujo) ===
@app.route('/api/reunion/<reunion_id>/transcribe-name', methods=['POST'])
def transcribe_name_for_participant(reunion_id: str):
    """Transcribe a short single-speaker clip to suggest a participant name (no diarization)."""
    audio_file = request.files.get('audio')
    if not audio_file:
        return jsonify({"error": "No se recibió el archivo de audio."}), 400
    try:
        result = transcribe_name_clip(app.config['UPLOAD_FOLDER'], audio_file)
        if not result.get('transcript'):
            return jsonify({"error": "Transcripción vacía o inválida."}), 422
        return jsonify(result)
    except Exception as e:
        print(f"Error en transcribe-name: {e}")
        return jsonify({"error": "Error al transcribir el nombre."}), 500


@app.route('/api/reunion/<reunion_id>/participants', methods=['PUT'])
def put_reunion_participants(reunion_id: str):
    """Replace participants list for a meeting. Accepts [{name, email?}]."""
    try:
        payload = request.get_json(silent=True) or {}
        incoming = payload.get('participants')
        if not isinstance(incoming, list):
            return jsonify({"error": "Formato no válido. Se esperaba 'participants' como lista."}), 400
        cleaned = normalize_and_save_participants(db, reunion_id, incoming)
        return jsonify({"participants": cleaned})
    except Exception as e:
        print(f"Error en PUT participants: {e}")
        return jsonify({"error": "Error interno del servidor."}), 500


@app.route('/api/reunion/<reunion_id>/minutes', methods=['PUT'])
def update_reunion_minutes(reunion_id: str):
    """Update meeting minutes: participants, key_points, and custom_sections."""
    try:
        payload = request.get_json(silent=True) or {}

        # Get the current meeting document
        reunion_doc = db.reuniones.find_one({"id": reunion_id})
        if not reunion_doc:
            return jsonify({"error": "Reunión no encontrada."}), 404

        # Parse current summary to preserve other data
        current_summary = {}
        if reunion_doc.get('resumen'):
            try:
                current_summary = json.loads(reunion_doc['resumen'])
            except:
                pass

        # Update fields based on payload
        update_fields = {}

        # Update participants if provided
        if 'participants' in payload:
            cleaned = normalize_and_save_participants(db, reunion_id, payload['participants'])
            # Already saved by normalize_and_save_participants, but we need to reflect it

        # Update key_points if provided
        if 'key_points' in payload:
            key_points = payload['key_points']
            # Update main_points in summary
            if 'main_points' not in current_summary:
                current_summary['main_points'] = []

            # Convert new key points to main_points format (preserve IDs if they exist)
            new_main_points = []
            for idx, kp in enumerate(key_points):
                # Try to preserve existing ID if count matches
                existing_id = None
                if idx < len(current_summary.get('main_points', [])):
                    existing_id = current_summary['main_points'][idx].get('id')

                new_main_points.append({
                    'id': existing_id or str(idx + 1),
                    'title': kp.get('title', ''),
                    'time': kp.get('time')
                })

            current_summary['main_points'] = new_main_points

        # Update tasks_and_objectives if provided
        if 'tasks_and_objectives' in payload:
            tasks = payload['tasks_and_objectives']
            current_summary['tasks_and_objectives'] = [
                {
                    'task': t.get('task', ''),
                    'description': t.get('description', '')
                }
                for t in tasks if isinstance(t, dict) and t.get('task')
            ]

        # Update custom_sections if provided
        if 'custom_sections' in payload:
            custom_sections = payload['custom_sections']
            current_summary['custom_sections'] = custom_sections

        # Save updated summary back to DB
        if current_summary:
            update_fields['resumen'] = json.dumps(current_summary, ensure_ascii=False)

        if update_fields:
            db.reuniones.update_one(
                {"id": reunion_id},
                {"$set": update_fields}
            )

        return jsonify({"message": "Minutos actualizados correctamente."})

    except Exception as e:
        print(f"Error en PUT /api/reunion/{reunion_id}/minutes: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Error interno del servidor."}), 500


@app.route('/confirm_participants', methods=['POST'])
def confirm_participants():
    # (Esta ruta puede mantenerse igual por ahora. La llamaremos más tarde)
    data = request.get_json()
    reunion_id = data.get('reunion_id')
    participants = data.get('participants')
    if not reunion_id or participants is None: return jsonify({"error": "Faltan datos."}), 400
    
    db.reuniones.update_one({"id": reunion_id}, {"$set": {"participantes": participants}})
    
    # Aquí es donde lanzarías el análisis final de la reunión completa
    reunion_doc = db.reuniones.find_one({"id": reunion_id})
    # _process_full_meeting(reunion_doc['audio_path'], reunion_id, participants)
    
    return jsonify({"success": True})

@app.route('/audio/<filename>')
def uploaded_audio(filename: str):
    """Sirve los archivos de audio procesados desde la carpeta 'uploads'."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/reunion/<reunion_id>/send-summary', methods=['POST'])
def send_summary_email(reunion_id: str):
    """Send the meeting summary to all participants with valid emails."""
    try:
        reunion_doc = db.reuniones.find_one({"id": reunion_id})
        if not reunion_doc:
            return jsonify({"error": "Reunión no encontrada."}), 404

        # Parse summary
        summary = {}
        try:
            if reunion_doc.get('resumen'):
                summary = json.loads(reunion_doc['resumen'])
        except Exception:
            summary = {}

        # Participants with email
        participants = []
        if isinstance(reunion_doc.get('participants'), list):
            for p in reunion_doc.get('participants'):
                if isinstance(p, dict) and p.get('name') and p.get('email'):
                    participants.append({"name": p['name'], "email": p['email']})

        if not participants:
            return jsonify({"error": "No hay participantes con email asociado."}), 400

        emailer = SMTPEmailer()
        if not emailer.is_configured():
            return jsonify({"error": "SMTP no configurado. Defina SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM."}), 500

        # Use minutes for email content
        # Reuse the same composer as in GET
        def _last_timestamp_seconds(text: str) -> int:
            try:
                lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
                for ln in reversed(lines):
                    m = re.match(r'\[(\d{2}):(\d{2})\]', ln)
                    if m:
                        return int(m.group(1)) * 60 + int(m.group(2))
            except Exception:
                pass
            return 0

        def compose_minutes(doc: dict, summary_obj: dict) -> dict:
            minutes = {"metadata": {}, "participants": [], "key_points": [], "details": {}}
            title_local = summary_obj.get('metadata', {}).get('title') if isinstance(summary_obj.get('metadata'), dict) else None
            if not title_local:
                title_local = doc.get('titulo') or 'Acta de Reunión'
            minutes['metadata']['title'] = title_local
            fecha = doc.get('fecha_de_subida')
            try:
                if isinstance(fecha, datetime):
                    minutes['metadata']['date'] = fecha.isoformat()
                else:
                    minutes['metadata']['date'] = str(fecha) if fecha else None
            except Exception:
                minutes['metadata']['date'] = None
            minutes['metadata']['meeting_id'] = doc.get('id')
            text = doc.get('transcripcion') or ''
            if isinstance(text, str) and text.strip():
                minutes['metadata']['duration_seconds'] = _last_timestamp_seconds(text)
            if isinstance(doc.get('participants'), list):
                for p in doc.get('participants'):
                    if isinstance(p, dict) and p.get('name'):
                        entry = {"name": p['name']}
                        if p.get('email'): entry['email'] = p['email']
                        minutes['participants'].append(entry)
            elif isinstance(doc.get('participantes'), list):
                for n in doc.get('participantes'):
                    n_str = str(n).strip()
                    if n_str: minutes['participants'].append({"name": n_str})
            mps = summary_obj.get('main_points') if isinstance(summary_obj, dict) else None
            if isinstance(mps, list):
                for mp in mps:
                    if not isinstance(mp, dict): continue
                    minutes['key_points'].append({'id': mp.get('id'), 'title': mp.get('title'), 'time': mp.get('time')})
            det = summary_obj.get('detailed_summary') if isinstance(summary_obj, dict) else None
            if isinstance(det, dict):
                minutes['details'] = {
                    k: {'content': (v.get('content') if isinstance(v, dict) else ''), 'key_timestamps': (v.get('key_timestamps') if isinstance(v, dict) else [])}
                    for k, v in det.items()
                }
            # action_items logic removed per user request
            return minutes

        minutes_obj = compose_minutes(reunion_doc, summary)

        title = minutes_obj.get('metadata', {}).get('title') or 'Acta de Reunión'
        subject = f"Acta de la reunión: {title}"

        def build_body_from_minutes():
            points_html = ''.join([f"<li>{p.get('title','')}</li>" for p in (minutes_obj.get('key_points') or [])])
            participants_html = ''.join([f"<li>{(p.get('name') or '')} {( '('+p['email']+')' ) if p.get('email') else ''}</li>" for p in (minutes_obj.get('participants') or [])])
            date_txt = minutes_obj.get('metadata', {}).get('date') or ''
            return f"""
                <html>
                <body>
                    <h2>{title}</h2>
                    <p>Fecha: {date_txt}</p>
                    <h3>Asistentes</h3>
                    <ul>{participants_html or '<li>No especificados</li>'}</ul>
                    <h3>Puntos Clave</h3>
                    <ul>{points_html or '<li>Sin puntos clave</li>'}</ul>
                </body>
                </html>
            """

        html_body = build_body_from_minutes()

        # Send emails via service
        rcpts = [p['email'] for p in participants]
        try:
            result = emailer.send_html_bulk(subject, html_body, rcpts)
        except Exception as e:
            print(f"SMTP send error: {e}")
            return jsonify({"error": "Fallo enviando correos."}), 500

        delivered = result.get('delivered', [])
        failed = result.get('failed', [])
        return jsonify({"delivered": delivered, "failed": failed, "count": {"delivered": len(delivered), "failed": len(failed)}})
    except Exception as e:
        print(f"Error en send-summary: {e}")
        return jsonify({"error": "Error interno del servidor."}), 500


@app.route('/api/reunion/<reunion_id>/send-acta-pdf', methods=['POST'])
def send_acta_pdf_email(reunion_id: str):
    """Generate PDF acta and send it via email to all participants with valid emails."""
    try:
        reunion_doc = db.reuniones.find_one({"id": reunion_id})
        if not reunion_doc:
            return jsonify({"error": "Reunión no encontrada."}), 404

        # Parse summary
        summary = {}
        try:
            if reunion_doc.get('resumen'):
                summary = json.loads(reunion_doc['resumen'])
        except Exception:
            summary = {}

        # Compose minutes data for PDF generation
        minutes_obj = compose_minutes(reunion_doc, summary)

        # Get participants with emails
        participants = []
        if isinstance(reunion_doc.get('participants'), list):
            for p in reunion_doc.get('participants'):
                if isinstance(p, dict) and p.get('name') and p.get('email'):
                    participants.append({"name": p['name'], "email": p['email']})

        if not participants:
            return jsonify({"error": "No hay participantes con email asociado."}), 400

        # Initialize emailer
        emailer = SMTPEmailer()
        if not emailer.is_configured():
            return jsonify({"error": "SMTP no configurado. Defina SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM."}), 500

        # Generate PDF
        try:
            pdf_bytes = generate_acta_pdf(minutes_obj)
        except Exception as e:
            print(f"Error generando PDF: {e}")
            return jsonify({"error": "Error al generar el PDF del acta."}), 500

        # Prepare email details
        meeting_date = minutes_obj.get('metadata', {}).get('date', '')
        date_str = ''
        if meeting_date:
            try:
                date_obj = datetime.fromisoformat(meeting_date.replace('Z', '+00:00'))
                date_str = date_obj.strftime('%d/%m/%Y')
            except Exception:
                date_str = datetime.now().strftime('%d/%m/%Y')
        else:
            date_str = datetime.now().strftime('%d/%m/%Y')

        subject = f"Acta de Reunión {date_str}"
        title = minutes_obj.get('metadata', {}).get('title', 'Reunión')
        html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #17345C;">Acta de Reunión {date_str}</h2>
                <p>Estimado/a participante,</p>
                <p>Adjunto encontrarás el acta de la reunión <strong>{title}</strong> celebrada el {date_str}.</p>
                <br>Frumecar</p>
            </body>
            </html>
        """

        filename = f"Acta_{title.replace(' ', '_')}_{date_str.replace('/', '-')}.pdf"

        # Send emails
        rcpts = [p['email'] for p in participants]
        try:
            result = emailer.send_pdf_bulk(subject, pdf_bytes, filename, rcpts, html_body)
        except Exception as e:
            print(f"Error enviando correos: {e}")
            return jsonify({"error": "Fallo enviando correos."}), 500

        delivered = result.get('delivered', [])
        failed = result.get('failed', [])
        return jsonify({
            "delivered": delivered,
            "failed": failed,
            "count": {"delivered": len(delivered), "failed": len(failed)}
        })

    except Exception as e:
        print(f"Error en send-acta-pdf: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Error interno del servidor."}), 500


@app.route('/api/reunion/<reunion_id>/send-acta-pdf-upload', methods=['POST'])
def send_acta_pdf_email_upload(reunion_id: str):
    """Email an uploaded PDF (generated on the frontend) to participants with valid emails.

    Expects multipart/form-data with field 'pdf' and optional 'filename'.
    Reuses meeting metadata to compose subject and HTML body; does not render server-side PDF.
    """
    try:
        reunion_doc = db.reuniones.find_one({"id": reunion_id})
        if not reunion_doc:
            return jsonify({"error": "Reunión no encontrada."}), 404

        # Uploaded PDF
        pdf_file = request.files.get('pdf')
        if not pdf_file:
            return jsonify({"error": "No se recibió el PDF."}), 400
        pdf_bytes = pdf_file.read()
        if not pdf_bytes:
            return jsonify({"error": "El PDF está vacío."}), 400

        # Parse summary to build minutes metadata (title/date)
        summary = {}
        try:
            if reunion_doc.get('resumen'):
                summary = json.loads(reunion_doc['resumen'])
        except Exception:
            summary = {}

        minutes_obj = compose_minutes(reunion_doc, summary)

        # Recipients with email
        participants = []
        if isinstance(reunion_doc.get('participants'), list):
            for p in reunion_doc.get('participants'):
                if isinstance(p, dict) and p.get('name') and p.get('email'):
                    participants.append({"name": p['name'], "email": p['email']})
        if not participants:
            return jsonify({"error": "No hay participantes con email asociado."}), 400

        # Emailer config
        emailer = SMTPEmailer()
        if not emailer.is_configured():
            return jsonify({"error": "SMTP no configurado. Defina SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM."}), 500

        # Subject/body
        meeting_date = minutes_obj.get('metadata', {}).get('date', '')
        try:
            date_obj = datetime.fromisoformat(meeting_date.replace('Z', '+00:00')) if meeting_date else datetime.now()
            date_str = date_obj.strftime('%d/%m/%Y')
        except Exception:
            date_str = datetime.now().strftime('%d/%m/%Y')
        title = minutes_obj.get('metadata', {}).get('title', 'Reunión')
        subject = f"Acta de Reunión {date_str}"
        html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #17345C;">Acta de Reunión {date_str}</h2>
                <p>Estimado/a participante,</p>
                <p>Adjunto encontrarás el acta de la reunión <strong>{title}</strong> celebrada el {date_str}.</p>
                <br>Frumecar</p>
            </body>
            </html>
        """

        # Filename
        incoming_filename = request.form.get('filename')
        if isinstance(incoming_filename, str) and incoming_filename.strip():
            filename = incoming_filename.strip()
        else:
            filename = f"Acta_{title.replace(' ', '_')}_{date_str.replace('/', '-')}.pdf"

        # Send
        rcpts = [p['email'] for p in participants]
        try:
            result = emailer.send_pdf_bulk(subject, pdf_bytes, filename, rcpts, html_body)
        except Exception as e:
            print(f"Error enviando correos (upload): {e}")
            return jsonify({"error": "Fallo enviando correos."}), 500

        delivered = result.get('delivered', [])
        failed = result.get('failed', [])
        return jsonify({
            "delivered": delivered,
            "failed": failed,
            "count": {"delivered": len(delivered), "failed": len(failed)}
        })
    except Exception as e:
        print(f"Error en send-acta-pdf-upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Error interno del servidor."}), 500


@app.route('/direct_summarize_transcript', methods=['POST'])
def direct_summarize_transcript():
    """
    Maneja la subida de un .txt, crea un registro y genera un resumen.
    """
    if 'transcript_file' not in request.files: return jsonify({"error": "No se encontró el archivo de transcripción."}), 400
    file = request.files['transcript_file']
    if file.filename == '': return jsonify({"error": "Archivo no seleccionado."}), 400
    try:
        transcript_content = file.read().decode('utf-8')
        unique_id = uuid.uuid4().hex[:8]
        reunion_data = {
            "id": unique_id, "titulo": f"Transcripción: {file.filename}", "audio_path": None,
            "transcripcion": transcript_content, "fecha_de_subida": datetime.now(), "resumen": ""
        }
        añadir_reunion(db, reunion_data)
        
        temp_gpt_input_file = f"gpt_input_{unique_id}.txt"
        with open(temp_gpt_input_file, 'w', encoding='utf-8') as f: f.write(transcript_content)
        gpt(temp_gpt_input_file, participants=[])  # No hay participantes en este caso
        os.remove(temp_gpt_input_file)
        
        resumen_data = cargar_json('resumen.json', {})
        if os.path.exists('resumen.json'): os.remove('resumen.json')
        
        db.reuniones.update_one({"id": unique_id}, {"$set": {"resumen": json.dumps(resumen_data, ensure_ascii=False)}})
        
        return jsonify({"reunion_id": unique_id, "message": "Transcripción procesada."})
    except Exception as e:
        print(f"Error en /direct_summarize_transcript: {e}")
        return jsonify({"error": "Error inesperado al procesar la transcripción."}), 500


@app.route('/verify_password', methods=['POST'])
def verify_password():
    """
    Verifica si la contraseña proporcionada coincide con la del entorno.
    """
    data = request.get_json()
    if not data or 'password' not in data:
        return jsonify({"success": False, "error": "No se proporcionó contraseña."}), 400

    submitted_password = data['password']
    correct_password = os.getenv('DATABASE_PASSWORD')

    if not correct_password:
        print("ERROR: La variable de entorno DATABASE_PASSWORD no está configurada.")
        return jsonify({"success": False, "error": "Error de configuración del servidor."}), 500

    if submitted_password == correct_password:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Contraseña incorrecta."}), 401


# ===================== CONTACTS API =====================
@app.route('/api/contacts', methods=['GET'])
def api_list_contacts():
    try:
        contacts = list_contacts(db)
        return jsonify(contacts)
    except Exception as e:
        print(f"Error listing contacts: {e}")
        return jsonify({"error": "Error interno."}), 500

@app.route('/api/contacts', methods=['POST'])
def api_create_or_update_contact():
    try:
        payload = request.get_json(silent=True) or {}
        name = (payload.get('name') or '').strip()
        email = payload.get('email')
        if not name:
            return jsonify({"error": "Nombre requerido."}), 400
        contact = upsert_contact(db, name, email)
        contact.pop('_id', None)
        return jsonify(contact), 201
    except Exception as e:
        print(f"Error upserting contact: {e}")
        return jsonify({"error": "Error interno."}), 500

@app.route('/api/contacts/<name>', methods=['DELETE'])
def api_delete_contact(name: str):
    try:
        deleted = delete_contact(db, name)
        if deleted == 0:
            return jsonify({"error": "No encontrado."}), 404
        return jsonify({"deleted": deleted})
    except Exception as e:
        print(f"Error deleting contact: {e}")
        return jsonify({"error": "Error interno."}), 500

@app.route('/rename_reunion/<reunion_id>', methods=['PUT'])
def rename_reunion_route(reunion_id: str):
    """Permite cambiar el título de una reunión existente."""
    data = request.get_json()
    nuevo_titulo = data.get('nuevo_titulo')
    if not nuevo_titulo:
        return jsonify({"error": "No se proporcionó un nuevo título."}), 400
    try:
        result = db.reuniones.update_one({"id": reunion_id}, {"$set": {"titulo": nuevo_titulo}})
        if result.matched_count == 0:
            return jsonify({"error": "No se encontró una reunión con ese ID."}), 404
        return jsonify({"message": "Reunión renombrada correctamente."}), 200
    except Exception as e:
        print(f"Error en /rename_reunion: {e}")
        return jsonify({"error": "Ocurrió un error en el servidor."}), 500

@app.route('/delete_reunion/<reunion_id>', methods=['DELETE'])
def delete_reunion_route(reunion_id: str):
    """
    Elimina una reunión de la DB y su archivo de audio asociado del disco.
    """
    try:
        reunion_a_eliminar = db.reuniones.find_one({"id": reunion_id})
        if not reunion_a_eliminar:
            return jsonify({"error": "No se encontró la reunión para eliminar."}), 404

        audio_path = reunion_a_eliminar.get('audio_path')
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                print(f"Archivo físico eliminado: {audio_path}")
            except OSError as e:
                print(f"Error al eliminar el archivo físico {audio_path}: {e}")

        result = db.reuniones.delete_one({"id": reunion_id})
        if result.deleted_count == 0:
            return jsonify({"error": "No se pudo eliminar la reunión de la base de datos."}), 500

        return jsonify({"message": "Reunión eliminada correctamente."}), 200
    except Exception as e:
        print(f"Error en /delete_reunion: {e}")
        return jsonify({"error": "Ocurrió un error en el servidor al eliminar la reunión."}), 500
    
# app.py - AÑADIR ESTA NUEVA RUTA

@app.route('/upload_and_process_directly', methods=['POST'])
def upload_and_process_directly():
    """
    NUEVO: Recibe un archivo de audio, lo guarda, crea la reunión,
    lanza el análisis completo inmediatamente y devuelve el ID.
    Este flujo omite la página de participantes.
    """
    if 'audio' not in request.files:
        return jsonify({"error": "No se encontró el archivo de audio."}), 400
    
    file = request.files['audio']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "Archivo no válido."}), 400

    # 1. Guardar el archivo de forma segura
    unique_id = uuid.uuid4().hex[:8]
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{unique_id}.{file_extension}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # Convertir a MP3 si es necesario
    if file_extension == 'webm':
        try:
            file_path = _convert_webm_to_mp3(file_path)
        except Exception as e:
            print(f"Error convirtiendo a mp3: {e}.")
            
    # 2. Crear el registro en la base de datos (con participantes vacíos)
    reunion_data = {
        "id": unique_id,
        "titulo": f"Reunión de archivo: {secure_filename(file.filename)}",
        "audio_path": file_path,
        "fecha_de_subida": datetime.now(),
        "participantes": [], # Se omite la petición de participantes
        "transcripcion": None,
        "resumen": None
    }
    añadir_reunion(db, reunion_data)

    # 3. Lanzar el proceso de análisis completo en segundo plano
    #    (Esta es la parte clave que se hace de inmediato)
    _process_audio_and_generate_summary(file_path, unique_id)

    print(f"Archivo subido {unique_id}. Análisis directo iniciado en segundo plano.")
    
    # 4. Devolver el ID para que el frontend muestre el progreso y redirija
    return jsonify({"reunion_id": unique_id, "message": "Procesamiento iniciado."}), 200

@app.route('/upload_and_process_meeting', methods=['POST'])
def upload_and_process_meeting():
    """
    Recibe el audio de la reunión principal y la lista de participantes,
    lo guarda, y lanza el proceso completo de análisis.
    """
    if 'audio' not in request.files:
        return jsonify({"error": "No se encontró el archivo de audio."}), 400
    
    file = request.files['audio']
    # Los participantes vienen como un string separado por comas
    participants_str = request.form.get('participants', '')
    participants = participants_str.split(',') if participants_str else []
    
    if file.filename == '':
        return jsonify({"error": "Archivo no válido."}), 400

    # 1. Guardar el archivo
    unique_id = uuid.uuid4().hex[:8]
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}.{file_extension}")
    file.save(file_path)

    if file_extension == 'webm':
        try:
            file_path = _convert_webm_to_mp3(file_path)
        except Exception as e:
            print(f"Error convirtiendo a mp3: {e}.")
            
    # 2. Crear el registro en la base de datos CON los participantes
    reunion_data = {
        "id": unique_id,
        "titulo": f"Reunión {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "audio_path": file_path,
        "fecha_de_subida": datetime.now(),
        "participantes": participants,
        "transcripcion": None,
        "resumen": None
    }
    añadir_reunion(db, reunion_data)

    # 3. Lanzar el proceso de análisis completo en segundo plano
    #    (usando tus funciones de `_process_full_meeting` que ya tenías)
    # _process_audio_and_generate_summary(file_path, unique_id) # Esta función ahora recibiría los `participants`

    # Devuelve el ID para que el frontend redirija a la página de resultados
    return jsonify({"reunion_id": unique_id, "message": "Procesamiento iniciado."}), 200


# =========================================================================
# 6. PUNTO DE ENTRADA DE LA APLICACIÓN
# =========================================================================

if __name__ == '__main__':
    """
    Este bloque se ejecuta solo cuando el script se corre directamente.
    Inicia el servidor de desarrollo de Flask.
    """
    app.run(debug=True, host='0.0.0.0', port=5000)