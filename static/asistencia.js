// JS para asistencia.html: carga estudiantes, consulta asistencias, guarda, escanea QR, exporta Excel/PDF


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
    const videoStreamElement = document.getElementById('qrVideo'); // Renombrado para claridad
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

/* === BLOQUE REEMPLAZO: Lector QR robusto con borde y sonidos === */
(function() {
  const video = document.getElementById('qrVideo');
  const canvasProcess = document.getElementById('qrCanvasProcess'); // oculto, para getImageData
  const canvasOverlay = document.getElementById('qrCanvasOverlay'); // visible, para dibujar borde
  const abrirBtn = document.getElementById('abrirQR');
  const cerrarBtn = document.getElementById('cerrarQR');
  const scanSoundEl = document.getElementById('scan-sound');
  const errorSoundEl = document.getElementById('error-sound');

  let stream = null;
  let scanActive = false;
  let lastDetected = null;
  const DEBOUNCE_MS = 1500;

  // Helper: play sound safely
  function safePlay(el){
    if(!el) return;
    try { el.currentTime = 0; el.play().catch(()=>{}); } catch(e){}
  }

  // Ajusta overlay para cubrir exactamente el video en pantalla
  function resizeOverlay(){
    const rect = video.getBoundingClientRect();
    canvasOverlay.style.left = rect.left + 'px';
    canvasOverlay.style.top = rect.top + 'px';
    canvasOverlay.style.width = rect.width + 'px';
    canvasOverlay.style.height = rect.height + 'px';
    canvasOverlay.width = Math.floor(rect.width * (window.devicePixelRatio || 1));
    canvasOverlay.height = Math.floor(rect.height * (window.devicePixelRatio || 1));
    canvasOverlay.getContext('2d').setTransform(window.devicePixelRatio || 1,0,0,window.devicePixelRatio || 1,0,0);
  }

  // Esperar a video listo
  function waitVideoReady(videoEl, timeoutMs=2500){
    return new Promise(resolve => {
      const start = Date.now();
      (function check(){
        if(videoEl.videoWidth && videoEl.videoHeight) return resolve(true);
        if(Date.now() - start > timeoutMs) return resolve(false);
        requestAnimationFrame(check);
      })();
    });
  }

  async function startCameraAndScan(){
    const fecha = fechaSelect.value;
    const turno = turnoSelect.value;
    if (!fecha || !turno) {
      showToast('Por favor, selecciona fecha y turno antes de escanear.', '#e74c3c');
      return;
    }

    if (typeof jsQR === 'undefined') {
      console.error('jsQR no está cargado. Añade: <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"></script>');
      showToast('Falta librería jsQR. Revisa la consola.', '#e74c3c');
      return;
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width:{ideal:1280}, height:{ideal:720} }, audio:false });
      video.srcObject = stream;
      await video.play();
      // esperar dims
      await waitVideoReady(video, 2500);

      // asegurarse que overlay se ajuste al tamaño y posición del video
      resizeOverlay();
      window.addEventListener('resize', resizeOverlay);

      qrModal.style.display = 'flex';
      scanActive = true;
      requestAnimationFrame(scanLoop);
      // desbloqueo de audio (intento silencioso para permitir play)
      safePlay(scanSoundEl); scanSoundEl && scanSoundEl.pause && scanSoundEl.pause();
      safePlay(errorSoundEl); errorSoundEl && errorSoundEl.pause && errorSoundEl.pause();

      showToast("Cámara activada. Apunte el QR al lente.", '#4e54c8');
    } catch (err) {
      console.error("Error al acceder a la cámara:", err);
      showToast("No se pudo acceder a la cámara. Revisa permisos o usa HTTPS.", '#e74c3c');
    }
  }

  function stopCamera(){
    scanActive = false;
    window.removeEventListener('resize', resizeOverlay);
    if(stream) { stream.getTracks().forEach(t=>t.stop()); stream=null; }
    try{ video.pause(); }catch(e){}
    video.srcObject = null;
    // limpiar overlay
    const ctxO = canvasOverlay.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    ctxO.clearRect(0,0,canvasOverlay.width / dpr, canvasOverlay.height / dpr);
    qrModal.style.display = 'none';
  }

  // Dibuja polígono en overlay con color especificado
  // AHORA ESPERA COORDENADAS EN CSS PIXELS (TAMAÑO DE PANTALLA)
  function drawPolygonOnOverlay(location, color='#00FF00', lineWidth=4){
    const ctx = canvasOverlay.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    // Limpiar el canvas antes de dibujar. El re-escalado del contexto se encarga del DPR.
    ctx.clearRect(0, 0, canvasOverlay.width / dpr, canvasOverlay.height / dpr);
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    
    // Las coordenadas ya vienen mapeadas al tamaño de display (CSS pixels)
    const tl = location.topLeftCorner;
    const tr = location.topRightCorner;
    const br = location.bottomRightCorner;
    const bl = location.bottomLeftCorner;

    ctx.moveTo(tl.x, tl.y);
    ctx.lineTo(tr.x, tr.y);
    ctx.lineTo(br.x, br.y);
    ctx.lineTo(bl.x, bl.y);
    ctx.closePath();
    ctx.stroke();
  }

  // Loop principal
  function scanLoop(){
    if(!scanActive) return;

    if(!(video.videoWidth && video.videoHeight)){
      requestAnimationFrame(scanLoop);
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    const vw = video.videoWidth;
    const vh = video.videoHeight;

    const MAX_SIDE = 1000;
    const scale = Math.min(1, MAX_SIDE / Math.max(vw, vh));
    const procW = Math.max(320, Math.floor(vw * scale));
    const procH = Math.max(240, Math.floor(vh * scale));

    canvasProcess.width = Math.floor(procW * dpr);
    canvasProcess.height = Math.floor(procH * dpr);
    canvasProcess.style.width = procW + 'px';
    canvasProcess.style.height = procH + 'px';

    const ctxP = canvasProcess.getContext('2d', { willReadFrequently: true });
    ctxP.setTransform(dpr,0,0,dpr,0,0);
    ctxP.drawImage(video, 0, 0, procW, procH);

    let imageData;
    try {
      imageData = ctxP.getImageData(0, 0, Math.floor(procW * dpr), Math.floor(procH * dpr));
    } catch(e) {
      console.error('getImageData error', e);
      requestAnimationFrame(scanLoop);
      return;
    }

    const code = jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: "attemptBoth" });

    if(code && code.data){
      const codigo = String(code.data).trim();
      const now = Date.now();

      // **CORRECCIÓN DE COORDENADAS**
      // Mapear las coordenadas del QR (que están en el tamaño de la imagen procesada)
      // al tamaño de visualización del video en la pantalla (CSS pixels).
      const rect = video.getBoundingClientRect();
      const ratioX = rect.width / imageData.width;
      const ratioY = rect.height / imageData.height;

      const mappedLocation = {
        topLeftCorner: { x: code.location.topLeftCorner.x * ratioX, y: code.location.topLeftCorner.y * ratioY },
        topRightCorner: { x: code.location.topRightCorner.x * ratioX, y: code.location.topRightCorner.y * ratioY },
        bottomRightCorner: { x: code.location.bottomRightCorner.x * ratioX, y: code.location.bottomRightCorner.y * ratioY },
        bottomLeftCorner: { x: code.location.bottomLeftCorner.x * ratioX, y: code.location.bottomLeftCorner.y * ratioY }
      };

      // Mostrar borde verde inmediatamente (feedback visual)
      drawPolygonOnOverlay(mappedLocation, '#00FF00', 4);

      if(!lastDetected || lastDetected.value !== codigo || (now - lastDetected.time) > DEBOUNCE_MS){
        lastDetected = { value: codigo, time: now };
        sendCodigoToServer(codigo, mappedLocation);
      } else {
        safePlay(errorSoundEl);
        drawPolygonOnOverlay(mappedLocation, '#FF0000', 4);
      }
    } else {
      const ctxO = canvasOverlay.getContext('2d');
      ctxO.clearRect(0, 0, canvasOverlay.width / dpr, canvasOverlay.height / dpr);
    }

    requestAnimationFrame(scanLoop);
  }

  // Envía a backend y procesa respuesta
  async function sendCodigoToServer(codigo_id, location){
    const fecha = fechaSelect.value;
    const turno = turnoSelect.value;
    try {
      const resp = await fetch('/api/asistencia/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codigo_id, fecha, turno })
      });
      const data = await resp.json();

      if(data.status === 'success'){
        safePlay(scanSoundEl);
        showToast(`Asistencia de ${data.student_name || 'estudiante'} registrada.`, '#43e97b');
        drawPolygonOnOverlay(location, '#00FF00', 4);
        setTimeout(()=>{ const ctxO = canvasOverlay.getContext('2d'); const dpr = window.devicePixelRatio || 1; ctxO.clearRect(0,0,canvasOverlay.width/dpr,canvasOverlay.height/dpr); }, 900);
        const estudianteEnLista = window.asistencias.find(a => a.codigo_id === data.codigo_id);
        if (estudianteEnLista && !estudianteEnLista.asistio) {
          estudianteEnLista.asistio = true;
          estudianteEnLista.hora = new Date().toLocaleTimeString('es-PE', { hour12:false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
          renderTabla();
        }
      } else if(data.status === 'duplicate'){
        safePlay(errorSoundEl);
        drawPolygonOnOverlay(location, '#FF0000', 4);
        showToast(`${data.student_name || 'Estudiante'} ya tiene asistencia.`, '#e74c3c');
        setTimeout(()=>{ const ctxO = canvasOverlay.getContext('2d'); const dpr = window.devicePixelRatio || 1; ctxO.clearRect(0,0,canvasOverlay.width/dpr,canvasOverlay.height/dpr); }, 900);
      } else if(data.status === 'not_found'){
        safePlay(errorSoundEl);
        drawPolygonOnOverlay(location, '#FF8C00', 4); // Naranja para no encontrado
        showToast('QR no reconocido.', '#e74c3c');
      } else {
        showToast(data.message || 'Respuesta desconocida del servidor', '#f39c12');
      }
    } catch(e){
      console.error('Error enviando codigo al servidor:', e);
      showToast('Error de conexión al enviar QR.', '#e74c3c');
    }
  }

  // Listeners
  abrirBtn.addEventListener('click', startCameraAndScan);
  cerrarBtn.addEventListener('click', stopCamera);
  document.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') stopCamera(); });
})();
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

        if (!fecha || !turno) {
            showToast('Por favor, selecciona fecha y turno antes de escanear.', '#e74c3c');
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

        // CORRECCIÓN: Se añade la URL correcta al endpoint
        fetch('/api/asistencia', { 
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(payload)
        }).then(r=>r.json()).then(data=>{
            if(data.success){
                showToast('Se guardó correctamente en reportes.', '#43e97b');
                gradoSelect.value = "";
                fechaSelect.value = new Date().toISOString().split('T')[0];
                turnoSelect.value = "manana";
                window.asistencias = [];
                renderTabla();
                mostrarRangoTurno();
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
