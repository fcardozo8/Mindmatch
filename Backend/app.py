# Backend/app.py

import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import re
from datetime import datetime
import uuid

# Importar la función get_database desde db_connection.py
# ¡Asegúrate de que tu archivo db_connection.py esté en la misma carpeta Backend/
# y que contenga la función get_database() como me la pasaste previamente!
from db_connection import get_database

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- Configuración de la base de datos usando get_database ---
db = get_database() # Intentar obtener la conexión a la base de datos
cv_collection = None # Inicializar cv_collection a None por si falla la conexión

if db is None:
    print("¡ERROR CRÍTICO: No se pudo conectar a la base de datos! La aplicación no funcionará correctamente.")
    # Podrías considerar una lógica aquí para detener la aplicación o mostrar un mensaje de error en la UI.
else:
    cv_collection = db.cvs # Colección para almacenar metadatos de CVs

# --- Resto de la configuración y funciones ---
basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'cv_files')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

print(f"DEBUG: app.py está ubicado en: {basedir}")
print(f"DEBUG: El directorio de trabajo actual es: {os.getcwd()}")
print(f"DEBUG: UPLOAD_FOLDER configurado como: {app.config['UPLOAD_FOLDER']}")

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
        return None
    return text

def extract_skills(text):
    if text is None:
        return []

    skills_keywords = [
        'python', 'java', 'javascript', 'html', 'css', 'node.js', 'react', 'angular',
        'vue.js', 'sql', 'nosql', 'mongodb', 'mysql', 'postgresql', 'aws', 'azure',
        'gcp', 'docker', 'kubernetes', 'git', 'github', 'gitlab', 'jira', 'agile',
        'scrum', 'linux', 'windows', 'macos', 'networking', 'security',
        'data science', 'machine learning', 'ai', 'deep learning', 'r', 'excel',
        'power bi', 'tableau', 'c++', 'c#', '.net', 'php', 'symfony', 'laravel',
        'ruby', 'rails', 'go', 'kotlin', 'swift', 'android', 'ios', 'unity',
        'figma', 'sketch', 'adobe xd', 'photoshop', 'illustrator', 'ui/ux',
        'testing', 'qa', 'automation', 'devops', 'ci/cd', 'bash', 'shell',
        'api rest', 'graphql', 'xml', 'json', 'microservices', 'cloud', 'blockchain',
        'inteligencia artificial', 'aprendizaje automático', 'ciencia de datos',
        'desarrollo web', 'desarrollo móvil', 'gestión de proyectos', 'metodologías ágiles',
        'comunicación', 'liderazgo', 'resolución de problemas', 'trabajo en equipo',
        'inglés', 'español', 'francés', 'alemán', 'portugués', 'base de datos',
        'redes', 'seguridad informática', 'contabilidad', 'finanzas', 'marketing digital'
    ]
    
    found_skills = []
    text_lower = text.lower()
    for skill in skills_keywords:
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
            found_skills.append(skill)
    return sorted(list(set(found_skills)))


# --- Rutas de la API ---

# Función auxiliar para verificar la conexión a la DB en las rutas
def check_db_connection(f):
    def wrapper(*args, **kwargs):
        if cv_collection is None:
            return jsonify({'message': 'Error: La base de datos no está conectada. Revise el servidor de MongoDB.'}), 500
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__ # Preserva el nombre de la función para Flask
    return wrapper

@app.route('/upload_cvs', methods=['POST'])
@check_db_connection
def upload_cvs():
    if 'cv_files' not in request.files:
        return jsonify({'message': 'No se proporcionaron archivos de CV'}), 400

    files = request.files.getlist('cv_files')
    uploaded_count = 0
    skipped_count = 0
    errors = []

    for file in files:
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4().hex) + '_' + original_filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            try:
                file.save(filepath)
                text = extract_text_from_pdf(filepath)
                
                if text is None:
                    os.remove(filepath)
                    errors.append(f"Error al extraer texto de {original_filename}. Archivo saltado.")
                    skipped_count += 1
                    continue

                skills = extract_skills(text)

                cv_data = {
                    'original_filename': original_filename,
                    'filename': unique_filename,
                    'filepath': filepath,
                    'extracted_text': text,
                    'skills': skills,
                    'upload_date': datetime.utcnow(),
                    'state': True
                }
                cv_collection.insert_one(cv_data)
                uploaded_count += 1
            except Exception as e:
                errors.append(f"Error procesando {original_filename}: {e}")
                skipped_count += 1
        else:
            errors.append(f"Archivo {file.filename} no permitido o no proporcionado.")
            skipped_count += 1
    
    response_message = f"Subida completada. {uploaded_count} CV(s) procesado(s) exitosamente."
    if skipped_count > 0:
        response_message += f" {skipped_count} CV(s) saltado(s) o con errores."
        if errors:
            response_message += f" Errores: {', '.join(errors)}"

    return jsonify({'message': response_message, 'uploaded_count': uploaded_count, 'skipped_count': skipped_count, 'errors': errors}), 200


@app.route('/get_all_skills', methods=['GET'])
@check_db_connection
def get_all_skills():
    all_skills = cv_collection.distinct("skills")
    return jsonify(sorted(all_skills)), 200


@app.route('/filter_cvs', methods=['POST'])
@check_db_connection
def filter_cvs():
    data = request.get_json()
    required_skills = data.get('skills', [])

    if not required_skills:
        return jsonify({'message': 'No se proporcionaron habilidades para filtrar.'}), 400

    query = {
        'skills': {'$all': required_skills},
        'state': True
    }

    filtered_cvs = cv_collection.find(query, {'_id': 0, 'original_filename': 1, 'filename': 1, 'skills': 1, 'state': 1})

    results = []
    for cv in filtered_cvs:
        results.append(cv)

    return jsonify(results), 200


@app.route('/view_cv/<filename>', methods=['GET'])
def view_cv(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    print(f"DEBUG: Intentando servir archivo para visualización: {file_path}")
    if not os.path.exists(file_path):
        print(f"DEBUG: ¡El archivo NO EXISTE en la ruta: {file_path}!")
        return jsonify({'message': 'File not found'}), 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/download_cv/<filename>', methods=['GET'])
def download_cv(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({'message': 'File not found'}), 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/update_cv_state', methods=['POST'])
@check_db_connection
def update_cv_state():
    data = request.get_json()
    filename_to_update = data.get('filename')
    new_state = data.get('state')

    if not filename_to_update or new_state is None or not isinstance(new_state, bool):
        return jsonify({'message': 'Faltan datos o formato incorrecto (filename, state: boolean)'}), 400

    result = cv_collection.update_one(
        {'filename': filename_to_update},
        {'$set': {'state': new_state}}
    )

    if result.modified_count == 1:
        return jsonify({'message': f'Estado del CV {filename_to_update} actualizado a {new_state}.'}), 200
    else:
        return jsonify({'message': f'No se pudo actualizar el estado del CV {filename_to_update}. Posiblemente no encontrado o estado ya el mismo.'}), 404


# --- Rutas para servir archivos estáticos del frontend ---
@app.route('/')
def index():
    return send_from_directory(os.path.join(basedir, '../Frontend/main'), 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(os.path.join(basedir, '../Frontend/main'), path)


if __name__ == '__main__':
    # No es necesario client.admin.command('ping') aquí, ya lo maneja get_database()
    app.run(debug=True)