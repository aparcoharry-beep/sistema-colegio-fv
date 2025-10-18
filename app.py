import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import qrcode
import io
import base64
import os
from sqlalchemy.exc import IntegrityError
import functools, time
import cv2
from pyzbar.pyzbar import decode as pyzbar_decode
from datetime import timezone, time as time_obj

app = Flask(__name__)
app.config['SECRET_KEY'] = 'francois-viete-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///colegio_francois_viete.db'
# --- CONFIGURACIÓN DE BASE DE DATOS PARA PRODUCCIÓN Y DESARROLLO ---
# Esto asegura que la base de datos se cree en una carpeta 'instance' que es estándar en Flask
# y compatible con servicios de despliegue. Funciona tanto en local como en la nube.
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'colegio_francois_viete.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# --- CONFIGURACIÓN DE SESIÓN ---
# Se configura la sesión para que expire después de un tiempo de inactividad.
# Esto soluciona el problema de navegadores como Chrome que restauran
# las sesiones incluso después de cerrar el navegador.
app.config['SESSION_PERMANENT'] = True
# Define el tiempo de vida de la sesión. El usuario deberá volver a iniciar sesión
# si está inactivo por más de 60 minutos.
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)
# Con esto, el tiempo de vida de la sesión se reinicia en cada petición,
# por lo que el usuario no será desconectado mientras esté usando la aplicación.
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# --- Almacenamiento en memoria para eventos de escaneo ---
# Usamos una lista para comunicar eventos de escaneo desde el hilo de la cámara al hilo principal.
SCAN_EVENTS = []

db = SQLAlchemy(app)

# Modelos de la base de datos
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dni = db.Column(db.String(8), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)

# Modelo de estudiantes
class Estudiante(db.Model):


    id = db.Column(db.Integer, primary_key=True)
    codigo_id = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(8))
    fecha_nacimiento = db.Column(db.Date)
    grado = db.Column(db.String(10), nullable=False)
    seccion = db.Column(db.String(10), nullable=False)
    qr_code = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

# Modelo de asistencias
class Asistencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiante.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False) # Columna añadida
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=True)
    asistio = db.Column(db.Boolean, default=False)
    tipo = db.Column(db.String(20), default='manual')  # manual o qr
    turno = db.Column(db.String(10), default='manana')  # manana o tarde
    estudiante = db.relationship('Estudiante', backref=db.backref('asistencias', lazy=True, cascade="all, delete-orphan"))
    usuario = db.relationship('Usuario', backref=db.backref('asistencias_registradas', lazy=True)) # Relación añadida

@app.route('/api/estudiantes/importar-excel', methods=['POST'])
def importar_estudiantes_excel():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No se envió archivo'}), 400
    file = request.files['file']
    try:
        df = pd.read_excel(file, engine='openpyxl')
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al leer Excel: {str(e)}'}), 400
    def norm(s):
        return str(s).strip().lower().replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').replace(' ','_').replace('-','_')
    
    df.columns = [norm(c) for c in df.columns]
    
    # Búsqueda flexible de columnas
    col_nombres = next((c for c in df.columns if 'nombre' in c), None)
    col_apellidos = next((c for c in df.columns if 'apellido' in c), None)
    col_dni = next((c for c in df.columns if 'dni' in c), None)
    col_fecha_nac = next((c for c in df.columns if 'fecha' in c and 'nac' in c), None)
    col_grado = next((c for c in df.columns if 'grado' in c), None)
    col_seccion = next((c for c in df.columns if 'seccion' in c or 'sección' in c), None)

    if not col_nombres or not col_apellidos:
        return jsonify({'success': False, 'message': 'El Excel debe tener columnas de Nombres y Apellidos.'}), 400
    
    agregados = 0
    errores = []
    
    for i, row in df.iterrows():
        nombres = str(row[col_nombres]).strip() if pd.notna(row.get(col_nombres)) else ''
        apellidos = str(row[col_apellidos]).strip() if pd.notna(row.get(col_apellidos)) else ''
        
        if not nombres or not apellidos:
            continue # Si no hay nombre o apellido, se salta la fila

        dni = str(row[col_dni]).strip() if col_dni and pd.notna(row.get(col_dni)) else ''
        fecha_nac_val = row.get(col_fecha_nac)
        grado = str(row[col_grado]).strip() if col_grado and pd.notna(row.get(col_grado)) else ''
        seccion = str(row[col_seccion]).strip() if col_seccion and pd.notna(row.get(col_seccion)) else 'A'

        if not grado:
            grado = request.form.get('grado', '') # Usar el grado del selector si no está en el Excel
        
        try:
            fecha_nac_obj = None
            if pd.notna(fecha_nac_val):
                try:
                    # pd.to_datetime es más robusto para diferentes formatos de fecha
                    fecha_nac_obj = pd.to_datetime(fecha_nac_val).date()
                except (ValueError, TypeError):
                    errores.append(f"{nombres} {apellidos}: Fecha de nacimiento '{fecha_nac_val}' con formato inválido.")
                    fecha_nac_obj = None # Ignorar fecha inválida

            # Lógica de generación de código de estudiante más robusta
            dni_part = dni if dni and dni.isdigit() else ''.join(filter(str.isalnum, nombres))[:3].upper()
            
            nuevo = Estudiante(
                codigo_id = f"{grado[:3].upper()}-{dni_part}-{int(time.time() * 1000) + i}",
                nombre = nombres,
                apellido = apellidos,
                dni = dni,
                fecha_nacimiento = fecha_nac_obj,
                grado = grado,
                seccion = seccion,
                qr_code = '',
                activo = True
            )
            db.session.add(nuevo)
            db.session.commit()
            agregados += 1
        except Exception as e:
            db.session.rollback()
            errores.append(f"{nombres} {apellidos}: {str(e)}")
    return jsonify({'success': True, 'message': f'Importación finalizada. Agregados: {agregados}.', 'agregados': agregados, 'errores': errores})

# --- ENDPOINT: Obtener asistencias por grado, fecha y turno (para frontend) ---
@app.route('/api/asistencia')
def api_asistencia():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    grado = request.args.get('grado')
    fecha = request.args.get('fecha')
    turno = request.args.get('turno', 'manana')
    if not grado or not fecha or not turno:
        return jsonify({'success': False, 'message': 'Faltan parámetros'}), 400
    estudiantes = Estudiante.query.filter_by(grado=grado).order_by(Estudiante.apellido.asc()).all()
    estudiante_ids = [e.id for e in estudiantes]
    asistencias = Asistencia.query.filter(
        Asistencia.estudiante_id.in_(estudiante_ids),
        Asistencia.fecha == fecha,
        Asistencia.turno == turno
    ).all()
    asis_map = {a.estudiante_id: a for a in asistencias}
    lista = []
    for e in estudiantes:
        a = asis_map.get(e.id)
        lista.append({
            'id': e.id,
            'codigo_id': e.codigo_id,
            'nombres': e.nombre,
            'apellidos': e.apellido,
            'dni': e.dni,
            'grado': e.grado,
            'asistio': a.asistio if a else False,
            'hora': a.hora.strftime('%H:%M:%S') if a and a.hora else ''
        })
    return jsonify({'success': True, 'asistencias': lista})

# Endpoint para reportes de asistencia
@app.route('/api/reportes/asistencia')
def api_reportes_asistencia():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    grado = request.args.get('grado')
    fecha_str = request.args.get('fecha')
    turno = request.args.get('turno') # Añadido turno

    if not grado or not fecha_str or not turno:
        return jsonify({'success': False, 'error': 'Faltan parámetros: grado, fecha y turno son requeridos'}), 400

    try:
        fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400

    estudiantes = Estudiante.query.filter_by(grado=grado).order_by(Estudiante.apellido.asc()).all()
    estudiante_ids = [e.id for e in estudiantes]

    # Consultar asistencias para el día, grado y turno especificados
    asistencias_db = Asistencia.query.filter(
        Asistencia.estudiante_id.in_(estudiante_ids),
        Asistencia.fecha == fecha_dt,
        Asistencia.turno == turno
    ).all()
    asistencias_map = {a.estudiante_id: a for a in asistencias_db}

    lista = []
    for e in estudiantes:
        asistencia = asistencias_map.get(e.id)
        lista.append({
            'id': e.id,
            'codigo_id': e.codigo_id,
            'nombres': e.nombre,
            'apellidos': e.apellido,
            'dni': e.dni,
            'grado': e.grado,
            'asistio': asistencia.asistio if asistencia else False,
            'hora': asistencia.hora.strftime('%H:%M:%S') if asistencia and asistencia.hora else '',
            'tipo': asistencia.tipo if asistencia else 'No Registrado',
        })

    return jsonify({
        'success': True,
        'reporte': lista,
        'filtros': {'grado': grado, 'fecha': fecha_str, 'turno': turno}
    })

# Guardar asistencia (manual o QR)
@app.route('/api/asistencia', methods=['POST'])
def guardar_asistencia():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    data = request.get_json()
    asistencias = data.get('asistencias', [])
    fecha = data.get('fecha')
    tipo = data.get('tipo', 'manual')
    turno = data.get('turno', 'manana')
    if not asistencias or not fecha or not turno:
        return jsonify({'success': False, 'message': 'Datos incompletos'}), 400
    fecha_dt = datetime.strptime(fecha, '%Y-%m-%d').date()
    user_id = session['user_id'] # Obtener el ID del usuario de la sesión
    guardadas = 0
    for a in asistencias:
        estudiante_id = a.get('estudiante_id')
        asistio = a.get('asistio', False)
        hora_str = a.get('hora')
        if not estudiante_id:
            continue

        hora_dt = None
        if asistio and hora_str:
            try:
                hora_dt = time_obj.fromisoformat(hora_str)
            except ValueError:
                hora_dt = None # Ignorar hora inválida

        # Buscar si ya existe asistencia para ese estudiante, fecha y turno
        existente = Asistencia.query.filter_by(estudiante_id=estudiante_id, fecha=fecha_dt, turno=turno).first()
        if existente:
            existente.asistio = asistio
            existente.hora = hora_dt
            existente.tipo = tipo # Actualizamos el tipo
            existente.usuario_id = user_id # Actualizamos el usuario que modificó
        else:
            nueva = Asistencia(
                estudiante_id=estudiante_id,
                usuario_id=user_id, # Guardamos el ID del usuario
                fecha=fecha_dt,
                hora=hora_dt,
                asistio=asistio,
                tipo=tipo,
                turno=turno
            )
            db.session.add(nueva)
        guardadas += 1
    db.session.commit()
    return jsonify({'success': True, 'guardadas': guardadas})

# --- ENDPOINT: Registrar asistencia por escaneo de QR ---
@app.route('/api/asistencia/scan', methods=['POST'])
def registrar_asistencia_scan():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401

    data = request.get_json()
    codigo_id = data.get('codigo_id')
    fecha_str = data.get('fecha')
    turno = data.get('turno')

    if not all([codigo_id, fecha_str, turno]):
        return jsonify({'success': False, 'message': 'Datos incompletos (codigo_id, fecha, turno)'}), 400

    estudiante = Estudiante.query.filter_by(codigo_id=codigo_id).first()
    if not estudiante:
        return jsonify({'success': False, 'message': f'Estudiante con código {codigo_id} no encontrado.'}), 404

    fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    user_id = session['user_id']
    hora_actual = datetime.now(timezone.utc).astimezone().time()

    # Buscar si ya existe para no duplicar
    existente = Asistencia.query.filter_by(estudiante_id=estudiante.id, fecha=fecha_dt, turno=turno).first()
    if existente:
        if existente.asistio:
            return jsonify({'success': True, 'message': f'{estudiante.nombre} ya tiene asistencia registrada.'})
        existente.asistio = True
        existente.hora = hora_actual
        existente.tipo = 'qr'
        existente.usuario_id = user_id
    else:
        nueva = Asistencia(estudiante_id=estudiante.id, usuario_id=user_id, fecha=fecha_dt, hora=hora_actual, asistio=True, tipo='qr', turno=turno)
        db.session.add(nueva)
    
    db.session.commit()
    return jsonify({'success': True, 'message': f'Asistencia de {estudiante.nombre} registrada.', 'codigo_id': estudiante.codigo_id})

# Consultar asistencias por grado y fecha
@app.route('/api/asistencia/por-grado', methods=['GET'])
def asistencia_por_grado():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    grado = request.args.get('grado')
    fecha = request.args.get('fecha')
    if not grado or not fecha:
        return jsonify({'success': False, 'message': 'Grado y fecha requeridos'}), 400
    fecha_dt = datetime.strptime(fecha, '%Y-%m-%d').date()
    estudiantes = Estudiante.query.filter_by(grado=grado).order_by(Estudiante.apellido.asc()).all()

    estudiante_ids = [e.id for e in estudiantes]
    asistencias_db = Asistencia.query.filter(
        Asistencia.estudiante_id.in_(estudiante_ids),
        Asistencia.fecha == fecha_dt
    ).all()
    asistencias_map = {a.estudiante_id: a for a in asistencias_db}

    lista = []
    for e in estudiantes:
        asistencia = asistencias_map.get(e.id)
        lista.append({
            'id': e.id,
            'codigo_id': e.codigo_id,
            'nombres': e.nombre,
            'apellidos': e.apellido,
            'dni': e.dni,
            'grado': e.grado,
            'asistio': asistencia.asistio if asistencia else False,
            'hora': asistencia.hora.strftime('%H:%M:%S') if asistencia and asistencia.hora else '',
            'tipo': asistencia.tipo if asistencia else '',
        })
    return jsonify({'success': True, 'asistencias': lista})

# --- MIGRACIÓN AUTOMÁTICA DE password_hash SI FALTA ---
import sqlite3

def ensure_password_hash_column():
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///','')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Verifica si la tabla usuario existe antes de intentar alterarla
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuario'")
    if cur.fetchone():
        cur.execute("PRAGMA table_info(usuario)")
        columns = [row[1] for row in cur.fetchall()]
        if 'password_hash' not in columns:
            cur.execute("ALTER TABLE usuario ADD COLUMN password_hash VARCHAR(128)")
            conn.commit()
    conn.close()

def ensure_asistencia_hora_column():
    # Corregir la ruta a la base de datos. Flask la crea en la carpeta 'instance'.
    # Nos aseguramos de que la carpeta 'instance' exista.
    instance_path = os.path.join(app.root_path, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    
    # Construir la ruta completa al archivo de la base de datos
    db_name = app.config['SQLALCHEMY_DATABASE_URI'].split('/')[-1]
    db_path = os.path.join(instance_path, db_name)
    conn = sqlite3.connect(db_path) # Conectar a la ruta correcta
    cur = conn.cursor()
    # Primero, verificar si la tabla 'asistencia' existe
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='asistencia'")
    if cur.fetchone():
        # Si la tabla existe, verificar si la columna 'hora' está presente
        cur.execute("PRAGMA table_info(asistencia)")
        columns = [row[1] for row in cur.fetchall()]
        if 'hora' not in columns:
            # Añadimos la columna solo si no existe
            cur.execute("ALTER TABLE asistencia ADD COLUMN hora TIME")
            conn.commit()
        if 'tipo' not in columns:
            cur.execute("ALTER TABLE asistencia ADD COLUMN tipo VARCHAR(20) DEFAULT 'manual'")
            conn.commit()
        if 'turno' not in columns:
            cur.execute("ALTER TABLE asistencia ADD COLUMN turno VARCHAR(10) DEFAULT 'manana'")
            conn.commit()
        if 'usuario_id' not in columns:
            # Añadimos la columna y le ponemos un valor por defecto (1) para los registros existentes
            cur.execute("ALTER TABLE asistencia ADD COLUMN usuario_id INTEGER REFERENCES usuario(id) NOT NULL DEFAULT 1")
            conn.commit()
    conn.close() # Asegurarse de cerrar la conexión

# Función para verificar autenticación
def require_auth(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Rutas principales
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('menu'))
    # Si no está autenticado, limpiar sesión por si hay datos corruptos y mostrar login
    session.clear()
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario and check_password_hash(usuario.password_hash, password):
        session.permanent = True  # Usa la configuración de sesión permanente de la app
        session['user_id'] = usuario.id
        session['user_name'] = f"{usuario.nombre} {usuario.apellido}"
        return jsonify({'success': True, 'message': 'Inicio de sesión exitoso', 'redirect': url_for('menu')})
    return jsonify({'success': False, 'message': 'Credenciales incorrectas'})

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'La solicitud no contiene datos JSON válidos.'})

    # Extraer y validar datos
    first_name = data.get('firstName', '').strip()
    last_name = data.get('lastName', '').strip()
    dni = data.get('dni', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not all([first_name, last_name, dni, email, password]):
        return jsonify({'success': False, 'message': 'Todos los campos obligatorios deben ser completados.'})
    if len(dni) != 8 or not dni.isdigit():
        return jsonify({'success': False, 'message': 'El DNI debe tener exactamente 8 dígitos.'})
    if len(password) < 8:
        return jsonify({'success': False, 'message': 'La contraseña debe tener al menos 8 caracteres.'})
    if Usuario.query.filter_by(dni=dni).first():
        return jsonify({'success': False, 'message': 'Ya existe un usuario con este DNI.'})

    if Usuario.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Ya existe un usuario con este email.'})

    try:
        usuario = Usuario(
            dni=dni,
            nombre=first_name,
            apellido=last_name,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(usuario)
        db.session.commit()
        # Iniciar sesión automáticamente tras registro
        session['user_id'] = usuario.id
        session['user_name'] = f"{usuario.nombre} {usuario.apellido}"
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al registrar usuario: {str(e)}'})
    return jsonify({'success': True, 'message': '¡Registro exitoso! Bienvenido/a.', 'redirect': url_for('menu')})



# Nuevo menú visual
@app.route('/dashboard')
@app.route('/menu')
def menu():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    return render_template('menu.html')

# --- VISTA: Generar QR ---
@app.route('/generar-qr')
def generar_qr():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('generar_qr.html')


@app.route('/check_auth')
def check_auth():
    if 'user_id' in session:
        usuario = db.session.get(Usuario, session['user_id'])
        if usuario:
            return jsonify({
                'authenticated': True,
                'user': {
                    'id': usuario.id,
                    'nombre': usuario.nombre,
                    'apellido': usuario.apellido,
                    'email': usuario.email
                }
            })
    return jsonify({'authenticated': False})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# Ruta para cargar/agregar estudiantes
@app.route('/cargar-estudiantes')
def cargar_estudiantes():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('cargar_estudiantes.html')

# Ruta para lista de asistencia
@app.route('/asistencia')
def asistencia():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('asistencia.html')

# Ruta para la página de reportes
@app.route('/reportes')
def reportes():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('reportes.html')


# API para agregar o consultar estudiantes
@app.route('/api/estudiantes', methods=['GET', 'POST'])
def api_estudiantes():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    if request.method == 'POST':
        data = request.get_json()
        estudiantes = data.get('estudiantes', [])
        grado = data.get('grado', '')
        if not estudiantes or not grado:
            return jsonify({'success': False, 'message': 'Datos incompletos'}), 400
        agregados = 0
        errores = []
        for est in estudiantes:
            try:
                fecha_nac_str = est.get('fechaNacimiento')
                fecha_nac_obj = None
                if fecha_nac_str:
                    try:
                        fecha_nac_obj = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        fecha_nac_obj = None # Ignorar si el formato es incorrecto
                # Generar seccion si no viene
                seccion = est.get('seccion', '')
                if not seccion:
                    seccion = 'A'  # Por defecto
                # Generar codigo_id único
                # CORRECCIÓN: Se usa time.time() que requiere importar 'time'.
                # Se hace la generación de ID más robusta y consistente con la de importación.
                dni_part = est.get('dni') if est.get('dni') and est.get('dni').isdigit() else ''.join(filter(str.isalnum, est.get('nombres','')))[:3].upper()
                
                nuevo = Estudiante(
                    codigo_id = f"{grado[:3].upper()}-{dni_part}-{int(time.time() * 1000)}",
                    nombre = est.get('nombres',''),
                    apellido = est.get('apellidos',''),
                    dni = est.get('dni',''),
                    fecha_nacimiento = fecha_nac_obj,
                    grado = grado,
                    seccion = seccion,
                    qr_code = '',
                    activo = True
                )
                db.session.add(nuevo)
                db.session.commit()
                agregados += 1
            except IntegrityError:
                db.session.rollback()
                errores.append(f"Duplicado: {est.get('nombres','')} {est.get('apellidos','')}")
            except Exception as e:
                db.session.rollback()
                errores.append(str(e))
        return jsonify({'success': True, 'agregados': agregados, 'errores': errores})
    # GET: consultar estudiantes (todos o por grado)
    grado = request.args.get('grado')
    query = Estudiante.query
    if grado:
        query = query.filter_by(grado=grado)
    estudiantes = query.order_by(Estudiante.apellido.asc()).all()
    lista = [
        {
            'id': e.id,
            'codigo_id': e.codigo_id,
            'nombres': e.nombre,
            'apellidos': e.apellido,
            'dni': e.dni,
            'grado': e.grado,
            'seccion': e.seccion,
            'fecha_nacimiento': e.fecha_nacimiento.strftime('%Y-%m-%d') if e.fecha_nacimiento else '',
            'activo': e.activo
        }
        for e in estudiantes
    ]
    return jsonify({'success': True, 'estudiantes': lista})

# --- ENDPOINT: Eliminar un estudiante ---
@app.route('/api/estudiantes/<int:estudiante_id>', methods=['DELETE'])
def eliminar_estudiante(estudiante_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401

    estudiante = db.session.get(Estudiante, estudiante_id)
    if not estudiante:
        return jsonify({'success': False, 'message': 'Estudiante no encontrado'}), 404

    try:
        db.session.delete(estudiante)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Estudiante eliminado correctamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al eliminar: {str(e)}'}), 500

# --- ENDPOINT: Eliminar múltiples estudiantes ---
@app.route('/api/estudiantes/bulk-delete', methods=['DELETE'])
def eliminar_estudiantes_bulk():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401

    data = request.get_json()
    ids_a_eliminar = data.get('ids')

    if not ids_a_eliminar or not isinstance(ids_a_eliminar, list):
        return jsonify({'success': False, 'message': 'Se requiere una lista de IDs de estudiantes.'}), 400

    try:
        # Eliminar estudiantes y sus asistencias asociadas (gracias a cascade="all, delete-orphan")
        num_eliminados = Estudiante.query.filter(Estudiante.id.in_(ids_a_eliminar)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({'success': True, 'message': f'Se eliminaron {num_eliminados} estudiantes correctamente.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al eliminar en masa: {str(e)}'}), 500

# Endpoint para obtener estudiantes por grado
@app.route('/api/estudiantes/por-grado', methods=['GET'])
def estudiantes_por_grado():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    grado = request.args.get('grado')
    if not grado:
        return jsonify({'success': False, 'message': 'Grado requerido'}), 400
    estudiantes = Estudiante.query.filter_by(grado=grado).all()
    lista = [{
        'id': e.id,
        'nombres': e.nombre,
        'apellidos': e.apellido,
        'dni': e.dni,
        'grado': e.grado
    } for e in estudiantes]
    return jsonify({'success': True, 'estudiantes': lista})

def inicializar_base_de_datos():
    """Función centralizada para crear y migrar la base de datos."""
    # Asegurarse de que el directorio 'instance' exista antes de crear la BD.
    instance_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    os.makedirs(instance_folder, exist_ok=True)
    with app.app_context():
        db.create_all()
        ensure_password_hash_column()
        ensure_asistencia_hora_column()

# --- INICIO: Transmisión de video con OpenCV ---
def gen_frames(fecha_str=None, turno_str=None, user_id=1):
    """DEPRECADO: Esta función usa OpenCV en el servidor, lo cual no es compatible con la mayoría de servicios en la nube. La lógica de escaneo se ha movido al frontend (asistencia.js)."""
    """Generador de frames de la cámara que también detecta QR."""
    try:
        fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()
    except (ValueError, TypeError):
        fecha_dt = date.today()

    turno = turno_str if turno_str in ['manana', 'tarde'] else ('manana' if datetime.now().time() < time_obj(12, 0) else 'tarde')

    print(f"Iniciando escaneo para Fecha: {fecha_dt}, Turno: {turno}")

    # --- INICIO BLOQUE COMENTADO ---
    # El siguiente código no se ejecutará en producción.
    # Se deja como referencia de la lógica original.
    """
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    last_scan_time = 0
    scan_interval = 0.5  # 0.5 segundos para escaneo rápido y continuo
    last_code = None

    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara.")
        return

    try:
        while True:
            success, frame = cap.read()
            if not success:
                continue  # Si falla un frame, intenta el siguiente sin romper el bucle

            frame = cv2.resize(frame, (800, 500))
            decoded_objects = pyzbar_decode(frame)
            qr_detected = False
            for obj in decoded_objects:
                data = obj.data.decode('utf-8')
                qr_detected = True
                current_time = time.time()
                if data != last_code or (current_time - last_scan_time) > scan_interval:
                    last_code = data
                    last_scan_time = current_time
                    with app.app_context():
                        estudiante = Estudiante.query.filter_by(codigo_id=data).first()
                        hora_actual_time = datetime.now().time()
                        if not estudiante:
                            SCAN_EVENTS.append({'status': 'not_found', 'codigo_id': data})
                        else:
                            existente = Asistencia.query.filter_by(estudiante_id=estudiante.id, fecha=fecha_dt, turno=turno).first()
                            if existente and existente.asistio:
                                SCAN_EVENTS.append({'status': 'duplicate', 'student_name': f'{estudiante.apellido} {estudiante.nombre}', 'codigo_id': estudiante.codigo_id})
                            else:
                                if not existente:
                                    nueva = Asistencia(estudiante_id=estudiante.id, usuario_id=user_id, fecha=fecha_dt, hora=hora_actual_time, asistio=True, tipo='qr', turno=turno)
                                    db.session.add(nueva)
                                else:
                                    existente.asistio = True
                                    existente.hora = hora_actual_time
                                    existente.tipo = 'qr'
                                    existente.usuario_id = user_id
                                db.session.commit()
                                SCAN_EVENTS.append({'status': 'success', 'student_name': f'{estudiante.apellido} {estudiante.nombre}', 'codigo_id': estudiante.codigo_id})
                (x, y, w, h) = obj.rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Si no hay QR, no dibuja nada

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    finally:
        cap.release()
    """
    # --- FIN BLOQUE COMENTADO ---
    # Devolvemos un generador vacío para no romper la ruta si se llama accidentalmente.
    yield b''

@app.route('/video_feed')
@require_auth
def video_feed():
    """Ruta que sirve el stream de video."""
    # Esta ruta ya no es necesaria para el escaneo QR, que ahora se hace en el frontend.
    # Devolvemos una respuesta vacía para evitar errores si el frontend antiguo la llama.
    return Response("El streaming de video ha sido movido al cliente.", mimetype='text/plain')

# --- ENDPOINT para que el frontend consulte los eventos de escaneo ---
# Este endpoint ya no es necesario, ya que el frontend procesará los resultados directamente.
# Lo mantenemos por si se usa en otra parte, pero la nueva lógica no lo necesita.
@app.route('/api/scan_events')
@require_auth
def get_scan_events():
    """Devuelve y limpia la lista de eventos de escaneo."""
    global SCAN_EVENTS
    events = list(SCAN_EVENTS) # Copiar la lista
    SCAN_EVENTS.clear() # Limpiar la lista original
    return jsonify({'events': events})

# --- INICIALIZACIÓN Y ARRANQUE ---
# 1. Inicializar y migrar la base de datos ANTES de iniciar el servidor.
# Esta llamada se ejecuta una vez cuando el proceso de Gunicorn inicia en el servidor.
inicializar_base_de_datos()

if __name__ == '__main__':
    # 2. Iniciar el servidor Flask
    # El servidor en la nube (como Render) ignorará este bloque y usará el comando de Gunicorn.
    app.run(host='0.0.0.0', port=5000, debug=True)