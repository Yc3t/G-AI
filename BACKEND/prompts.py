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

7.  **NO generes tareas ni objetivos**:
    *   El campo `tasks_and_objectives` puede estar vacio o tener una lista vacia `[]`.
    *   NO es necesario extraer tareas, acciones ni compromisos en el resumen estructurado (esto se hace en las actas).

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
            "Genera SOLO los campos 'main_points' y 'detailed_summary' (sin repetir metadata ni tasks_and_objectives) para el fragmento siguiente de la reunion. "
            "Asegurate de seguir la misma estructura JSON exacta."
        )
    
    # Build context of already covered topics
    covered_topics = "\n".join([f"- {p.get('title', '')}" for p in previous_points[-5:]])  # Last 5 points for context
    
    return (
        f"Ya se han cubierto los siguientes temas en fragmentos anteriores:\n{covered_topics}\n\n"
        "Ahora, genera SOLO los campos 'main_points' y 'detailed_summary' (sin repetir metadata ni tasks_and_objectives) para el fragmento siguiente de la reunion. "
        "**CRITICO:** NO repitas ni reformules los temas ya cubiertos arriba. Enfocate UNICAMENTE en informacion NUEVA y diferente de este fragmento. "
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


def minutes_generation_system_prompt(participants: List[str]) -> str:
    """System prompt for one-shot minutes generation with detailed sections."""
    formatted_participants = ", ".join(participants) if participants else "No especificados"
    return f"""\
Eres un asistente experto en analisis de reuniones. Tu tarea es generar el acta de reunion (minutes) completa y detallada en formato JSON a partir de una transcripcion.

**Asistentes:** {formatted_participants}

La transcripcion contiene **inline timestamps** en formato `[MM:SS]` que debes usar para los campos de tiempo.

**REQUISITOS OBLIGATORIOS:**

1. **Objetivo (`objective`)**:
   - Sintetiza en 1-3 frases el objetivo principal de la reunion.
   - Debe ser claro, conciso y profesional.

2. **Metadatos (`metadata`)**:
   - `title`: Titulo descriptivo y profesional de la reunion.
   - `participants`: Lista de nombres de los participantes (usar la lista proporcionada).

3. **Puntos Principales (`main_points`)**:
   - Lista de 5-10 puntos clave, distribuidos a lo largo de toda la reunion.
   - Cada punto:
     * `id`: identificador unico (ej: "point_1", "point_2")
     * `title`: titulo conciso (max 12 palabras)
     * `time`: timestamp "MM:SS" (NUNCA "00:00" salvo que sea el inicio real)
   - Cubrir toda la duracion; el ultimo punto debe estar cerca del final.

4. **Detalles de Puntos (`details`)** - **MUY IMPORTANTE**:
   - Objeto cuyas claves son los `id` de `main_points`.
   - Cada entrada debe tener:
     * `title`: mismo titulo del punto principal
     * `content`: **UNA SOLA CADENA** con viñetas detalladas del contenido tratado en ese punto:
       - Cada viñeta empieza con `- ` (guion + espacio)
       - Se permiten subviñetas SOLO si aportan contexto crítico (max 1 por viñeta)
       - **Solo 2 o 3 viñetas por punto**, cada una de 1 frase concisa y sin redundancias
       - Incluye datos especificos (numeros, decisiones, incidencias), pero evita narrativas largas
       - Usa formato profesional y tecnico cuando corresponda
       - Separa las viñetas con saltos de linea: `\\n`
   - NO menciones nombres propios ni frases como “Jeff dijo” o “María comentó”; describe los hechos de manera impersonal (“se acordó”, “el equipo técnico informó”).
   - El `content` debe ser similar al ejemplo del usuario: detallado, estructurado, con subapartados si es necesario.

5. **Tareas y Objetivos (`tasks_and_objectives`)**:
   - Lista exhaustiva de todas las acciones, tareas, compromisos y objetivos acordados.
   - Busca activamente: acciones a realizar, compromisos, proximos pasos, seguimientos, entregas.
   - Cada elemento:
     * `task`: nombre/titulo de la tarea (string conciso)
      * `description`: descripcion detallada redactada de forma impersonal, sin mencionar nombres propios.
   - Si no hay tareas explicitas, genera objetivos implicitos.
   - NUNCA dejes vacia esta lista si hay contenido relevante.

**FORMATO DE SALIDA:**
- Devuelve SOLO un objeto JSON valido.
- NO incluyas comentarios ni texto adicional.
- El acta DEBE estar en **espanol**.
- El campo `content` en `details` debe ser UNA CADENA con viñetas separadas por `\\n`, NO una lista JSON.

Estructura JSON esperada:
```json
{{
  "objective": "string",
  "metadata": {{
    "title": "string",
    "participants": ["string"]
  }},
  "main_points": [
    {{
      "id": "string",
      "title": "string",
      "time": "MM:SS"
    }}
  ],
  "details": {{
    "point_1": {{
      "title": "string",
      "content": "- Detalle principal 1\\n  - Subdetalle especifico\\n- Detalle principal 2\\n- Detalle principal 3"
    }}
  }},
  "tasks_and_objectives": [
    {{
      "task": "string",
      "description": "string"
    }}
  ]
}}
```
"""


def minutes_generation_user_prompt(transcript_text: str) -> str:
    """User prompt for minutes generation."""
    return f"Genera el acta de reunion (minutes) en formato JSON para la siguiente transcripcion con timestamps:\n\n{transcript_text}\n\nJSON:"


def minutes_details_messages(point_title: str, segment_text: str) -> List[Message]:
    """Prompt to generate detailed bullet content for a specific main point from a transcript segment."""
    system_prompt = (
        "Genera contenido DETALLADO para el apartado de 'details' de un punto principal del acta.\n"
        "REQUISITOS:\n"
        "- Devuelve SOLO una cadena de texto con viñetas, NO JSON.\n"
        "- Cada viñeta empieza con '- ' (guion + espacio).\n"
        "- Solo 2 o 3 viñetas; cada una debe ser una frase breve y directa.\n"
        "- Subviñetas solo si son imprescindibles (máximo una por viñeta).\n"
        "- NO incluyas nombres propios ni frases como 'X dijo'; describe todo de forma impersonal.\n"
        "- Incluye numeros, decisiones, incidencias, propuestas, cuando aparezcan en el segmento.\n"
        "- Lenguaje profesional en español."
    )
    user_prompt = (
        f"Título del punto: {point_title}\n\n"
        f"Segmento de la transcripción (con timestamps):\n''' \n{segment_text}\n'''\n\n"
        "Devuelve SOLO la cadena de viñetas:"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
