"""Prompt builders for GPT interactions."""
from typing import Dict, List

Message = Dict[str, str]


def fragment_summary_messages(fragment: str) -> List[Message]:
    system_prompt = (
        "Analiza muy bien el fragmento de la reunion y elabora un resumen ejecutivo que cumple con los siguientes criterios:\n\n"
        "1. Resume todos los temas tratados de forma clara, sin omitir informacion clave.\n"
        "2. Utiliza un lenguaje profesional, neutro y directo.\n"
        "3. Manten el resumen conciso pero completo.\n"
        "4. Presenta los puntos tratados en orden logico o cronologico.\n"
        "5. Usa Markdown para resaltar los puntos importantes, pero sin abusar de el, usalo lo necesario."
    )
    user_prompt = f"Resume el siguiente fragmento de una reunion:\n\n{fragment}\n\nResumen:"
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def fragment_summary_with_context_messages(fragment: str, context: str) -> List[Message]:
    system_prompt = (
        "Analiza la continuacion de la reunion en base al resumen previo y resume el siguiente fragmento, de modo que la informacion se acople de manera coherente al final del resumen anterior.\n\n"
        "El resumen previo es:\n\n\"\"\" \n{contexto} \n\"\"\"\n\n"
        "Ahora, resume el siguiente fragmento y continua de forma coherente usando los siguientes requisitos:\n\n"
        "1. Resume todos los temas tratados de forma clara, sin omitir informacion clave.\n"
        "2. Utiliza un lenguaje profesional, neutro y directo.\n"
        "3. Manten el resumen conciso pero completo.\n"
        "4. Presenta los puntos tratados en orden logico o cronologico.\n"
        "5. NO incluir cosas como \"Resumen ejecutivo de la reunion (continuacion)\" o \"Resumen de la reunion (continuacion)\".\n"
        "6. Usa Markdown para resaltar los puntos importantes, pero sin abusar de el, usalo lo necesario."
    ).format(contexto=context)
    user_prompt = (
        system_prompt
        + "\n\nFragmento:\n{fragmento}\n\nResumen continuado:"
    ).format(fragmento=fragment)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def fragment_summary_final_messages(fragment: str, context: str) -> List[Message]:
    system_prompt = (
        "Analiza muy bien el fragmento de la reunion y elabora un resumen ejecutivo que cumple con los siguientes criterios:\n"
        "1. Resume todos los temas tratados de forma clara, sin omitir informacion clave.\n"
        "2. Identifica y detalla las decisiones tomadas durante la reunion (en el resumen previo).\n"
        "3. Senala los acuerdos, desacuerdos, proximos pasos si se mencionan (en el resumen previo).\n"
        "4. Presenta los puntos tratados en orden logico o cronologico.\n"
        "5. Utiliza un lenguaje profesional, neutro y directo.\n"
        "6. Manten el resumen conciso pero completo.\n"
        "7. Al final, anade la asignacion de tareas y responsables, si existen (en el resumen previo).\n"
        "8. Incluye fechas o plazos si se mencionan (en el resumen previo).\n"
        "9. NO incluir cosas como \"Resumen de la reunion (continuacion)\" o \"Resumen de la reunion (continuacion)\".\n"
        "10. Usa Markdown para resaltar los puntos importantes, pero sin abusar de el, usalo lo necesario.\n\n"
        "El resumen previo es:\n\n\"\"\" \n{contexto} \n\"\"\"\n\n"
        "Ahora, resume el siguiente fragmento final y proporciona la conclusion del acta de la reunion:"
    ).format(contexto=context)
    user_prompt = (
        system_prompt
        + "\n\nFragmento final:\n{fragmento}\n\nResumen final:"
    ).format(fragmento=fragment)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def structured_summary_system_prompt(participants: List[str]) -> str:
    formatted_participants = ", ".join(participants) if participants else "No especificados"
    return f"""\
Eres un asistente experto en analisis y sintesis de reuniones empresariales. Tu tarea es generar un resumen formal estructurado en formato JSON a partir de una transcripcion de reunion y una lista de asistentes.
La transcripcion proporcionada contiene **inline timestamps** en formato `[MM:SS]` al inicio de los segmentos de texto relevantes. Debes utilizar estos timestamps para poblar los campos de tiempo en tu respuesta.

**Asistentes:** {formatted_participants}

***REQUISITOS OBLIGATORIOS***
1. Cada entrada en `main_points` **DEBE** tener su contraparte en `detailed_summary` (usando el mismo `id`).  No puede faltar ninguna.
2. `detailed_summary` **no puede estar vacio** y cada item debe incluir al menos **un** elemento en `key_timestamps` con un timestamp valido.
3. Los campos `time` y `start_time` **no pueden ser "00:00"** salvo que realmente la conversacion empiece en 00:00.
4. Devuelve **SOLO** el objeto JSON final, sin comentarios ni texto adicional.
5. El resumen **DEBE** estar en **espanol**.

6.  **Formato del Campo `content` en `detailed_summary`**:
    *   El campo `content` DEBE ser una **UNICA CADENA DE TEXTO (string) en el JSON resultante**.
    *   Dentro de esta unica cadena, incluiras de **2 a 4 vinietas muy detalladas y explicativas**.
    *   Cada vinieta DEBE comenzar con `- ` (guion seguido de un espacio).
    *   Las vinietas multiples DENTRO de la cadena de texto `content` DEBEN estar separadas por el caracter de nueva linea (`\n`).
    *   **NO generes una lista de strings JSON (ej: `[\"vinieta1\", \"vinieta2\"]`) para el campo `content`.** Debe ser una sola string (ej: `"- vinieta1\n- vinieta2"`).
    *   Cada vinieta debe contener informacion ESPECIFICA y UNICA de ese punto. **NO repitas** la misma informacion en diferentes puntos. Si un contenido ya fue mencionado antes, **omite** volver a incluirlo.
    *   Usa Markdown para resaltar palabras clave (**negritas** o *cursivas*) cuando aporte claridad.

7.  **Tareas y Objetivos (`tasks_and_objectives`) - CRÍTICO**:
    *   **SIEMPRE** incluye una lista `tasks_and_objectives` con elementos que representen tareas u objetivos mencionados en la reunion.
    *   Busca activamente en la transcripcion cualquier mencion de: acciones a realizar, tareas asignadas, compromisos adquiridos, objetivos planteados, proximos pasos, seguimientos pendientes, entregas acordadas.
    *   Cada elemento debe ser un objeto con SOLO estos campos: `task` (string, el nombre/título de la tarea u objetivo) y `description` (string, breve descripcion que incluya responsable si se menciona).
    *   Extrae esta informacion del contenido de la transcripcion de forma exhaustiva.
    *   Si realmente no hay tareas u objetivos explicitos, genera al menos objetivos implicitos basados en los temas discutidos.
    *   NUNCA dejes esta lista completamente vacia si hay contenido relevante en la reunion.

Sigue rigurosamente la estructura especificada.
"""


def structured_summary_dynamic_prompt(final_timestamp: str, total_minutes: int, minimum_points: int) -> str:
    return (
        "La duracion total detectada de la reunion es de aproximadamente {minutes} minutos (timestamp final: {timestamp}). Debes generar **al menos {min_points} puntos principales** en 'main_points', distribuidos a lo largo de toda la linea de tiempo, de modo que el ultimo 'main_points.time' no este a mas de 2 minutos de {timestamp}. Asegurate de que cada punto principal tenga su correspondiente entrada detallada en 'detailed_summary'."
    ).format(minutes=total_minutes, timestamp=final_timestamp, min_points=minimum_points)


def followup_structured_prompt_with_context(previous_points: list) -> str:
    """Generate followup prompt with context of what was already covered."""
    if not previous_points:
        return (
            "Genera SOLO los campos 'main_points', 'detailed_summary' y 'tasks_and_objectives' (sin repetir metadata) para el fragmento siguiente de la reunion. "
            "**IMPORTANTE:** Busca activamente tareas, objetivos, compromisos y acciones acordadas en este fragmento para incluir en 'tasks_and_objectives'. "
            "Asegurate de seguir la misma estructura JSON exacta."
        )
    
    # Build context of already covered topics
    covered_topics = "\n".join([f"- {p.get('title', '')}" for p in previous_points[-5:]])  # Last 5 points for context
    
    return (
        f"Ya se han cubierto los siguientes temas en fragmentos anteriores:\n{covered_topics}\n\n"
        "Ahora, genera SOLO los campos 'main_points', 'detailed_summary' y 'tasks_and_objectives' (sin repetir metadata) para el fragmento siguiente de la reunion. "
        "**CRITICO:** NO repitas ni reformules los temas ya cubiertos arriba. Enfocate UNICAMENTE en informacion NUEVA y diferente de este fragmento. "
        "**IMPORTANTE:** Busca activamente tareas, objetivos, compromisos y acciones acordadas en este fragmento para incluir en 'tasks_and_objectives'. "
        "Asegurate de seguir la misma estructura JSON exacta."
    )


def structured_summary_user_prompt(chunk_text: str) -> str:
    return f"Genera/continúa el acta estructurado en JSON para el siguiente fragmento con timestamps:\n\n{chunk_text}\n\nJSON:"


def participant_extraction_messages(transcript_text: str) -> List[Message]:
    system_prompt = (
        "Eres un asistente experto en analizar textos. Tu unica tarea es leer la siguiente transcripcion y extraer los nombres de las personas que se presentan. "
        "Busca patrones como 'Soy [Nombre]', 'Mi nombre es [Nombre]', o simplemente nombres mencionados en un contexto de presentacion. Ignora cualquier otra palabra.\n\n"
        "Devuelve la respuesta como un objeto JSON que contenga una unica clave 'participants' cuyo valor sea una lista de los nombres encontrados."
    )
    user_prompt = (
        "Transcripcion:\n'''\n{transcripcion}\n'''\n\nExtrae los nombres en el formato JSON solicitado."
    ).format(transcripcion=transcript_text)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
