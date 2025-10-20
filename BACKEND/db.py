import os
from typing import Any
from pymongo.database import Database
from pymongo import MongoClient
from pymongo.cursor import Cursor
from datetime import datetime
from bson.objectid import ObjectId 

db_hostname: str = os.getenv('DB_HOSTNAME', "127.0.0.1")
client: MongoClient[dict[str, Any]] = MongoClient(db_hostname, 27017)
db: Database[dict[str,Any]] = client.basededatos

def create_coleccion_reuniones(db: Database) -> None:
    try:
        db.create_collection("reuniones")
    except Exception as e:
        print(f"Error al crear la colección 'reuniones': {e}")

    reunion_validador: dict = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["id", "titulo", "fecha_de_subida"],
            "properties": {
                "id": {
                    "bsonType": "string",
                    "description": "Id en forma de string obligatorio"
                },
                "titulo": {
                    "bsonType": "string",
                    "description": "Título de la reunión obligatorio"
                },
                "participants": {
                    "bsonType": "array",
                    "description": "Participantes con nombre y email opcional",
                    "items": {
                        "bsonType": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"bsonType": "string", "description": "Nombre del participante"},
                            "email": {"bsonType": ["string", "null"], "description": "Email del participante (opcional)"}
                        }
                    }
                },
                "participantes": {
                    "bsonType": ["array", "null"],
                    "description": "Compatibilidad: lista de nombres de participantes",
                    "items": {"bsonType": "string"}
                },
                "audio_path": {
                    "bsonType": ["string", "null"],
                    "description": "Ruta del audio de la reunión"
                },
                "transcripcion": {
                    "bsonType": ["string", "null"],
                    "description": "Transcripción de la reunión"
                },
                "fecha_de_subida": {
                    "bsonType": ["date", "string"],
                    "description": "Fecha de subida de la reunión"
                },
                "resumen": {
                    "bsonType": ["string", "null"],
                    "description": "Resumen estructurado de la reunión"
                }
            }
        }
    }

    try:
        db.command("collMod", "reuniones", validator=reunion_validador)
    except Exception as e:
        print(f"Error al aplicar validador a 'reuniones': {e}")


def create_coleccion_contactos(db: Database) -> None:
    try:
        db.create_collection("contactos")
    except Exception as e:
        # may already exist
        pass
    try:
        db.command("collMod", "contactos", validator={
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name"],
                "properties": {
                    "name": {"bsonType": "string"},
                    "email": {"bsonType": ["string", "null"]}
                }
            }
        })
    except Exception as e:
        print(f"Error al aplicar validador a 'contactos': {e}")

def ensure_indexes(db: Database) -> None:
    try:
        db.contactos.create_index("name", unique=True)
        db.contactos.create_index("email", unique=True, sparse=True)
    except Exception as e:
        print(f"Error creando índices de contactos: {e}")

def upsert_contact(db: Database, name: str, email: str | None) -> dict[str, Any]:
    name_norm = (name or '').strip()
    email_norm = (email or None)
    if email_norm:
        email_norm = email_norm.strip().lower()
    if not name_norm:
        raise ValueError("Nombre requerido")
    db.contactos.update_one({"name": name_norm}, {"$set": {"name": name_norm, "email": email_norm}}, upsert=True)
    return db.contactos.find_one({"name": name_norm}) or {"name": name_norm, "email": email_norm}

def list_contacts(db: Database) -> list[dict[str, Any]]:
    return list(db.contactos.find({}, {"_id": 0}))

def delete_contact(db: Database, name: str) -> int:
    res = db.contactos.delete_one({"name": name})
    return res.deleted_count

def añadir_reunion(db: Database, reunion: dict) -> None:
    try:
        db.reuniones.insert_one(reunion)
        print(f"Reunión '{reunion.get('titulo', 'Sin título')}' añadida correctamente.")
    except Exception as e:
        print(f"Error al añadir reunión: {e}")

def busqueda_por_fecha_mongo(fecha_inicio: datetime, fecha_fin: datetime) -> Cursor[dict[str, Any]]:
    busqueda = db.reuniones.find(
        {
            "fecha_de_subida": {
                "$gte": fecha_inicio,
                "$lte": fecha_fin
            }
        }
    )
    return busqueda

def renombrar_reunion(db: Database, id_reunion: str, nuevo_titulo: str) -> None:
    try:
        db.reuniones.update_one({"_id": ObjectId(id_reunion)}, {"$set": {"titulo": nuevo_titulo}})
        print(f"Reunión con ID '{id_reunion}' renombrada a '{nuevo_titulo}' correctamente.")
    except Exception as e:
        print(f"Error al renombrar reunión con ID '{id_reunion}': {e}")

def eliminar_reunion(db: Database, id_reunion: str) -> None:
    try:
        result = db.reuniones.delete_one({"_id": ObjectId(id_reunion)})
        if result.deleted_count > 0:
            print(f"Reunión con ID '{id_reunion}' eliminada correctamente.")
        else:
            print(f"No se encontró la reunión con ID '{id_reunion}'.")
    except Exception as e:
        print(f"Error al eliminar reunión con ID '{id_reunion}': {e}")
