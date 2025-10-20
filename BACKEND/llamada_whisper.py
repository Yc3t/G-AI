import os
from dotenv import load_dotenv
from groq import Groq
from pydub import AudioSegment
from io import BytesIO
import json # Added for JSON output
from typing import List, Optional # Added for Pydantic models
from pydantic import BaseModel # Added for Pydantic models

load_dotenv(override=True)

# Pydantic Models for Whisper verbose_json output
class WhisperSegment(BaseModel):
    id: int
    seek: int
    start: float
    end: float
    text: str
    tokens: List[int]
    temperature: float
    avg_logprob: float
    compression_ratio: float
    no_speech_prob: float
    transient: Optional[bool] = None # transient might not always be present

class WhisperVerboseJSON(BaseModel):
    task: str
    language: str
    duration: float
    text: str
    segments: List[WhisperSegment]
    words: Optional[List[dict]] = None # For word-level timestamps, if available and needed. Or use a more specific Word model.

# Function to transcribe and save structured output
def transcribe_audio_structured(filename, client = Groq(api_key=os.getenv("GROQ_API_KEY"))):
    # Usamos from_file para soportar múltiples formatos (mp3, wav, m4a, etc.)
    audio = AudioSegment.from_file(filename)
    chunk_length_ms = 15 * 60 * 1000  # 15 minutes in milliseconds
    
    all_segments: List[WhisperSegment] = []
    full_text_parts: List[str] = []
    total_duration_processed = 0.0
    detected_language = "unknown"

    for i in range(0, len(audio), chunk_length_ms):
        chunk_idx = i // chunk_length_ms + 1
        total_chunks = len(range(0, len(audio), chunk_length_ms))
        print(f"[Whisper] Procesando chunk {chunk_idx}/{total_chunks} (milisegundos {i} – {i+chunk_length_ms})…")

        chunk_audio = audio[i:i + chunk_length_ms]
        
        mp3_buffer = BytesIO()
        chunk_audio.export(mp3_buffer, format="mp3")
        mp3_buffer.seek(0)
        
        transcription_response = client.audio.transcriptions.create(
            model='whisper-large-v3', # Using the turbo variant as in original
            file=("chunk.mp3", mp3_buffer),
            response_format='verbose_json',
            # language="es", # Optional: specify language if known, otherwise auto-detect
            # prompt="PROMPT", # Optional: provide a prompt
            temperature=0.0 # Optional: set temperature
        )
        
        # The response from Groq client should be a model instance if it uses Pydantic internally,
        # or a dict. We parse it into our Pydantic model for validation and structured access.
        # Assuming transcription_response is an object that can be converted to dict 
        # or is already a dict-like structure. For Groq, it's an object with attributes.
        # The `transcription_response` object itself is what we need.
        # Let's assume it has .task, .language, .duration, .text, .segments attributes
        
        # Create a dictionary for Pydantic validation
        try:
            response_dict = {
                "task": transcription_response.task,
                "language": transcription_response.language,
                "duration": transcription_response.duration,
                "text": transcription_response.text,
                "segments": [
                    {
                        "id": seg['id'],
                        "seek": seg['seek'],
                        "start": seg['start'],
                        "end": seg['end'],
                        "text": seg['text'],
                        "tokens": seg['tokens'],
                        "temperature": seg['temperature'],
                        "avg_logprob": seg['avg_logprob'],
                        "compression_ratio": seg['compression_ratio'],
                        "no_speech_prob": seg['no_speech_prob'],
                        "transient": seg.get('transient') # Use .get for optional transient
                    } for seg in transcription_response.segments
                ]
            }
            if hasattr(transcription_response, 'words') and transcription_response.words is not None:
                 response_dict["words"] = transcription_response.words


            chunk_data = WhisperVerboseJSON(**response_dict)

            if i == 0: # First chunk
                detected_language = chunk_data.language
            
            for seg in chunk_data.segments:
                # Adjust segment times to be absolute for the whole audio
                adjusted_seg = seg.model_copy() # Use model_copy for Pydantic v2
                adjusted_seg.start += total_duration_processed
                adjusted_seg.end += total_duration_processed
                all_segments.append(adjusted_seg)
            
            full_text_parts.append(chunk_data.text.strip())
            total_duration_processed += chunk_data.duration # Add actual duration of the processed chunk

            print(f"Chunk {chunk_idx}/{total_chunks} transcrito. Duración acumulada: {total_duration_processed:.2f}s")

        except Exception as e:
            print(f"Error processing chunk: {e}")
            # Fallback for this chunk if parsing fails
            if hasattr(transcription_response, 'text'):
                 full_text_parts.append(transcription_response.text.replace('\\n', ' ').strip())
            # total_duration_processed needs to be estimated if chunk_data.duration is not available
            # This could be len(chunk_audio) / 1000.0
            total_duration_processed += len(chunk_audio) / 1000.0


    final_transcription_text = " ".join(full_text_parts).strip()
    
    # Create the final structured output
    final_structured_data = WhisperVerboseJSON(
        task="transcribe", # Overall task
        language=detected_language, # Use language from first chunk or a consensus
        duration=len(audio) / 1000.0, # Total duration of the original audio
        text=final_transcription_text,
        segments=all_segments
    )
    
    output_filename = "transcription_structured.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(final_structured_data.model_dump_json(indent=2, exclude_none=True)) # For Pydantic v2
    
    print(f"Estructura de la transcripción guardada en '{output_filename}'")
    return output_filename

#--------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------

def transcribe_audio_simple(audio_file_path: str) -> str:
    """
    Transcribe un archivo de audio completo y devuelve el texto plano.

    Args:
        audio_file_path (str): La ruta al archivo de audio (MP3, WAV, etc.).

    Returns:
        str: El texto de la transcripción.
    """
    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"El archivo de audio no se encontró en: {audio_file_path}")

    print(f"[Whisper] Iniciando transcripción simple para: {audio_file_path}")

    # No es necesario dividir en chunks para un audio corto de nombres
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        with open(audio_file_path, "rb") as file:
            transcription_response = client.audio.transcriptions.create(
                model='whisper-large-v3',
                file=(os.path.basename(audio_file_path), file.read())
            )
        
        transcript_text = transcription_response.text
        print(f"[Whisper] Transcripción completada.")
        return transcript_text

    except Exception as e:
        print(f"Error al transcribir el audio: {e}")
        return "[Error en la transcripción]"