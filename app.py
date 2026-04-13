from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import io
from datetime import datetime
import pandas as pd
import unicodedata
from sqlalchemy import extract, inspect

# --- CONFIGURACIÓN DE LA APP ---
# Se le indica a Flask que busque los templates en el directorio actual ('.')
# Esto soluciona el error TemplateNotFound sin necesidad de mover los archivos.
app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mi_clave_secreta_super_segura')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Límite de 16MB por archivo

# --- CONFIGURACIÓN DE BASE DE DATOS PROFESIONAL (PostgreSQL / Render) ---
# 1. Busca la variable de entorno DATABASE_URL (Provista por Render/Cloud)
# 2. Si no existe, usa una base de datos SQLite local (usuarios_v2.db)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///usuarios_v2.db')

# Corrección de compatibilidad para Render (PostgreSQL requiere el prefijo 'postgresql://')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Opciones del motor para evitar desconexiones en la nube (Production Grade)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 5,
    "pool_timeout": 30,
    "max_overflow": 20
}

# Inicializar extensiones
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- BASE DE DATOS (MODELO) ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(8), unique=True, nullable=False)
    celular = db.Column(db.String(9), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Notificado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombres_apellidos = db.Column(db.String(200))
    dni = db.Column(db.String(15))
    idioma = db.Column(db.String(50))
    codigo_libro = db.Column(db.String(100))
    anio = db.Column(db.String(10))
    fecha_elaboracion = db.Column(db.Date, nullable=True)
    fecha_entrega = db.Column(db.Date, nullable=True)
    correo_entrega = db.Column(db.String(100))
    modalidad = db.Column(db.String(50))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- RUTAS Y LÓGICA ---

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        nombres = request.form.get('nombres')
        apellidos = request.form.get('apellidos')
        dni = request.form.get('dni')
        celular = request.form.get('celular')
        email = request.form.get('email')
        fecha_nacimiento_str = request.form.get('fecha_nacimiento')
        password = request.form.get('password')

        user_exists = User.query.filter((User.dni == dni) | (User.email == email)).first()
        if user_exists:
            flash('El DNI o correo ya está en uso.')
            return redirect(url_for('register'))

        fecha_nacimiento = datetime.strptime(fecha_nacimiento_str, '%Y-%m-%d').date()
        new_user = User(nombres=nombres, apellidos=apellidos, dni=dni, celular=celular, email=email, fecha_nacimiento=fecha_nacimiento)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Cuenta creada. Por favor inicia sesión.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Correo o contraseña incorrectos.')

    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('menu.html')

@app.route('/registrar_notificados', methods=['GET', 'POST'])
@login_required
def registrar_notificados():
    datos_tabla = [] # Lista para pre-llenar la tabla

    if request.method == 'POST':
        accion = request.form.get('accion')

        # --- ACCIÓN 1: CARGAR EXCEL (Solo pre-visualización) ---
        if accion == 'cargar_excel':
            if 'file' not in request.files:
                flash('No se seleccionó ningún archivo.')
            else:
                file = request.files['file']
                if file.filename == '' or not file.filename.endswith(('.xlsx', '.xls')):
                    flash('Archivo inválido.')
                else:
                    try:
                        df = pd.read_excel(file)
                        
                        # 1. Normalizar cabeceras (Mayúsculas, sin acentos y sin símbolos como . ° - /)
                        def normalize_header(h):
                            h = str(h).strip().upper()
                            h = "".join(c for c in unicodedata.normalize('NFKD', h) if not unicodedata.combining(c))
                            for char in [".", "°", "-", "_", "/", "\\", "(", ")", ":"]:
                                h = h.replace(char, " ")
                            return " ".join(h.split())
                        df.columns = [normalize_header(col) for col in df.columns]

                        # Función auxiliar para buscar columnas flexibles
                        def get_val(row, aliases):
                            for alias in aliases:
                                if alias in row.index:
                                    val = row[alias]
                                    # Manejo de NaN
                                    if pd.isna(val) or val == '': return ''
                                    return val
                            return ''

                        # Función para formatear fechas de Excel a HTML (YYYY-MM-DD)
                        def format_date(val):
                            if pd.isna(val) or str(val).strip() == '': return ''
                            try:
                                if isinstance(val, (pd.Timestamp, datetime)):
                                    return val.strftime('%Y-%m-%d')
                                if isinstance(val, (int, float)): return pd.to_datetime(val, unit='D', origin='1899-12-30').strftime('%Y-%m-%d')
                                # Intenta parsear diversos formatos de fecha de forma inteligente
                                dt = pd.to_datetime(str(val).strip(), errors='coerce')
                                return dt.strftime('%Y-%m-%d') if pd.notna(dt) else ''
                            except:
                                return ''

                        # Función para limpiar DNI (quitar .0 si viene como float)
                        def clean_dni(val):
                            if not val: return ''
                            try:
                                return str(int(float(val)))
                            except:
                                return str(val).strip()

                        # Función para normalizar Idiomas y Modalidades para los Selects
                        def normalize_text(val):
                            if not val: return ''
                            val = str(val).upper().strip()
                            # Mapeo de Idiomas (Excel -> Value del Select)
                            if 'INGL' in val: return 'Ingles'
                            if 'PORT' in val: return 'Portugues'
                            if 'ITAL' in val: return 'Italiano'
                            if 'QUECH' in val: return 'Quechua'
                            return val # Si no coincide, devuelve el valor original

                        for _, row in df.iterrows():
                            # --- Lógica de Nombres y Apellidos (Unificados o Separados) ---
                            nombres_full = get_val(row, ['NOMBRES Y APELLIDOS', 'APELLIDOS Y NOMBRES', 'ALUMNO', 'ESTUDIANTE', 'NOMBRE COMPLETO', 'PARTICIPANTE'])
                            
                            # 2. Si no se encontró columna única, buscar columnas separadas y concatenar
                            if not nombres_full:
                                nom = get_val(row, ['NOMBRES', 'NOMBRE'])
                                ape = get_val(row, ['APELLIDOS', 'APELLIDO'])
                                if nom or ape:
                                    nombres_full = f"{nom} {ape}".strip()
                            
                            item = {
                                'nombres_apellidos': nombres_full,
                                'dni': clean_dni(get_val(row, ['DNI', 'DOCUMENTO', 'IDENTIFICACION', 'NUMERO DOCUMENTO', 'DOC', 'CEDULA'])),
                                'idioma': normalize_text(get_val(row, ['IDIOMA', 'LENGUA', 'CURSO', 'LENGUA EXTRANJERA', 'MATERIA'])),
                                'codigo_libro': get_val(row, ['CODIGO Y N DE LIBRO', 'COD Y N DE LIBRO', 'CODIGO Y NUMERO DE LIBRO', 'CODIGO', 'LIBRO', 'N LIBRO', 'NRO LIBRO', 'NUMERO DE LIBRO', 'COD LIBRO']),
                                'anio': get_val(row, ['ANO', 'ANIO', 'YEAR', 'PERIODO', 'FECHA ANUAL', 'EJERCICIO']),
                                'fecha_elaboracion': format_date(get_val(row, ['FECHA ELABORACION', 'FECHA DE ELABORACION', 'F ELABORACION', 'ELABORACION', 'F ELAB', 'FECHA ELAB', 'ELAB'])),
                                'fecha_entrega': format_date(get_val(row, ['FECHA ENTREGA', 'FECHA DE ENTREGA', 'F ENTREGA', 'ENTREGA', 'F ENT', 'FECHA ENT', 'ENTREGADO'])),
                                'correo_entrega': str(get_val(row, ['CORREO DE ENTREGA', 'CORREO', 'EMAIL', 'CORREO ELECTRONICO', 'MAIL', 'CONTACTO'])).strip().lower(),
                                'modalidad': str(get_val(row, ['MODALIDAD', 'TIPO', 'MODALIDAD DE ESTUDIO', 'FORMA', 'CATEGORIA'])).upper().strip()
                            }
                            datos_tabla.append(item)
                        
                        flash('Excel cargado. Verifique los datos en la tabla antes de guardar.')
                    except Exception as e:
                        flash(f'Error al leer Excel: {str(e)}')

        # --- ACCIÓN 2: GUARDAR EN BD ---
        elif accion == 'guardar_bd':
            try:
                # Obtener listas de los inputs del formulario
                dnis = request.form.getlist('dni[]')
                nombres = request.form.getlist('nombres_apellidos[]')
                idiomas = request.form.getlist('idioma[]')
                codigos = request.form.getlist('codigo_libro[]')
                anios = request.form.getlist('anio[]')
                correos = request.form.getlist('correo_entrega[]')
                modalidades = request.form.getlist('modalidad[]')
                # Fechas
                f_elab = request.form.getlist('fecha_elaboracion[]')
                f_ent = request.form.getlist('fecha_entrega[]')

                count = 0
                for i in range(len(dnis)):
                    # Validar que al menos haya DNI para guardar la fila
                    if not dnis[i]: 
                        continue

                    # Convertir strings de fecha a objetos Date si no están vacíos
                    fecha_elab_obj = datetime.strptime(f_elab[i], '%Y-%m-%d').date() if f_elab[i] else None
                    fecha_ent_obj = datetime.strptime(f_ent[i], '%Y-%m-%d').date() if f_ent[i] else None

                    nuevo_notificado = Notificado(
                        nombres_apellidos=nombres[i],
                        dni=dnis[i],
                        idioma=idiomas[i],
                        codigo_libro=codigos[i],
                        anio=anios[i],
                        fecha_elaboracion=fecha_elab_obj,
                        fecha_entrega=fecha_ent_obj,
                        correo_entrega=correos[i],
                        modalidad=modalidades[i]
                    )
                    db.session.add(nuevo_notificado)
                    count += 1
                db.session.commit()
                flash(f'Éxito: Se guardaron {count} registros en la base de datos.')
                return redirect(url_for('registrar_notificados')) # Limpiar tabla
            except Exception as e:
                db.session.rollback()
                flash(f'Error al guardar: {str(e)}')
                # Si falla, mantenemos los datos en la tabla (habría que reconstruir datos_tabla aquí idealmente)
        
        # --- ACCIÓN 3: EXPORTAR TABLA ACTUAL A EXCEL ---
        elif accion == 'exportar_excel':
            try:
                # Recopilar datos del formulario actual
                data = {
                    'NOMBRES Y APELLIDOS': request.form.getlist('nombres_apellidos[]'),
                    'DNI': request.form.getlist('dni[]'),
                    'IDIOMA': request.form.getlist('idioma[]'),
                    'CODIGO Y N° LIBRO': request.form.getlist('codigo_libro[]'),
                    'AÑO': request.form.getlist('anio[]'),
                    'F. ELABORACION': request.form.getlist('fecha_elaboracion[]'),
                    'F. ENTREGA': request.form.getlist('fecha_entrega[]'),
                    'CORREO': request.form.getlist('correo_entrega[]'),
                    'MODALIDAD': request.form.getlist('modalidad[]')
                }
                
                # Crear DataFrame y filtrar filas vacías (donde no hay DNI)
                df_export = pd.DataFrame(data)
                df_export = df_export[df_export['DNI'] != '']

                # Generar Excel en memoria
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Registros')
                output.seek(0)
                
                return send_file(output, download_name="registros_actuales.xlsx", as_attachment=True)
            except Exception as e:
                flash(f'Error al exportar: {str(e)}')

    # Si datos_tabla está vacío (inicio), creamos filas vacías por defecto
    if not datos_tabla:
        for _ in range(2):
            datos_tabla.append({})

    return render_template('registrar_notificados.html', datos_tabla=datos_tabla)

@app.route('/verificar_notificados', methods=['GET', 'POST'])
@login_required
def verificar_notificados():
    resultados = []
    accion = request.form.get('accion') # Capturar la acción (buscar o exportar)

    if request.method == 'POST':
        anio = request.form.get('anio') # Año ahora es único
        meses = request.form.getlist('mes')
        idiomas = request.form.getlist('idioma')
        modalidades = request.form.getlist('modalidad')
        
        query = Notificado.query
        
        # Filtros Lógicos:
        if anio:
            query = query.filter(Notificado.fecha_elaboracion != None, extract('year', Notificado.fecha_elaboracion) == int(anio))
        if meses:
            # Convertimos los meses a enteros para compararlos con extract('month', ...)
            query = query.filter(Notificado.fecha_elaboracion != None, extract('month', Notificado.fecha_elaboracion).in_([int(m) for m in meses]))
        if idiomas:
            query = query.filter(Notificado.idioma.in_(idiomas))
        if modalidades:
            query = query.filter(Notificado.modalidad.in_(modalidades))
        
        if accion == 'exportar_excel':
            # Obtener todos los resultados para exportar (sin límite o con uno alto)
            lista_notificados = query.all()
            
            # Convertir a lista de diccionarios para DataFrame
            data_export = []
            for n in lista_notificados:
                data_export.append({
                    'NOMBRES Y APELLIDOS': n.nombres_apellidos,
                    'DNI': n.dni,
                    'IDIOMA': n.idioma,
                    'CODIGO LIBRO': n.codigo_libro,
                    'AÑO': n.fecha_elaboracion.year if n.fecha_elaboracion else '',
                    'MES': n.fecha_elaboracion.strftime('%B') if n.fecha_elaboracion else '',
                    'MODALIDAD': n.modalidad
                })
            
            df = pd.DataFrame(data_export)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Filtrados')
            output.seek(0)
            return send_file(output, download_name="reporte_filtrado.xlsx", as_attachment=True)

        # --- ACCIÓN 4: ELIMINAR REGISTROS SELECCIONADOS ---
        elif accion == 'eliminar':
            try:
                ids_eliminar = request.form.getlist('eliminar_ids')
                if ids_eliminar:
                    # Convertir a enteros y borrar
                    ids_int = [int(i) for i in ids_eliminar]
                    Notificado.query.filter(Notificado.id.in_(ids_int)).delete(synchronize_session=False)
                    db.session.commit()
                    flash(f'✅ Se eliminaron {len(ids_int)} registros correctamente.')
                return redirect(url_for('verificar_notificados'))
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Error al eliminar: {str(e)}')
                return redirect(url_for('verificar_notificados'))

        # Búsqueda normal
        resultados = query.limit(200).all()

    return render_template('verificar_notificados.html', resultados=resultados)

@app.route('/graficos_proyeccion', methods=['GET', 'POST'])
@login_required
def graficos_proyeccion():
    # Inicialización de variables
    anios = request.form.getlist('anio')
    meses = request.form.getlist('mes')
    idiomas = request.form.getlist('idioma')
    modalidades = request.form.getlist('modalidad')
    tipo_grafico = request.form.get('tipo_grafico', 'bar')
    
    show_results = False
    chart_data = {}

    if request.method == 'POST':
        show_results = True
        query = Notificado.query

        if anios:
            anios_ints = [int(a) for a in anios if a.isdigit()]
            query = query.filter(Notificado.fecha_elaboracion != None, extract('year', Notificado.fecha_elaboracion).in_(anios_ints))
        if meses:
            meses_ints = [int(m) for m in meses if m.isdigit()]
            query = query.filter(Notificado.fecha_elaboracion != None, extract('month', Notificado.fecha_elaboracion).in_(meses_ints))
        if idiomas:
            query = query.filter(Notificado.idioma.in_(idiomas))
        if modalidades:
            query = query.filter(Notificado.modalidad.in_(modalidades))

        datos_filtrados = query.all()
        total = len(datos_filtrados)

        # Agrupar datos para el gráfico único (basado en Idioma para mostrar diversidad)
        # Si el usuario selecciona idiomas específicos, mostramos el conteo por esos idiomas
        agrupados = {}
        for d in datos_filtrados:
            label = d.idioma or "Sin Idioma"
            agrupados[label] = agrupados.get(label, 0) + 1
        
        chart_data = {
            'labels': list(agrupados.keys()),
            'values': list(agrupados.values()),
            'total': total
        }

    return render_template('graficos_proyeccion.html', 
                           chart_data=chart_data,
                           show_results=show_results,
                           filtros={
                               'anio': anios, 'meses': meses, 'idiomas': idiomas, 
                               'modalidades': modalidades,
                               'tipo_grafico': tipo_grafico
                           })

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

with app.app_context():
    # --- AUTO-CORRECCIÓN DE BASE DE DATOS PARA PRODUCCIÓN ---
    inspector = inspect(db.engine)
    if inspector.has_table("notificado"):
        columns = [c['name'] for c in inspector.get_columns("notificado")]
        if "nombres_apellidos" not in columns:
            print("⚠️ Esquema desactualizado detectado. Recreando tabla 'Notificado'...")
            Notificado.__table__.drop(db.engine)
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', port=port, debug=debug)