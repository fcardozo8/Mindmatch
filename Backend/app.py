import os
from flask import Flask, request, jsonify, send_from_directory
from pymongo import MongoClient
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import re # Para expresiones regulares para la extracción de habilidades

load_dotenv() # Cargar variables de entorno del archivo .env

app = Flask(__name__)

# Configuración de MongoDB
client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
db = client.cv_filter_db # Nombre de la base de datos
cv_collection = db.cvs # Colección para almacenar metadatos de CVs

# Carpeta para guardar los archivos PDF subidos
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', './cv_files')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Límite de 16MB para archivos

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    """Extrae texto de un archivo PDF."""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or "" # Añadir el texto de cada página
    except Exception as e:
        print(f"Error al extraer texto del PDF {pdf_path}: {e}")
    return text

def extract_skills_from_text(text):
    """
    Extrae habilidades de un texto. Esta es una implementación básica.
    Para un sistema más robusto, se recomienda usar NLP (NLTK, spaCy, etc.)
    y un diccionario de habilidades predefinido.
    """
    text = text.lower()
    # Ejemplos de habilidades a buscar. Se pueden expandir.
    # Puedes cargar esto desde un archivo de configuración o una DB.
    possible_skills = [
        "python", "java", "javascript", "react", "angular", "node.js",
        "sql", "mongodb", "docker", "aws", "azure", "gcp", "git",
        "html", "css", "devops", "machine learning", "data science",
        "inglés", "español", "frances", "comunicación", "liderazgo"
    ]
    found_skills = []
    for skill in possible_skills:
        if re.search(r'\b' + re.escape(skill) + r'\b', text): # Búsqueda de palabra completa
            found_skills.append(skill)
    return list(set(found_skills)) # Eliminar duplicados

@app.route('/upload_cvs', methods=['POST'])
def upload_cvs():
    """Permite al reclutador subir uno o más CVs en formato PDF."""
    if 'cvs' not in request.files:
        return jsonify({'message': 'No se encontraron archivos en la solicitud'}), 400

    files = request.files.getlist('cvs')
    if not files:
        return jsonify({'message': 'No se seleccionaron archivos'}), 400

    uploaded_count = 0
    for file in files:
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            # Generar un nombre de archivo único para evitar colisiones
            unique_filename = f"{os.urandom(8).hex()}_{original_filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)

            # Extraer texto y habilidades
            extracted_text = extract_text_from_pdf(filepath)
            identified_skills = extract_skills_from_text(extracted_text)

            # Guardar metadatos en MongoDB
            cv_data = {
                'original_filename': original_filename,
                'filename': unique_filename, # Nombre único para guardar/descargar
                'filepath': filepath,
                'extracted_text': extracted_text,
                'skills': identified_skills,
                'upload_date': datetime.now()
            }
            cv_collection.insert_one(cv_data)
            uploaded_count += 1
        else:
            print(f"Archivo no permitido o inválido: {file.filename}")

    if uploaded_count > 0:
        return jsonify({'message': f'Se subieron {uploaded_count} CV(s) exitosamente.'}), 200
    else:
        return jsonify({'message': 'No se pudo subir ningún CV. Asegúrate de que sean archivos PDF.'}), 400

@app.route('/skills', methods=['GET'])
def get_skills():
    """Devuelve una lista de todas las habilidades únicas encontradas en los CVs."""
    # Se podría mejorar para obtener habilidades de una colección de "habilidades"
    # que se va poblando o se define manualmente.
    all_skills = cv_collection.distinct("skills")
    return jsonify(sorted(all_skills)), 200

@app.route('/filter_cvs', methods=['POST'])
def filter_cvs():
    """Filtra CVs basándose en las habilidades seleccionadas."""
    data = request.get_json()
    required_skills = data.get('skills', [])

    if not required_skills:
        return jsonify({'message': 'No se proporcionaron habilidades para filtrar'}), 400

    # Construir la consulta para MongoDB: buscar CVs que contengan TODAS las habilidades
    query = {"skills": {"$all": required_skills}}
    filtered_cvs = cv_collection.find(query, {'_id': 0, 'original_filename': 1, 'filename': 1}) # Proyectar solo lo necesario

    results = []
    for cv in filtered_cvs:
        results.append(cv)

    return jsonify(results), 200

@app.route('/download_cv/<filename>', methods=['GET'])
def download_cv(filename):
    """Permite descargar un CV específico."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# Sirve los archivos estáticos (HTML, CSS, JS)
@app.route('/')
def index():
    return send_from_directory('Frontend', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('Frontend', path)


if __name__ == '__main__':
    from datetime import datetime
    app.run(debug=True, host='0.0.0.0', port=5000) # Se ejecuta en el puerto 5000 por defecto