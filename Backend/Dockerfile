# Usar una imagen base oficial de Python
FROM python:3.9-slim-buster

# Establecer el directorio de trabajo en /app
WORKDIR /app

# Copiar los archivos de requerimientos e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de los archivos de la aplicación
COPY . .

# Exponer el puerto en el que Flask se ejecutará
EXPOSE 5000

# Comando para ejecutar la aplicación
CMD ["python", "app.py"]