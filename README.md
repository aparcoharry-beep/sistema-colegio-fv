# Sistema de Gestión Escolar - Colegio François Viète

## 🎓 Descripción
Sistema integral de gestión escolar desarrollado para el Colegio François Viète que incluye:
- **Control de Asistencia** con códigos QR
- **Gestión de Estudiantes** (carga individual y masiva desde Excel)
- **Control de Pagos de Pensión** mensual
- **Generación de Reportes** (PDF/Excel)
- **Dashboard** interactivo y moderno

## 🚀 Características Principales

### ✅ Gestión de Usuarios
- Registro e inicio de sesión para personal del colegio
- Validación de DNI (8 dígitos)
- Sistema de roles y permisos

### 👥 Gestión de Estudiantes
- **Carga Individual**: Formulario para agregar estudiantes uno por uno
- **Carga Masiva**: Importación desde archivos Excel
- **Generación Automática de Códigos QR** para cada estudiante
- **Filtrado por Grado**: 1°, 2°, 3°, 4°, 5° grado
- **Secciones**: A, B, C por grado

### 📊 Control de Asistencia
- **Registro Manual**: Marcar asistencia por estudiante
- **Escaneo QR**: Lectura de códigos QR para registro automático
- **Tipos de Registro**: Asistió, Tardanza, Falta
- **Filtros por Fecha y Grado**

### 💰 Control de Pagos
- **Registro de Pagos Mensuales** de pensión
- **Seguimiento por Mes y Año**
- **Estado de Pago**: Pagado/No pagado
- **Reportes de Morosos**

### 📈 Reportes y Estadísticas
- **Reportes Diarios, Semanales y Mensuales**
- **Exportación a PDF y Excel**
- **Dashboard con estadísticas en tiempo real**
- **Gráficos y métricas**

## 🛠️ Tecnologías Utilizadas

### Backend
- **Python 3.8+**
- **Flask** - Framework web
- **SQLAlchemy** - ORM para base de datos
- **SQLite** - Base de datos
- **QRCode** - Generación de códigos QR
- **Pandas** - Procesamiento de Excel
- **ReportLab** - Generación de PDFs

### Frontend
- **HTML5, CSS3, JavaScript**
- **Font Awesome** - Iconos
- **Google Fonts (Poppins)** - Tipografía
- **Diseño Responsivo** - Compatible con móviles

## 📋 Requisitos del Sistema

### Software Necesario
- Python 3.8 o superior
- pip (gestor de paquetes de Python)

### Dependencias
Todas las dependencias están listadas en `requirements.txt`:
```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Werkzeug==2.3.7
qrcode[pil]==7.4.2
pandas==2.1.1
openpyxl==3.1.2
reportlab==4.0.4
Pillow==10.0.1
gunicorn==22.0.0
```

## 🚀 Instalación y Configuración

### 1. Clonar o Descargar el Proyecto
```bash
# Si tienes git instalado
git clone <url-del-repositorio>
cd PYTHON

# O descarga y extrae el archivo ZIP
```

### 2. Crear Entorno Virtual (Recomendado)
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows:
venv\Scripts\activate

# En macOS/Linux:
source venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Ejecutar la Aplicación
```bash
python app.py
```

### 5. Acceder al Sistema
- Abrir navegador web
- Ir a: `http://localhost:5000`
- Registrar un usuario o iniciar sesión

## 📁 Estructura del Proyecto

```
PYTHON/
├── app.py                 # Aplicación principal Flask
├── requirements.txt       # Dependencias de Python
├── index.html            # Página de inicio (login/registro)
├── styles.css            # Estilos para login/registro
├── script.js             # JavaScript para login/registro
├── dashboard.css         # Estilos para dashboard y páginas
├── dashboard.js          # JavaScript para dashboard
├── estudiantes.js        # JavaScript para gestión de estudiantes
├── templates/            # Plantillas HTML
│   ├── index.html        # Login/Registro
│   ├── dashboard.html    # Panel principal
│   ├── estudiantes.html  # Gestión de estudiantes
│   ├── asistencia.html   # Control de asistencia
│   ├── pagos.html        # Control de pagos
│   ├── reportes.html     # Generación de reportes
│   └── qr.html           # Generación de códigos QR
├── static/               # Archivos estáticos (CSS, JS, imágenes)
└── colegio_francois_viete.db  # Base de datos SQLite (se crea automáticamente)
```

## 👤 Uso del Sistema

### 1. Primer Acceso
1. Ir a `http://localhost:5000`
2. Hacer clic en "Regístrate aquí"
3. Completar formulario con:
   - Nombre y apellido
   - DNI (8 dígitos)
   - Email
   - Contraseña
   - Materia que enseña
4. Aceptar términos y condiciones
5. Hacer clic en "Registrarse"

### 2. Iniciar Sesión
1. Usar email y contraseña registrados
2. Opcional: marcar "Recordarme"
3. Hacer clic en "Iniciar Sesión"

### 3. Dashboard Principal
- **Estadísticas**: Ver resumen de estudiantes, asistencias, pagos
- **Acciones Rápidas**: Acceso directo a funciones principales
- **Navegación**: Menú lateral con todas las opciones

### 4. Gestión de Estudiantes
- **Agregar Individual**: Formulario con todos los datos
- **Cargar Excel**: Arrastrar archivo o hacer clic para seleccionar
- **Filtros**: Por grado y búsqueda de texto
- **Acciones**: Ver, editar, generar QR, eliminar

### 5. Control de Asistencia
- **Seleccionar Fecha**: Calendario para elegir día
- **Filtrar por Grado**: Ver estudiantes de grado específico
- **Marcar Asistencia**: Checkbox para cada estudiante
- **Tipos**: Asistió, Tardanza, Falta
- **Guardar**: Automáticamente en base de datos

### 6. Control de Pagos
- **Seleccionar Mes/Año**: Dropdown para período
- **Filtrar por Grado**: Ver estudiantes por grado
- **Marcar Pago**: Checkbox para estado de pago
- **Monto**: Campo opcional para cantidad pagada

### 7. Generación de Reportes
- **Tipo de Reporte**: Diario, Semanal, Mensual
- **Fechas**: Seleccionar rango de fechas
- **Formato**: PDF o Excel
- **Descargar**: Archivo generado automáticamente

## 📊 Formato de Excel para Carga Masiva

El archivo Excel debe contener las siguientes columnas:

| codigo_id | nombre | apellido | grado | seccion | dni | fecha_nacimiento |
|-----------|--------|----------|-------|---------|-----|------------------|
| 1ROA24101 | Juan   | Pérez    | 1ro   | A       | 12345678 | 2015-03-15 |
| 2DOB24102 | María  | García   | 2do   | B       | 87654321 | 2014-07-22 |

### Descripción de Columnas:
- **codigo_id**: Código único del estudiante (obligatorio)
- **nombre**: Nombre del estudiante (obligatorio)
- **apellido**: Apellido del estudiante (obligatorio)
- **grado**: Grado (1ro, 2do, 3ro, 4to, 5to) (obligatorio)
- **seccion**: Sección (A, B, C) (obligatorio)
- **dni**: DNI de 8 dígitos (opcional)
- **fecha_nacimiento**: Fecha en formato YYYY-MM-DD (opcional)

## 🔧 Configuración Avanzada

### Cambiar Puerto de la Aplicación
Editar `app.py` línea final:
```python
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)  # Cambiar puerto aquí
```

### Configurar Base de Datos Externa
Editar `app.py` línea de configuración:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://usuario:password@localhost/colegio'
```

### Personalizar Colegio
Editar en `templates/index.html` y `templates/dashboard.html`:
- Nombre del colegio
- Logo (reemplazar icono Font Awesome)
- Colores (modificar CSS)

## 🐛 Solución de Problemas

### Error: "ModuleNotFoundError"
```bash
# Asegurarse de que el entorno virtual esté activado
# Reinstalar dependencias
pip install -r requirements.txt
```

### Error: "Port already in use"
```bash
# Cambiar puerto en app.py o matar proceso
# En Windows:
netstat -ano | findstr :5000
taskkill /PID <PID_NUMBER> /F

# En macOS/Linux:
lsof -ti:5000 | xargs kill
```

### Error al cargar Excel
- Verificar que el archivo sea .xlsx o .xls
- Comprobar que las columnas tengan los nombres exactos
- Asegurarse de que no haya filas vacías al inicio

### Problemas de Permisos
```bash
# En Windows, ejecutar como administrador
# En macOS/Linux:
sudo pip install -r requirements.txt
```

## 📞 Soporte

Para soporte técnico o consultas:
- Revisar este README
- Verificar logs de la aplicación
- Comprobar que todas las dependencias estén instaladas

## 🔄 Actualizaciones Futuras

### Funcionalidades Planificadas:
- [ ] Sistema de notificaciones por email
- [ ] Aplicación móvil
- [ ] Integración con sistemas de pago
- [ ] Reportes automáticos por email
- [ ] Backup automático de base de datos
- [ ] Sistema de roles más avanzado

## 📄 Licencia

Este proyecto está desarrollado para uso interno del Colegio François Viète.

---

**Desarrollado con ❤️ para el Colegio François Viète**
