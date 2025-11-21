document.addEventListener('DOMContentLoaded', function() {
    const gradoSelect = document.getElementById('gradoSelect');
    const fechaSelect = document.getElementById('fechaSelect');
    const turnoSelect = document.getElementById('turnoSelect');
    const buscarBtn = document.getElementById('buscarBtn');
    const reporteContainer = document.getElementById('reporteContainer');
    const reporteInfo = document.getElementById('reporteInfo');
    const exportPDFBtn = document.getElementById('exportPDFBtn');
    const exportExcelBtn = document.getElementById('exportExcelBtn');
    const actionsContainer = exportPDFBtn.parentElement; // Contenedor de botones

    // Guardar los datos del último reporte generado para poder exportarlos
    let ultimoReporteData = [];
    let ultimosFiltros = {};

    // Poner la fecha de hoy por defecto
    fechaSelect.value = new Date().toISOString().split('T')[0];

    buscarBtn.addEventListener('click', generarReporte);

    async function generarReporte() {
        const grado = gradoSelect.value;
        const fecha = fechaSelect.value;
        const turno = turnoSelect.value;

        if (!grado || !fecha || !turno) {
            alert('Por favor, selecciona grado, fecha y turno.');
            return;
        }

        const url = `/api/reportes/asistencia?grado=${encodeURIComponent(grado)}&fecha=${encodeURIComponent(fecha)}&turno=${encodeURIComponent(turno)}`;

        try {
            const response = await fetch(url);
            const data = await response.json();

            if (data.success) {
                // Guardar datos para exportación
                ultimoReporteData = data.reporte;
                ultimosFiltros = data.filtros;
                renderReporte(data.reporte, data.filtros);
            } else {
                alert('Error al generar reporte: ' + (data.error || 'Error desconocido.'));
                reporteContainer.innerHTML = '';
                reporteInfo.innerHTML = '';
                exportPDFBtn.style.display = 'none';
                exportExcelBtn.style.display = 'none';
                ultimoReporteData = []; // Limpiar en caso de error
            }
        } catch (error) {
            console.error('Error en la petición:', error);
            exportPDFBtn.style.display = 'none';
            exportExcelBtn.style.display = 'none';
            alert('Hubo un error de conexión al generar el reporte.');
            ultimoReporteData = []; // Limpiar en caso de error
        }
    }

    function limpiarBotonEditar() {
        const existingBtn = document.getElementById('editReportBtn');
        if (existingBtn) {
            existingBtn.remove();
        }
    }

    function crearBotonEditar(filtros) {
        limpiarBotonEditar(); // Limpiar botón anterior si existe

        const editBtn = document.createElement('button');
        editBtn.id = 'editReportBtn';
        editBtn.className = 'edit-btn'; // Asignar una clase para estilos
        editBtn.innerHTML = '<i class="fas fa-edit"></i> Editar Lista';
        editBtn.addEventListener('click', () => {
            // Construir la URL para la página de asistencia con parámetros
            const url = `/asistencia?grado=${encodeURIComponent(filtros.grado)}&fecha=${encodeURIComponent(filtros.fecha)}&turno=${encodeURIComponent(filtros.turno)}`;
            window.location.href = url;
        });

        // Insertar el botón de editar antes del de exportar a Excel
        actionsContainer.insertBefore(editBtn, exportExcelBtn);
    }

    function renderReporte(reporteData, filtros) {
        limpiarBotonEditar(); // Limpiar por si acaso

        if (!reporteData || reporteData.length === 0) {
            reporteInfo.textContent = `No se encontraron registros para ${filtros.grado} en la fecha ${filtros.fecha} (${filtros.turno}).`;
            reporteContainer.innerHTML = '';
            exportPDFBtn.style.display = 'none'; // Ocultar botón si no hay datos
            exportExcelBtn.style.display = 'none';
            limpiarBotonEditar();
            return;
        }

        const turnoTexto = filtros.turno === 'manana' ? 'Turno Mañana' : 'Turno Tarde';
        reporteInfo.textContent = `Mostrando reporte para: ${filtros.grado} - ${filtros.fecha} - ${turnoTexto}`;

        let tableHTML = `
            <table class="reporte-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Apellidos</th>
                        <th>Nombres</th>
                        <th>DNI</th>
                        <th>Asistió</th>
                        <th>Hora</th>
                        <th>Tipo de Registro</th>
                    </tr>
                </thead>
                <tbody>
        `;

        reporteData.forEach((item, index) => {
            tableHTML += `
                <tr>
                    <td>${index + 1}</td>
                    <td>${item.apellidos}</td>
                    <td>${item.nombres}</td>
                    <td>${item.dni || ''}</td>
                    <td><span class="${item.asistio ? 'asistio-label' : 'noasistio-label'}">${item.asistio ? 'Sí' : 'No'}</span></td>
                    <td>${item.hora || '-'}</td>
                    <td>${item.tipo}</td>
                </tr>
            `;
        });

        tableHTML += `</tbody></table>`;
        reporteContainer.innerHTML = tableHTML;
        exportPDFBtn.style.display = 'inline-flex'; // Mostrar botones
        exportExcelBtn.style.display = 'inline-flex';
        crearBotonEditar(filtros); // Crear y mostrar el botón de editar
    }

    // Exportar PDF
    exportPDFBtn.addEventListener('click', function() {
        if (!ultimoReporteData.length) return;

        const turnoTexto = ultimosFiltros.turno === 'manana' ? 'Turno Mañana' : 'Turno Tarde';
        const el = document.createElement('div');
        el.innerHTML = `<h2 style='color:#4e54c8;text-align:center;'>Reporte de Asistencia</h2>` +
            `<div style='margin-bottom:8px;font-weight:700;'>Grado: ${ultimosFiltros.grado} | Fecha: ${ultimosFiltros.fecha} | Turno: ${turnoTexto}</div>` +
            `<table border='1' style='width:100%;border-collapse:collapse;font-size:10px;'>` +
            `<thead style='background:#f2f2f2;'><tr style='background:#4e54c8;color:#fff;'><th>#</th><th>Apellidos</th><th>Nombres</th><th>DNI</th><th>Asistió</th><th>Hora</th><th>Tipo Registro</th></tr></thead><tbody>` +
            ultimoReporteData.map((item, i) => `<tr><td>${i + 1}</td><td>${item.apellidos}</td><td>${item.nombres}</td><td>${item.dni || ''}</td><td>${item.asistio ? 'Sí' : 'No'}</td><td>${item.hora || '-'}</td><td>${item.tipo}</td></tr>`).join('') +
            `</tbody></table>`;

        html2pdf().set({
            margin: 10,
            filename: `reporte_asistencia_${ultimosFiltros.grado}_${ultimosFiltros.fecha}_${ultimosFiltros.turno}.pdf`,
            html2canvas: { scale: 2 },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'landscape' }
        }).from(el).save();
    });

    // Exportar Excel
    exportExcelBtn.addEventListener('click', function() {
        if (!ultimoReporteData.length) return;

        const ws_data = [['#', 'Apellidos', 'Nombres', 'DNI', 'Asistió', 'Hora', 'Tipo de Registro']];
        ultimoReporteData.forEach((item, i) => {
            ws_data.push([i + 1, item.apellidos, item.nombres, item.dni || '', item.asistio ? 'Sí' : 'No', item.hora || '-', item.tipo]);
        });
        const wb = XLSX.utils.book_new();
        const ws = XLSX.utils.aoa_to_sheet(ws_data);
        XLSX.utils.book_append_sheet(wb, ws, 'Reporte Asistencia');
        XLSX.writeFile(wb, `reporte_asistencia_${ultimosFiltros.grado}_${ultimosFiltros.fecha}_${ultimosFiltros.turno}.xlsx`);
    });
});