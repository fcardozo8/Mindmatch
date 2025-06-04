document.addEventListener('DOMContentLoaded', () => {
    const backendUrl = 'http://localhost:5000';

    const cvUploadInput = document.getElementById('cvUpload');
    const uploadButton = document.getElementById('uploadButton');
    const uploadStatusDiv = document.getElementById('uploadStatus');
    const skillCheckboxesDiv = document.getElementById('skillCheckboxes');
    const filterButton = document.getElementById('filterButton');
    const filteredCvsList = document.getElementById('filteredCvsList');

    // Función para obtener y mostrar las habilidades disponibles del backend
    async function fetchSkills() {
        try {
            const response = await fetch(`${backendUrl}/skills`);
            const skills = await response.json();
            skillCheckboxesDiv.innerHTML = ''; // Limpiar checkboxes existentes
            skills.forEach(skill => {
                const div = document.createElement('div');
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.id = skill;
                checkbox.value = skill;
                const label = document.createElement('label');
                label.htmlFor = skill;
                label.textContent = skill;
                div.appendChild(checkbox);
                div.appendChild(label);
                skillCheckboxesDiv.appendChild(div);
            });
        } catch (error) {
            console.error('Error fetching skills:', error);
        }
    }

    // Subir CVs
    uploadButton.addEventListener('click', async () => {
        const files = cvUploadInput.files;
        if (files.length === 0) {
            uploadStatusDiv.textContent = 'Por favor, selecciona al menos un CV.';
            return;
        }

        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('cvs', files[i]);
        }

        uploadStatusDiv.textContent = 'Subiendo CVs...';
        try {
            const response = await fetch(`${backendUrl}/upload_cvs`, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                uploadStatusDiv.textContent = result.message;
                fetchSkills(); // Refrescar habilidades después de subir CVs
            } else {
                uploadStatusDiv.textContent = 'Error al subir CVs.';
            }
        } catch (error) {
            console.error('Error uploading CVs:', error);
            uploadStatusDiv.textContent = 'Error de conexión al subir CVs.';
        }
    });

    // Filtrar CVs
    filterButton.addEventListener('click', async () => {
        const selectedSkills = Array.from(skillCheckboxesDiv.querySelectorAll('input[type="checkbox"]:checked'))
                                   .map(checkbox => checkbox.value);

        if (selectedSkills.length === 0) {
            alert('Por favor, selecciona al menos una habilidad para filtrar.');
            return;
        }

        filteredCvsList.innerHTML = ''; // Limpiar resultados anteriores
        try {
            const response = await fetch(`${backendUrl}/filter_cvs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ skills: selectedSkills })
            });

            if (response.ok) {
                const filteredCvs = await response.json();
                if (filteredCvs.length > 0) {
                    filteredCvs.forEach(cv => {
                        const li = document.createElement('li');
                        const a = document.createElement('a');
                        a.href = `${backendUrl}/download_cv/${cv.filename}`;
                        a.textContent = cv.original_filename;
                        a.target = "_blank";
                        li.appendChild(a);
                        filteredCvsList.appendChild(li);
                    });
                } else {
                    filteredCvsList.innerHTML = '<li>No se encontraron CVs que coincidan con los filtros seleccionados.</li>';
                }
            } else {
                filteredCvsList.innerHTML = '<li>Error al filtrar CVs.</li>';
            }
        } catch (error) {
            console.error('Error filtering CVs:', error);
            filteredCvsList.innerHTML = '<li>Error de conexión al filtrar CVs.</li>';
        }
    });

    // Cargar habilidades al iniciar la página
    fetchSkills();
});
