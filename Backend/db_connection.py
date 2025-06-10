from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
import datetime
import re # ¡Importante! Asegúrate de que esta línea esté presente

MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "mindmatch_db"

def get_database():
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ismaster')
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

# --- Métodos CRUD para CVs (colección 'cvs') ---
# Renombradas para ser más claras y consistentes con 'cvs'
def add_cv_data(cv_data):
    db = get_database()
    if db is None:
        return None
    cv_collection = db.cvs
    if "upload_date" not in cv_data:
        cv_data["upload_date"] = datetime.datetime.now()
    if "folders" not in cv_data: # NEW: Inicializar folders
        cv_data["folders"] = []
    try:
        result = cv_collection.insert_one(cv_data)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error al agregar datos de CV: {e}")
        return None

def get_all_cv_data(query=None):
    db = get_database()
    if db is None:
        return []
    cv_collection = db.cvs
    try:
        if query:
            return list(cv_collection.find(query))
        else:
            return list(cv_collection.find())
    except Exception as e:
        print(f"Error al recuperar datos de CV: {e}")
        return []

def get_cv_data_by_filename(filename):
    db = get_database()
    if db is None:
        return None
    cv_collection = db.cvs
    try:
        return cv_collection.find_one({"$or": [{"filename": filename}, {"original_filename": filename}]})
    except Exception as e:
        print(f"Error al recuperar CV por filename {filename}: {e}")
        return None

def update_cv_data(cv_id, update_data):
    db = get_database()
    if db is None:
        return False
    cv_collection = db.cvs
    try:
        result = cv_collection.update_one(
            {"_id": ObjectId(cv_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error al actualizar CV con ID {cv_id}: {e}")
        return False

def delete_cv_data(filename):
    db = get_database()
    if db is None:
        return False
    cv_collection = db.cvs
    try:
        result = cv_collection.delete_one({"$or": [{"filename": filename}, {"original_filename": filename}]})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error al eliminar CV con filename {filename}: {e}")
        return False

# --- NEW: Métodos CRUD para Carpetas (colección 'folders') ---

def add_folder(folder_name):
    db = get_database()
    if db is None:
        return None
    folders_collection = db.folders
    try:
        # Check if folder already exists (case-insensitive)
        existing_folder = folders_collection.find_one({"name": {"$regex": f"^{re.escape(folder_name)}$", "$options": "i"}})
        if existing_folder:
            return "exists" # Custom return to indicate it already exists
        
        result = folders_collection.insert_one({"name": folder_name, "created_at": datetime.datetime.now()})
        print(f"Carpeta '{folder_name}' agregada con ID: {result.inserted_id}")
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error al agregar carpeta: {e}")
        return None

def get_folders():
    db = get_database()
    if db is None:
        return []
    folders_collection = db.folders
    try:
        # Return _id as ObjectId (will be converted to string by Flask's jsonify), and name
        return list(folders_collection.find({}, {"_id": 1, "name": 1}))
    except Exception as e:
        print(f"Error al recuperar carpetas: {e}")
        return []

def delete_folder(folder_id):
    db = get_database()
    if db is None:
        return False, "Database connection error."
    folders_collection = db.folders
    cv_collection = db.cvs # Get CVs collection to update them
    try:
        folder_to_delete = folders_collection.find_one({"_id": ObjectId(folder_id)})
        if not folder_to_delete:
            return False, "Folder not found."
        
        folder_name = folder_to_delete['name']

        # Remove the folder from all CVs that contain it
        cv_collection.update_many(
            {"folders": folder_name},
            {"$pull": {"folders": folder_name}}
        )
        print(f"Carpeta '{folder_name}' eliminada de los CVs asociados.")

        # Delete the folder itself
        result = folders_collection.delete_one({"_id": ObjectId(folder_id)})
        if result.deleted_count > 0:
            print(f"Carpeta con ID {folder_id} eliminada exitosamente.")
            return True, "Folder deleted successfully."
        else:
            print(f"No se encontró la carpeta con ID {folder_id}.")
            return False, "Folder not found or could not be deleted."
    except Exception as e:
        print(f"Error al eliminar carpeta con ID {folder_id}: {e}")
        return False, f"Internal server error: {e}"

def assign_cv_to_folder(cv_filename, folder_names):
    db = get_database()
    if db is None:
        return False, "Database connection error."
    cv_collection = db.cvs
    try:
        # Find the CV by its filename (unique_filename or original_filename)
        cv_data = cv_collection.find_one(
            {"$or": [{"filename": cv_filename}, {"original_filename": cv_filename}]}
        )
        if not cv_data:
            return False, "CV not found."

        current_folders = set(cv_data.get('folders', []))
        
        # Ensure only existing folder names are added
        existing_folders = [f['name'] for f in get_folders()]
        folders_to_add = [name for name in folder_names if name in existing_folders]
        
        if not folders_to_add:
            return False, "No valid existing folders provided for assignment."

        # Add new folders to the existing set
        updated_folders = list(current_folders.union(set(folders_to_add)))
        
        result = cv_collection.update_one(
            {"_id": cv_data["_id"]},
            {"$set": {"folders": updated_folders}}
        )
        if result.modified_count > 0:
            return True, f"CV '{cv_filename}' assigned to folders: {', '.join(folders_to_add)}."
        else:
            return False, "CV already assigned to these folders or no changes made."
    except Exception as e:
        print(f"Error al asignar CV '{cv_filename}' a carpeta(s): {e}")
        return False, f"Internal server error: {e}"

def remove_cv_from_folder(cv_filename, folder_name):
    db = get_database()
    if db is None:
        return False
    cv_collection = db.cvs
    try:
        result = cv_collection.update_one(
            {"$or": [{"filename": cv_filename}, {"original_filename": cv_filename}]},
            {"$pull": {"folders": folder_name}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error al remover CV '{cv_filename}' de la carpeta '{folder_name}': {e}")
        return False

def get_cvs_in_folder(folder_name):
    db = get_database()
    if db is None:
        return []
    cv_collection = db.cvs
    try:
        # Find CVs where the 'folders' array contains the specific folder_name
        return list(cv_collection.find({"folders": folder_name}, {'_id': 0, 'original_filename': 1, 'filename': 1, 'skills': 1, 'folders': 1}))
    except Exception as e:
        print(f"Error al recuperar CVs en la carpeta '{folder_name}': {e}")
        return []

# No incluyo el bloque `if __name__ == "__main__":` aquí para evitar ejecución de pruebas
# innecesarias cada vez que se importa el módulo. Es para pruebas unitarias si las quieres.