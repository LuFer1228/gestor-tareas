from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from database import db, Usuario, Tarea, Subtarea, Evento
from dotenv import load_dotenv
import os
load_dotenv()
from groq import Groq
load_dotenv()
groq_client = Groq(api_key=os.environ.get('GROQ_API_KEY'))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave-secreta-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gestor_tareas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Debes iniciar sesión para acceder.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def cargar_usuario(user_id):
    return Usuario.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password')

        if Usuario.query.filter_by(email=email).first():
            flash('Ya existe una cuenta con ese correo.', 'danger')
            return render_template('registro.html')

        nuevo_usuario = Usuario(
            nombre=nombre,
            email=email,
            password=generate_password_hash(password)
        )
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash('¡Cuenta creada! Ahora inicia sesión.', 'success')
        return redirect(url_for('login'))

    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.password, password):
            login_user(usuario)
            return redirect(url_for('dashboard'))
        flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    tareas_pendientes = Tarea.query.filter_by(
        usuario_id=current_user.id, completada=False
    ).order_by(Tarea.fecha_limite.asc()).all()

    tareas_completadas = Tarea.query.filter_by(
        usuario_id=current_user.id, completada=True
    ).all()

    hoy = date.today()
    pronto = hoy + timedelta(days=2)

    # Eventos del mes actual
    eventos = Evento.query.filter_by(usuario_id=current_user.id).all()
    fechas_eventos = [e.fecha.strftime('%Y-%m-%d') for e in eventos]

    # Fechas de entregas
    fechas_entregas = [t.fecha_limite.strftime('%Y-%m-%d') for t in tareas_pendientes]

    return render_template('dashboard.html',
        tareas_pendientes=tareas_pendientes,
        tareas_completadas=tareas_completadas,
        hoy=hoy,
        pronto=pronto,
        eventos=eventos,
        fechas_eventos=fechas_eventos,
        fechas_entregas=fechas_entregas)

# ── Tareas ────────────────────────────────────────────────────────

@app.route('/tarea/nueva', methods=['GET', 'POST'])
@login_required
def nueva_tarea():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion')
        fecha_limite = datetime.strptime(request.form.get('fecha_limite'), '%Y-%m-%d').date()

        tarea = Tarea(
            titulo=titulo,
            descripcion=descripcion,
            fecha_limite=fecha_limite,
            usuario_id=current_user.id
        )
        db.session.add(tarea)
        db.session.commit()
        flash('¡Tarea creada!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('tarea_form.html', accion='nueva', tarea=None)

@app.route('/tarea/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_tarea(id):
    tarea = Tarea.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()

    if request.method == 'POST':
        tarea.titulo = request.form.get('titulo')
        tarea.descripcion = request.form.get('descripcion')
        tarea.fecha_limite = datetime.strptime(request.form.get('fecha_limite'), '%Y-%m-%d').date()
        db.session.commit()
        flash('¡Tarea actualizada!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('tarea_form.html', accion='editar', tarea=tarea)

@app.route('/tarea/completar/<int:id>')
@login_required
def completar_tarea(id):
    tarea = Tarea.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    tarea.completada = not tarea.completada
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/tarea/eliminar/<int:id>')
@login_required
def eliminar_tarea(id):
    tarea = Tarea.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(tarea)
    db.session.commit()
    flash('Tarea eliminada.', 'info')
    return redirect(url_for('dashboard'))

# ── Subtareas ─────────────────────────────────────────────────────

@app.route('/subtarea/agregar/<int:tarea_id>', methods=['POST'])
@login_required
def agregar_subtarea(tarea_id):
    tarea = Tarea.query.filter_by(id=tarea_id, usuario_id=current_user.id).first_or_404()
    titulo = request.form.get('titulo')
    if titulo:
        subtarea = Subtarea(titulo=titulo, tarea_id=tarea.id)
        db.session.add(subtarea)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/subtarea/completar/<int:id>')
@login_required
def completar_subtarea(id):
    subtarea = Subtarea.query.get_or_404(id)
    tarea = Tarea.query.filter_by(id=subtarea.tarea_id, usuario_id=current_user.id).first_or_404()
    subtarea.completada = not subtarea.completada
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/subtarea/eliminar/<int:id>')
@login_required
def eliminar_subtarea(id):
    subtarea = Subtarea.query.get_or_404(id)
    Tarea.query.filter_by(id=subtarea.tarea_id, usuario_id=current_user.id).first_or_404()
    db.session.delete(subtarea)
    db.session.commit()
    return redirect(url_for('dashboard'))

# ── Eventos ───────────────────────────────────────────────────────

@app.route('/evento/nuevo', methods=['POST'])
@login_required
def nuevo_evento():
    titulo = request.form.get('titulo')
    fecha = datetime.strptime(request.form.get('fecha'), '%Y-%m-%d').date()
    hora = request.form.get('hora')

    evento = Evento(
        titulo=titulo,
        fecha=fecha,
        hora=hora,
        usuario_id=current_user.id
    )
    db.session.add(evento)
    db.session.commit()
    flash('¡Evento agregado!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/evento/eliminar/<int:id>')
@login_required
def eliminar_evento(id):
    evento = Evento.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(evento)
    db.session.commit()
    return redirect(url_for('dashboard'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
# ── Rutas de IA ───────────────────────────────────────────────────

@app.route('/ia/chatbot', methods=['POST'])
@login_required
def chatbot():
    mensaje = request.form.get('mensaje', '')
    historial = request.form.get('historial', '[]')
    if not mensaje:
        return jsonify({'respuesta': 'Escribe algo para que pueda ayudarte.'})

    import json
    historial = json.loads(historial)

    # Obtener contexto del usuario
    tareas_pendientes = Tarea.query.filter_by(
        usuario_id=current_user.id, completada=False
    ).order_by(Tarea.fecha_limite.asc()).all()

    tareas_completadas = Tarea.query.filter_by(
        usuario_id=current_user.id, completada=True
    ).all()

    eventos = Evento.query.filter_by(usuario_id=current_user.id).all()

    # Construir contexto
    contexto_tareas = ""
    for t in tareas_pendientes:
        total = len(t.subtareas)
        hechas = sum(1 for s in t.subtareas if s.completada)
        progreso = int((hechas / total) * 100) if total > 0 else 0
        contexto_tareas += f"- {t.titulo} (vence: {t.fecha_limite.strftime('%d/%m/%Y')}, progreso: {progreso}%)\n"

    contexto_completadas = ""
    for t in tareas_completadas:
        contexto_completadas += f"- {t.titulo}\n"

    contexto_eventos = ""
    for e in eventos:
        contexto_eventos += f"- {e.titulo} ({e.fecha.strftime('%d/%m/%Y')}{ ' a las ' + e.hora if e.hora else ''})\n"

    system_prompt = f"""Eres un asistente académico personal amigable para {current_user.nombre}.
Responde siempre en español, de forma clara y concisa.
Tienes acceso al contexto académico actual del estudiante:

TAREAS PENDIENTES:
{contexto_tareas if contexto_tareas else 'No tiene tareas pendientes.'}

TAREAS COMPLETADAS:
{contexto_completadas if contexto_completadas else 'No tiene tareas completadas.'}

EVENTOS PRÓXIMOS:
{contexto_eventos if contexto_eventos else 'No tiene eventos programados.'}

Usa esta información para dar respuestas personalizadas. Si te preguntan por sus tareas, fechas, proyectos o eventos, responde basándote en esta información."""

    # Construir mensajes con historial
    messages = [{"role": "system", "content": system_prompt}]
    for msg in historial[-10:]:  # últimos 10 mensajes
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": mensaje})

    try:
        respuesta = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        texto = respuesta.choices[0].message.content
        return jsonify({'respuesta': texto})
    except Exception as e:
        return jsonify({'respuesta': f'Error: {str(e)}'})
    
@app.route('/ia/plan/<int:tarea_id>', methods=['POST'])
@login_required
def generar_plan(tarea_id):
    tarea = Tarea.query.filter_by(id=tarea_id, usuario_id=current_user.id).first_or_404()
    try:
        respuesta = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Eres un asistente académico. Genera exactamente 5 subtareas concretas para completar la tarea del estudiante. Responde SOLO con las 5 subtareas, una por línea, sin números ni viñetas, sin texto extra."},
                {"role": "user", "content": f"Título: {tarea.titulo}\nDescripción: {tarea.descripcion or 'Sin descripción'}\nFecha límite: {tarea.fecha_limite}"}
            ]
        )
        subtareas_texto = respuesta.choices[0].message.content.strip().split('\n')
        subtareas_texto = [s.strip() for s in subtareas_texto if s.strip()][:5]
        for titulo in subtareas_texto:
            subtarea = Subtarea(titulo=titulo, tarea_id=tarea.id)
            db.session.add(subtarea)
        db.session.commit()
        flash(f'¡La IA generó {len(subtareas_texto)} subtareas!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/ia/resumir/<int:tarea_id>', methods=['POST'])
@login_required
def resumir_tarea(tarea_id):
    tarea = Tarea.query.filter_by(id=tarea_id, usuario_id=current_user.id).first_or_404()
    if not tarea.descripcion:
        flash('La tarea no tiene descripción para resumir.', 'warning')
        return redirect(url_for('dashboard'))
    try:
        # Guardar descripción original antes de resumir
        if not tarea.descripcion_original:
            tarea.descripcion_original = tarea.descripcion
        respuesta = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Resume la descripción de la tarea académica en máximo 2 líneas, de forma clara y directa. Solo devuelve el resumen, sin texto extra."},
                {"role": "user", "content": tarea.descripcion}
            ]
        )
        tarea.descripcion = respuesta.choices[0].message.content.strip()
        db.session.commit()
        flash('¡Descripción resumida por la IA!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/ia/restaurar/<int:tarea_id>')
@login_required
def restaurar_descripcion(tarea_id):
    tarea = Tarea.query.filter_by(id=tarea_id, usuario_id=current_user.id).first_or_404()
    if tarea.descripcion_original:
        tarea.descripcion = tarea.descripcion_original
        tarea.descripcion_original = None
        db.session.commit()
        flash('¡Descripción restaurada!', 'success')
    else:
        flash('No hay descripción original guardada.', 'warning')
    return redirect(url_for('dashboard'))