# Backend/app.py
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import re
from datetime import datetime

# Importar las funciones de conexión y CRUD de db_connection.py
from db_connection import get_database, add_folder, get_folders, delete_folder, \
    assign_cv_to_folder, remove_cv_from_folder, get_cvs_in_folder, get_cv_data_by_filename

load_dotenv()

app = Flask(__name__)
CORS(app)

db = get_database()
if db is None:
    print("¡ADVERTENCIA: No se pudo conectar a la base de datos! La aplicación podría no funcionar correctamente.")

# Inicializar colecciones (solo si db no es None)
cv_collection = db.cvs if db is not None else None
folders_collection = db.folders if db is not None else None # NEW: Colección de carpetas

basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'cv_files')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
    except Exception as e:
        print(f"Error al extraer texto del PDF {pdf_path}: {e}")
    return text

def extract_skills_from_text(text):
    text = text.lower()
    possible_skills = [
        "python", "java", "javascript", "react", "angular", "node.js",
        "sql", "mongodb", "docker", "aws", "azure", "gcp", "git",
        "html", "css", "devops", "machine learning", "data science",
        "inglés", "español", "frances", "comunicación", "liderazgo",
        "scrum", "agile", "sql", "git", "linux", "api", "rest", "graphql",
        "typescript", "kotlin", "swift", "c#", ".net", "php", "ruby", "go",
        "kubernetes", "terraform", "ansible", "jenkins", "ci/cd",
        "power bi", "tableau", "excel", "estadística", "álgebra"
    ]
    found_skills = []
    for skill in possible_skills:
        if re.search(r'\b' + re.escape(skill) + r'\b', text, re.IGNORECASE):
            found_skills.append(skill)
    return list(set(found_skills))

@app.route('/upload_cvs', methods=['POST'])
def upload_cvs():
    if cv_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500

    if 'cvs' not in request.files:
        return jsonify({'message': 'No se encontraron archivos en la solicitud'}), 400

    files = request.files.getlist('cvs')
    if not files:
        return jsonify({'message': 'No se seleccionaron archivos'}), 400

    uploaded_count = 0
    errors = []
    for file in files:
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            unique_filename = f"{os.urandom(8).hex()}_{original_filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            try:
                file.save(filepath)

                extracted_text = extract_text_from_pdf(filepath)
                identified_skills = extract_skills_from_text(extracted_text)

                cv_data = {
                    'original_filename': original_filename,
                    'filename': unique_filename, # Este es el nombre del archivo guardado
                    'filepath': filepath,
                    'extracted_text': extracted_text,
                    'skills': identified_skills,
                    'upload_date': datetime.now(),
                    'Fav': False,
                    'folders': [] # NEW: Inicializa con una lista de carpetas vacía
                }
                cv_collection.insert_one(cv_data)
                uploaded_count += 1
            except Exception as e:
                errors.append(f"Error al procesar '{original_filename}': {e}")
                print(f"Error al procesar archivo {original_filename}: {e}")
        else:
            errors.append(f"Archivo no permitido o inválido: {file.filename}")
            print(f"Archivo no permitido o inválido: {file.filename}")

    response_message = f'Se subieron {uploaded_count} CV(s) exitosamente.'
    if errors:
        response_message += f' Hubo errores con algunos archivos: {", ".join(errors)}'
        return jsonify({'message': response_message, 'errors': errors}), 207
    elif uploaded_count == 0:
        return jsonify({'message': 'No se pudo subir ningún CV. Asegúrate de que sean archivos PDF.'}), 400
    else:
        return jsonify({'message': response_message}), 200

@app.route('/skills', methods=['GET'])
def get_skills():
    if cv_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500
    all_skills = cv_collection.distinct("skills")
    return jsonify(sorted(all_skills)), 200

@app.route('/filter_cvs', methods=['POST'])
def filter_cvs():
    """
    Filtra CVs basándose en las habilidades seleccionadas.
    Si no se proporcionan habilidades, devuelve todos los CVs.
    Incluye las carpetas a las que pertenece cada CV.
    """
    if cv_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500

    data = request.get_json()
    required_skills = data.get('skills', [])

    projection = {
        '_id': 0,
        'original_filename': 1,
        'filename': 1, # Asegúrate de devolver el nombre del archivo guardado
        'skills': 1,
        'folders': 1 # NEW: Incluir el campo 'folders'
    }

    if not required_skills:
        # Si no se proporcionan habilidades, devuelve todos los CVs
        filtered_cvs_cursor = cv_collection.find({}, projection)
    else:
        required_skills_lower = [s.lower() for s in required_skills]
        query = {"skills": {"$all": required_skills_lower}}
        filtered_cvs_cursor = cv_collection.find(query, projection)

    results = []
    for cv in filtered_cvs_cursor:
        results.append(cv)

    return jsonify(results), 200

@app.route('/download_cv/<filename>', methods=['GET'])
def download_cv(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/delete_cv/<filename>', methods=['DELETE'])
def delete_cv(filename):
    if cv_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500

    try:
        cv_data = get_cv_data_by_filename(filename) # Usamos la función de db_connection
        
        if not cv_data:
            return jsonify({'message': 'CV no encontrado en la base de datos.'}), 404

        # Eliminar de la base de datos
        result = cv_collection.delete_one({
            "$or": [
                {"filename": filename},
                {"original_filename": filename}
            ]
        })

        if result.deleted_count > 0:
            try:
                # Intenta eliminar el archivo físico usando el 'filename' guardado
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], cv_data.get('filename'))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Archivo físico eliminado: {file_path}")
            except Exception as e:
                print(f"Error al eliminar archivo físico: {e}")
            
            return jsonify({'message': 'CV eliminado exitosamente.'}), 200
        else:
            return jsonify({'message': 'No se pudo eliminar el CV.'}), 500
            
    except Exception as e:
        print(f"Error al eliminar CV: {e}")
        return jsonify({'message': 'Error interno del servidor.'}), 500

@app.route('/view_cv/<filename>', methods=['GET'])
def view_cv(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({'message': 'Archivo no encontrado'}), 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- NEW: Rutas de API para Carpetas ---

@app.route('/folders', methods=['POST'])
def create_folder_api():
    if folders_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500
    
    data = request.get_json()
    folder_name = data.get('name')

    if not folder_name:
        return jsonify({'message': 'El nombre de la carpeta es requerido.'}), 400
    
    result = add_folder(folder_name)
    if result == "exists":
        return jsonify({'message': f"La carpeta '{folder_name}' ya existe."}), 409 # Conflict
    elif result:
        return jsonify({'message': 'Carpeta creada exitosamente.', 'folder_id': result}), 201
    else:
        return jsonify({'message': 'Error al crear la carpeta.'}), 500

@app.route('/folders', methods=['GET'])
def get_folders_api():
    if folders_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500
    
    folders = get_folders()
    # Convertir ObjectId a string para jsonify
    for folder in folders:
        folder['_id'] = str(folder['_id'])
    return jsonify(folders), 200

@app.route('/folders/<folder_id>', methods=['DELETE'])
def delete_folder_api(folder_id):
    if folders_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500
    
    deleted, message = delete_folder(folder_id)
    if deleted:
        return jsonify({'message': message}), 200
    else:
        status_code = 404 if "not found" in message.lower() else 500
        return jsonify({'message': message}), status_code

@app.route('/cvs/<filename>/assign_to_folder', methods=['POST'])
def assign_cv_to_folder_api(filename):
    if cv_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500
    
    data = request.get_json()
    folder_names = data.get('folder_names')

    if not folder_names or not isinstance(folder_names, list):
        return jsonify({'message': 'Se requiere una lista de nombres de carpeta.'}), 400
    
    success, message = assign_cv_to_folder(filename, folder_names)
    if success:
        return jsonify({'message': message}), 200
    else:
        status_code = 404 if "CV not found" in message else 500
        return jsonify({'message': message}), status_code

@app.route('/filter_cvs_by_folder', methods=['POST'])
def filter_cvs_by_folder_api():
    if cv_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500

    data = request.get_json()
    folder_name = data.get('folder_name')

    if not folder_name:
        return jsonify({'message': 'El nombre de la carpeta es requerido para filtrar.'}), 400
    
    cvs = get_cvs_in_folder(folder_name)
    return jsonify(cvs), 200


# ... [todo tu código previo permanece igual] ...

@app.route('/cvs/<filename>/toggle_favorite', methods=['POST'])
def toggle_favorite(filename):
    if cv_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500

    try:
        # Busca el CV por filename (nombre único con hash)
        cv = cv_collection.find_one({
            "$or": [
                {"filename": filename},
                {"original_filename": filename}
            ]
        })

        if not cv:
            return jsonify({'message': 'CV no encontrado'}), 404

        current_status = cv.get('Fav', False)
        new_status = not current_status

        result = cv_collection.update_one(
            {"_id": cv["_id"]},
            {"$set": {"Fav": new_status}}
        )

        if result.modified_count == 1:
            return jsonify({
                'message': f"Estado de favorito actualizado a {'⭐ Favorito' if new_status else '☆ No favorito'}.",
                'new_status': new_status
            }), 200
        else:
            return jsonify({'message': 'No se pudo actualizar el estado.'}), 500

    except Exception as e:
        print(f"Error al actualizar favorito: {e}")
        return jsonify({'message': 'Error interno al actualizar favorito'}), 500

# --- Rutas para el Frontend (Dashboard y Archivos Estáticos) ---

FRONTEND_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../Frontend/main'))

@app.route('/')
def index():
     # Asumo que la ruta principal sigue sirviendo el index.html
     return send_from_directory(FRONTEND_PATH, 'index.html')

@app.route('/dashboard')
def dashboard():
    # Esta ruta sirve 'dashboard.html' cuando se accede a /dashboard
    return send_from_directory(FRONTEND_PATH, 'dashboard.html')

@app.route('/candidates.html')
def candidates():
    # Esta ruta sirve 'candidates.html' cuando se accede a /candidates.html
    return send_from_directory(FRONTEND_PATH, 'candidates.html')

@app.route('/static/<path:filename>')
def serve_static_files(filename):
    """Sirve archivos estáticos (CSS, JS, imágenes) desde la carpeta 'Frontend/main/static'."""
    return send_from_directory(os.path.join(FRONTEND_PATH, 'static'), filename)

@app.route('/candidates_count', methods=['GET'])
def get_candidates_count():
    if cv_collection is None:
        return jsonify({'message': 'Error: Conexión a la base de datos no establecida.'}), 500
    
    total = cv_collection.count_documents({})
    return jsonify({'total': total}), 200

if __name__ == '__main__':
    if db is not None:
        print("MongoDB está conectado y listo.")
    else:
        print("La conexión a MongoDB falló al iniciar la aplicación.")

    app.run(debug=True, host='0.0.0.0', port=5000)