// JS para asistencia.html: carga estudiantes, consulta asistencias, guarda, escanea QR, exporta Excel/PDF

// Importar la librería jsQR para el escaneo de códigos QR en el navegador.
import jsQR from "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js";

document.addEventListener('DOMContentLoaded', function() {
    const gradoSelect = document.getElementById('gradoSelect');
    const fechaSelect = document.getElementById('fechaSelect');
    const turnoSelect = document.getElementById('turnoSelect');
    const buscarBtn = document.getElementById('buscarBtn');
    const tableContainer = document.getElementById('asistenciaTableContainer');
    const abrirQRBtn = document.getElementById('abrirQR');
    const qrModal = document.getElementById('qrModal');
    const cerrarQRBtn = document.getElementById('cerrarQR');
    const guardarReporteBtn = document.getElementById('guardarReporteBtn');
    const asistenciaResumen = document.getElementById('asistenciaResumen');
    const scanSound = document.getElementById('scan-sound');
    const errorSound = document.getElementById('error-sound');
    // Elementos para el nuevo escáner de QR en el frontend
    const videoElement = document.getElementById('qrVideo');
    const canvasElement = document.createElement('canvas');
    const canvas = canvasElement.getContext('2d', { willReadFrequently: true });
    let animationFrameId = null;
    window.asistencias = [];

    // --- Toast visual ---
    function showToast(msg, color='#4e54c8') {
        let toast = document.getElementById('toastMsg');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toastMsg';
            toast.style.position = 'fixed';
            toast.style.bottom = '32px';
            toast.style.left = '50%';
            toast.style.transform = 'translateX(-50%)';
            toast.style.background = color;
            toast.style.color = '#fff';
            toast.style.display = 'block';
            toast.style.padding = '14px 32px';
            toast.style.borderRadius = '8px';
            toast.style.fontWeight = 'bold';
            toast.style.fontSize = '1.1rem';
            toast.style.boxShadow = '0 2px 12px rgba(0,0,0,0.15)';
            toast.style.zIndex = 9999;
            toast.style.opacity = 0;
            toast.style.transition = 'opacity 0.3s';
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.style.opacity = 1;
        setTimeout(()=>{ 
            toast.style.opacity = 0; 
            setTimeout(() => { toast.style.display = 'none'; }, 300);
        }, 2200);
    }


    // Set default date to today
    if (fechaSelect) {
        const today = new Date().toISOString().split('T')[0];
        fechaSelect.value = today;
    }

    // --- NUEVA LÓGICA DE CÁMARA CON jsQR (FRONTEND) ---
    let lastScanTime = 0;
    const scanInterval = 2000; // 2 segundos de espera entre escaneos del mismo código

    async function registrarAsistenciaQR(codigoId) {
        const fecha = fechaSelect.value;
        const turno = turnoSelect.value;

        const response = await fetch('/api/asistencia/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ codigo_id: codigoId, fecha, turno })
        });
        const data = await response.json();

        if (data.success) {
            scanSound.play().catch(e => console.error("Error al reproducir sonido:", e));
            showToast(data.message, '#43e97b');
            // Actualizar la tabla en tiempo real
            const estudianteEnLista = window.asistencias.find(a => a.codigo_id === data.codigo_id);
            if (estudianteEnLista && !estudianteEnLista.asistio) {
                estudianteEnLista.asistio = true;
                estudianteEnLista.hora = new Date().toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
                renderTabla();
            }
        } else {
            errorSound.play().catch(e => console.error("Error al reproducir sonido:", e));
            showToast(data.message, data.message.includes('encontrado') ? '#e74c3c' : '#f39c12');
        }
    }

    function tick() {
        if (videoElement.readyState === videoElement.HAVE_ENOUGH_DATA) {
            canvasElement.height = videoElement.videoHeight;
            canvasElement.width = videoElement.videoWidth;
            canvas.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);
            const imageData = canvas.getImageData(0, 0, canvasElement.width, canvasElement.height);
            const code = jsQR(imageData.data, imageData.width, imageData.height, {
                inversionAttempts: "dontInvert",
            });

            if (code) {
                const currentTime = new Date().getTime();
                if (currentTime - lastScanTime > scanInterval) {
                    lastScanTime = currentTime;
                    registrarAsistenciaQR(code.data);
                }
            }
        }
        animationFrameId = requestAnimationFrame(tick);
    }

    async function abrirQRModal() {
        if (!fechaSelect.value || !turnoSelect.value) {
            showToast('Selecciona fecha y turno antes de escanear.', '#e74c3c');
            return;
        }
        qrModal.style.display = 'flex';
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
            videoElement.srcObject = stream;
            videoElement.setAttribute("playsinline", true); // Requerido para iOS
            videoElement.play();
            animationFrameId = requestAnimationFrame(tick);
            showToast("Cámara activada. Apunte el QR al lente.", '#4e54c8');
        } catch (err) {
            console.error("Error al acceder a la cámara: ", err);
            showToast("No se pudo acceder a la cámara.", '#e74c3c');
            cerrarQRModal();
        }
    }

    function cerrarQRModal() {
        qrModal.style.display = 'none';
        if (animationFrameId) {
            cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
        }
        if (videoElement.srcObject) {
            videoElement.srcObject.getTracks().forEach(track => track.stop());
            videoElement.srcObject = null;
        }
    }

    abrirQRBtn.addEventListener('click', abrirQRModal);
    cerrarQRBtn.addEventListener('click', cerrarQRModal);
    // --- FIN QR ESCANEO ---


    function mostrarRangoTurno() {
        const turno = turnoSelect.value;
        let texto = '';
        if (turno === 'manana') texto = 'Turno Mañana: 7:00 AM a 8:30 AM';
        else texto = 'Turno Tarde: 3:00 PM a 4:00 PM';
        asistenciaResumen.innerHTML = `<span style='color:#4e54c8;font-weight:700;'>${texto}</span>`;
    }
    turnoSelect.addEventListener('change', mostrarRangoTurno);
    mostrarRangoTurno();

    buscarBtn.addEventListener('click', function() {
        cargarAsistencias();
    });

    // Función para guardar la lista de asistencia actual en los reportes
    function guardarAReporte() {
        const grado = gradoSelect.value;
        const fecha = fechaSelect.value;
        const turno = turnoSelect.value;

        if (!grado || !fecha || !turno) {
            showToast('Selecciona grado, fecha y turno antes de guardar.', '#e74c3c');
            return;
        }

        const payload = {
            fecha: fecha,
            tipo: 'manual',
            turno: turno,
            asistencias: window.asistencias.map(a => ({
                estudiante_id: a.id,
                asistio: !!a.asistio,
                hora: a.hora || null
            }))
        }; // Faltaba esta llave de cierre

        // El fetch no tenía la URL del endpoint
        fetch('/api/asistencia', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(payload)
        }).then(r=>r.json()).then(data=>{
            if(data.success){
                showToast('Se guardó correctamente en reportes.', '#43e97b');
                // Recargar la lista para reflejar el estado guardado
                cargarAsistencias();
            }else{
                showToast('Error al guardar: ' + (data.message || 'Error desconocido.'), '#e74c3c');
            }
        }).catch(error => {
            console.error('Error en la petición de guardado:', error);
            showToast('Error de conexión. No se pudo guardar.', '#e74c3c');
        });
    }

    // Asignar la función al botón
    guardarReporteBtn.addEventListener('click', guardarAReporte);

    window.renderTabla = function() {
        if (!window.asistencias.length) {
            tableContainer.innerHTML = '<div style="color:#888; padding: 20px; text-align: center;">Seleccione grado, fecha y turno y presione <b>Buscar</b> para cargar la lista de asistencia.</div>';
            return;
        }
        let html = `<table class="asistencia-table">
            <thead><tr>
                <th>#</th><th>Apellido</th><th>Nombre</th><th>DNI</th><th>Asistió</th><th>Hora</th><th>Acciones</th>
            </tr></thead><tbody>`;
        window.asistencias.forEach((a, i) => {
            html += `<tr>
                <td class="orden">${i+1}</td>
                <td class="apellido">${a.apellidos}</td>
                <td class="nombre">${a.nombres}</td>
                <td class="dni">${a.dni||''}</td>
                <td class="check">
                    <input type="checkbox" data-idx="${i}" ${a.asistio ? 'checked' : ''}>
                    <span class="${a.asistio ? 'asistio-label' : 'noasistio-label'}">${a.asistio ? 'Sí' : 'No'}</span>
                </td>
                <td class="hora">${a.hora||''}</td>
                <td><button class="delete-btn" data-id="${a.id}" title="Eliminar estudiante"><i class="fas fa-trash-alt"></i></button></td>
            </tr>`;
        });
        html += '</tbody></table>';
        tableContainer.innerHTML = html;
        // Listeners para check
        tableContainer.querySelectorAll('input[type=checkbox]').forEach(cb => {
            cb.addEventListener('change', function() {
                const idx = this.getAttribute('data-idx');
                window.asistencias[idx].asistio = this.checked;
                window.asistencias[idx].hora = this.checked ? new Date().toLocaleTimeString('es-PE',{hour12:false, hour: '2-digit', minute: '2-digit', second: '2-digit'}) : '';
                renderTabla();
            });
        });
        // Listeners para eliminar
        tableContainer.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async function() {
                const id = this.dataset.id;
                if (confirm('¿Estás seguro de que quieres eliminar a este estudiante? Esta acción es permanente y no se puede deshacer.')) {
                    const resp = await fetch(`/api/estudiantes/${id}`, { method: 'DELETE' });
                    const data = await resp.json();
                    showToast(data.message, data.success ? '#43e97b' : '#e74c3c');
                    if (data.success) cargarAsistencias(); // Recargar la lista
                }
            });
        });
    }


    // --- Cargar estudiantes reales desde backend ---
    async function cargarAsistencias() {
        const grado = gradoSelect.value;
        const fecha = fechaSelect.value;
        const turno = turnoSelect.value;
        if (!grado || !fecha || !turno) {
            window.asistencias = [];
            renderTabla();
            return;
        }
        // Obtener estudiantes reales
        let estudiantes = [];
        try {
            const res = await fetch(`/api/estudiantes?grado=${encodeURIComponent(grado)}`);
            const data = await res.json();
            if (data.success) {
                estudiantes = data.estudiantes;
            }
        } catch (e) {
            estudiantes = [];
        }
        // Obtener asistencias previas para la fecha y turno
        let asistenciasPrevias = {};
        try {
            const res = await fetch(`/api/asistencia?grado=${encodeURIComponent(grado)}&fecha=${encodeURIComponent(fecha)}&turno=${encodeURIComponent(turno)}`);
            const data = await res.json();
            if (data.success && data.asistencias) {
                data.asistencias.forEach(a => {
                    asistenciasPrevias[a.codigo_id] = a;
                });
            }
        } catch (e) {}
        // Unir estudiantes con asistencias
        window.asistencias = estudiantes.map(e => {
            const prev = asistenciasPrevias[e.codigo_id] || {};
            return {
                id: e.id,
                codigo_id: e.codigo_id,
                nombres: e.nombres,
                apellidos: e.apellidos,
                dni: e.dni,
                grado: e.grado,
                asistio: prev.asistio || false,
                hora: prev.hora || ''
            };
        });
        renderTabla();
    }

    // Cargar lista al inicio
    // --- INICIO: Carga automática desde URL ---
    const urlParams = new URLSearchParams(window.location.search);
    const gradoUrl = urlParams.get('grado');
    const fechaUrl = urlParams.get('fecha');
    const turnoUrl = urlParams.get('turno');

    if (gradoUrl && fechaUrl && turnoUrl) {
        gradoSelect.value = gradoUrl;
        fechaSelect.value = fechaUrl;
        turnoSelect.value = turnoUrl;
        
        // Mostrar el rango de turno correcto
        mostrarRangoTurno();
        
        // Cargar automáticamente la lista de asistencia
        cargarAsistencias();
    }
});
