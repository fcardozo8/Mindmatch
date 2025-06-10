from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId # Necesario para buscar por ID
import datetime # Para manejar fechas

# URL de conexión a tu base de datos MongoDB local
MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "mindmatch_db"

def get_database():
    """
    Establece y devuelve una conexión a la base de datos MongoDB.
    """
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ismaster') # Prueba la conexión
        db = client[DATABASE_NAME]
        print(f"Conexión exitosa a la base de datos '{DATABASE_NAME}' en MongoDB.")
        return db
    except ConnectionFailure as e:
        print(f"Error de conexión a MongoDB: {e}")
        print("Asegúrate de que MongoDB esté corriendo en el puerto 27017 y sea accesible.")
        return None
    except Exception as e:
        print(f"Ocurrió un error inesperado al conectar a MongoDB: {e}")
        return None

# --- Métodos CRUD para Candidatos ---

def add_candidato(candidato_data):
    """
    Agrega un nuevo candidato a la colección 'candidatos'.
    :param candidato_data: Diccionario con la información del candidato.
                           Se añadirá 'fecha_registro' si no existe.
    :return: El ID del documento insertado o None si hay un error.
    """
    db = get_database()
    if db is None:
        return None

    candidatos_collection = db.candidatos
    if "fecha_registro" not in candidato_data:
        candidato_data["fecha_registro"] = datetime.datetime.now() # Añade fecha de registro

    try:
        result = candidatos_collection.insert_one(candidato_data)
        print(f"Candidato '{candidato_data.get('nombre', 'Desconocido')}' agregado con ID: {result.inserted_id}")
        return str(result.inserted_id) # Convertir ObjectId a string para facilitar su uso
    except Exception as e:
        print(f"Error al agregar candidato: {e}")
        return None

def get_candidatos(query=None):
    """
    Recupera candidatos de la colección 'candidatos'.
    :param query: Un diccionario para filtrar los candidatos (opcional).
                  Ej: {"habilidades": "Python"}.
    :return: Una lista de diccionarios de candidatos.
    """
    db = get_database()
    if db is None:
        return []

    candidatos_collection = db.candidatos
    try:
        if query:
            return list(candidatos_collection.find(query))
        else:
            return list(candidatos_collection.find())
    except Exception as e:
        print(f"Error al recuperar candidatos: {e}")
        return []

def get_candidato_by_id(candidato_id):
    """
    Recupera un candidato específico por su ID.
    :param candidato_id: El ID (string) del candidato.
    :return: Diccionario del candidato o None si no se encuentra o hay un error.
    """
    db = get_database()
    if db is None:
        return None

    candidatos_collection = db.candidatos
    try:
        return candidatos_collection.find_one({"_id": ObjectId(candidato_id)})
    except Exception as e:
        print(f"Error al recuperar candidato por ID {candidato_id}: {e}")
        return None

def update_candidato(candidato_id, update_data):
    """
    Actualiza la información de un candidato existente.
    :param candidato_id: El ID (string) del candidato a actualizar.
    :param update_data: Diccionario con los campos a actualizar.
    :return: True si la actualización fue exitosa, False en caso contrario.
    """
    db = get_database()
    if db is None:
        return False

    candidatos_collection = db.candidatos
    try:
        result = candidatos_collection.update_one(
            {"_id": ObjectId(candidato_id)},
            {"$set": update_data}
        )
        if result.modified_count > 0:
            print(f"Candidato con ID {candidato_id} actualizado exitosamente.")
            return True
        else:
            print(f"No se encontró el candidato con ID {candidato_id} o no se realizaron cambios.")
            return False
    except Exception as e:
        print(f"Error al actualizar candidato con ID {candidato_id}: {e}")
        return False

def delete_candidato(candidato_id):
    """
    Elimina un candidato de la colección 'candidatos'.
    :param candidato_id: El ID (string) del candidato a eliminar.
    :return: True si la eliminación fue exitosa, False en caso contrario.
    """
    db = get_database()
    if db is None:
        return False

    candidatos_collection = db.candidatos
    try:
        result = candidatos_collection.delete_one({"_id": ObjectId(candidato_id)})
        if result.deleted_count > 0:
            print(f"Candidato con ID {candidato_id} eliminado exitosamente.")
            return True
        else:
            print(f"No se encontró el candidato con ID {candidato_id}.")
            return False
    except Exception as e:
        print(f"Error al eliminar candidato con ID {candidato_id}: {e}")
        return False

# --- Bloque de prueba de los métodos CRUD ---
if __name__ == "__main__":
    db = get_database()
    if db is not None:
        print("\n--- Probando métodos CRUD para Candidatos ---")

        # 1. Crear un candidato
        print("\n--> Creando un nuevo candidato:")
        nuevo_candidato = {
            "nombre": "Ana García",
            "email": "ana.garcia@example.com",
            "telefono": "+54911-XXXX-YYYY",
            "habilidades": ["Java", "Spring Boot", "AWS"],
            "experiencia": [{"empresa": "Globant", "rol": "Desarrollador Java", "años": 4}],
            "educacion": [{"institucion": "ITBA", "titulo": "Ingeniería Informática"}],
            "curriculum_path": "/path/to/ana_garcia_cv.pdf"
        }
        candidato_id = add_candidato(nuevo_candidato)
        if candidato_id:
            print(f"ID del candidato agregado: {candidato_id}")

            # 2. Leer todos los candidatos
            print("\n--> Leyendo todos los candidatos:")
            candidatos = get_candidatos()
            for cand in candidatos:
                print(cand)

            # 3. Leer un candidato por ID
            print(f"\n--> Leyendo candidato por ID: {candidato_id}")
            candidato_recuperado = get_candidato_by_id(candidato_id)
            if candidato_recuperado:
                print("Candidato recuperado:", candidato_recuperado)
            else:
                print("Candidato no encontrado.")

            # 4. Actualizar un candidato
            print(f"\n--> Actualizando candidato con ID: {candidato_id}")
            update_data = {"telefono": "+54911-5555-6666", "habilidades": ["Java", "Spring Boot", "AWS", "Docker"]}
            if update_candidato(candidato_id, update_data):
                # Verificar la actualización
                print("\n--> Candidato actualizado (verificando):")
                print(get_candidato_by_id(candidato_id))

            # 5. Eliminar un candidato
            print(f"\n--> Eliminando candidato con ID: {candidato_id}")
            if delete_candidato(candidato_id):
                print("\n--> Candidatos restantes después de la eliminación:")
                print(get_candidatos())
        else:
            print("No se pudo agregar el candidato, omitiendo pruebas CRUD.")
    else:
        print("No se pudo establecer la conexión a la base de datos para probar los métodos CRUD.")