"""SuperGestión AE4: MVP educativo con roles, CSV, ventas y matriz dinámica."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for, abort
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from storage import init_files, next_id, read_all, write_all

app = Flask(__name__)
# En producción debe definirse SECRET_KEY mediante variable de entorno.
app.secret_key = os.environ.get('SECRET_KEY', 'solo-para-demostracion-local-cambiar')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
ROLES = {'administrador', 'encargado', 'cajero'}
PERMISOS = {
    'usuarios': {'administrador'},
    'proveedores': {'administrador', 'encargado'},
    'productos': {'administrador', 'encargado'},
    'clientes': ROLES,
    'ventas': {'administrador', 'cajero'},
    'reportes': {'administrador'},
}


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 220_000)
    return f'{salt}${digest.hex()}'


def check_password(password, encoded):
    try:
        salt, digest = encoded.split('$')
        return hmac.compare_digest(hash_password(password, salt), encoded)
    except (ValueError, TypeError):
        return False


def setup():
    init_files()
    if not read_all('usuarios'):
        write_all('usuarios', [{'id': '1', 'nombre': 'admin', 'clave_hash': hash_password('Admin123!'), 'rol': 'administrador', 'activo': '1'}])


def current_user():
    uid = session.get('uid')
    return next((u for u in read_all('usuarios') if u['id'] == uid and u['activo'] == '1'), None)


def authorized(section):
    user = current_user()
    return bool(user and user['rol'] in PERMISOS[section])


def login_required(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if not current_user():
            session.clear()
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapped


def requires(section):
    def deco(func):
        @wraps(func)
        @login_required
        def wrapped(*args, **kwargs):
            if not authorized(section):
                abort(403)
            return func(*args, **kwargs)
        return wrapped
    return deco


# Token CSRF firmado, independiente de la cookie de sesión.
# Evita el error 400 si el token de sesión cambia entre GET y POST.
def csrf_serializer():
    return URLSafeTimedSerializer(app.secret_key, salt='supergestion-csrf-v2')


@app.before_request
def csrf_check():
    if request.method == 'POST':
        token = request.form.get('csrf', '')
        try:
            if csrf_serializer().loads(token, max_age=3600) != 'formulario-supergestion':
                abort(400, 'Formulario inválido. Recargá la página.')
        except (BadSignature, SignatureExpired):
            abort(400, 'Formulario vencido o inválido. Recargá la página.')


@app.context_processor
def context():
    token = csrf_serializer().dumps('formulario-supergestion')
    return {'usuario': current_user(), 'permiso': authorized, 'csrf': token}


def money(raw):
    try:
        value = Decimal(str(raw).replace(',', '.'))
        if not value.is_finite() or value < 0:
            raise ValueError()
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError('El precio debe ser un número positivo o cero.')


def positive_int(raw, label):
    try:
        value = int(raw)
        if value < 1:
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ValueError(f'{label} debe ser un entero mayor que cero.')


def nonnegative_int(raw, label):
    try:
        value = int(raw)
        if value < 0:
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ValueError(f'{label} debe ser un entero no negativo.')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        password = request.form.get('password', '')
        user = next((u for u in read_all('usuarios') if u['nombre'].casefold() == nombre.casefold() and u['activo'] == '1'), None)
        if user and check_password(password, user['clave_hash']):
            session.clear()
            session['uid'] = user['id']
            return redirect(url_for('index'))
        flash('Usuario o contraseña incorrectos.', 'error')
    return render_template('login.html')


@app.post('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.get('/')
@login_required
def index():
    products = [p for p in read_all('productos') if p['activo'] == '1']
    sales = [v for v in read_all('ventas') if v['estado'] == 'Confirmada']
    today = datetime.now().date().isoformat()
    total = sum((Decimal(v['total']) for v in sales if v['fecha'][:10] == today), Decimal('0'))
    low = [p for p in products if int(p['stock']) <= 5]
    return render_template('index.html', products=len(products), clients=len(read_all('clientes')), low=low, total=total)


@app.route('/<kind>', methods=['GET', 'POST'])
@login_required
def catalog(kind):
    if kind not in ('proveedores', 'clientes', 'productos'):
        abort(404)
    if not authorized(kind):
        abort(403)
    if request.method == 'POST':
        try:
            rows = read_all(kind)
            nombre = request.form.get('nombre', '').strip()
            if not nombre:
                raise ValueError('El nombre no puede quedar vacío.')
            record = {'id': next_id(rows), 'nombre': nombre, 'activo': '1'}
            if kind in ('proveedores', 'clientes'):
                record['telefono'] = request.form.get('telefono', '').strip()
            else:
                categoria = request.form.get('categoria', '').strip()
                if not categoria:
                    raise ValueError('La categoría es obligatoria.')
                proveedor = request.form.get('proveedor_id', '')
                if not any(p['id'] == proveedor and p['activo'] == '1' for p in read_all('proveedores')):
                    raise ValueError('Seleccioná un proveedor activo.')
                record.update(categoria=categoria, precio=str(money(request.form.get('precio'))), stock=str(nonnegative_int(request.form.get('stock'), 'Stock')), proveedor_id=proveedor)
            rows.append(record)
            write_all(kind, rows)
            flash('Registro guardado correctamente.', 'ok')
            return redirect(url_for('catalog', kind=kind))
        except ValueError as error:
            flash(str(error), 'error')
    return render_template('catalog.html', kind=kind, rows=read_all(kind), proveedores=[p for p in read_all('proveedores') if p['activo']=='1'])


@app.post('/<kind>/<item_id>/desactivar')
@login_required
def deactivate(kind, item_id):
    if kind not in ('proveedores', 'clientes', 'productos'):
        abort(404)
    if not authorized(kind):
        abort(403)
    rows = read_all(kind)
    row = next((r for r in rows if r['id'] == item_id), None)
    if not row:
        abort(404)
    row['activo'] = '0'
    write_all(kind, rows)
    flash('Registro desactivado. Su historial se conserva.', 'ok')
    return redirect(url_for('catalog', kind=kind))


@app.route('/usuarios', methods=['GET', 'POST'])
@requires('usuarios')
def users():
    if request.method == 'POST':
        rows = read_all('usuarios')
        try:
            nombre = request.form.get('nombre', '').strip()
            password = request.form.get('password', '')
            rol = request.form.get('rol', '')
            if not nombre or len(password) < 8 or rol not in ROLES:
                raise ValueError('Ingresá nombre, rol válido y contraseña de al menos 8 caracteres.')
            if any(u['nombre'].casefold() == nombre.casefold() for u in rows):
                raise ValueError('Ya existe ese nombre de usuario.')
            rows.append({'id': next_id(rows), 'nombre': nombre, 'clave_hash': hash_password(password), 'rol': rol, 'activo': '1'})
            write_all('usuarios', rows)
            flash('Usuario creado.', 'ok')
            return redirect(url_for('users'))
        except ValueError as error:
            flash(str(error), 'error')
    return render_template('users.html', rows=read_all('usuarios'))


@app.post('/usuarios/<item_id>/desactivar')
@requires('usuarios')
def deactivate_user(item_id):
    rows = read_all('usuarios')
    target = next((u for u in rows if u['id'] == item_id), None)
    if not target:
        abort(404)
    if item_id == current_user()['id']:
        flash('No podés desactivar tu propio usuario.', 'error')
    elif target['rol'] == 'administrador' and target['activo'] == '1' and sum(u['rol']=='administrador' and u['activo']=='1' for u in rows) <= 1:
        flash('Debe quedar al menos un administrador activo.', 'error')
    else:
        target['activo'] = '0'
        write_all('usuarios', rows)
        flash('Usuario desactivado.', 'ok')
    return redirect(url_for('users'))


@app.route('/ventas', methods=['GET', 'POST'])
@requires('ventas')
def sales():
    if request.method == 'POST':
        try:
            product_id = request.form.get('producto_id')
            qty = positive_int(request.form.get('cantidad'), 'Cantidad')
            client_id = request.form.get('cliente_id', '')
            if client_id and not any(c['id'] == client_id and c['activo'] == '1' for c in read_all('clientes')):
                raise ValueError('El cliente seleccionado no está activo.')
            products = read_all('productos')
            product = next((p for p in products if p['id'] == product_id and p['activo'] == '1'), None)
            if not product:
                raise ValueError('El producto no existe o está inactivo.')
            if qty > int(product['stock']):
                raise ValueError('Stock insuficiente para confirmar la venta.')
            amount = money(product['precio']) * qty
            sales_rows = read_all('ventas')
            details = read_all('detalle_ventas')
            sale_id = next_id(sales_rows)
            sale = {'id': sale_id, 'fecha': datetime.now().isoformat(timespec='seconds'), 'cliente_id': client_id, 'cajero_id': current_user()['id'], 'total': str(amount), 'estado': 'Confirmada'}
            detail = {'id': next_id(details), 'venta_id': sale_id, 'producto_id': product_id, 'cantidad': str(qty), 'precio_unitario': product['precio']}
            # MVP monousuario: escrituras atómicas por archivo; no transacción entre los tres CSV.
            product['stock'] = str(int(product['stock']) - qty)
            write_all('productos', products)
            write_all('ventas', sales_rows + [sale])
            write_all('detalle_ventas', details + [detail])
            flash(f'Venta #{sale_id} confirmada: ${amount}.', 'ok')
            return redirect(url_for('sales'))
        except ValueError as error:
            flash(str(error), 'error')
    products = [p for p in read_all('productos') if p['activo']=='1']
    clients = [c for c in read_all('clientes') if c['activo']=='1']
    return render_template('sales.html', products=products, clients=clients, rows=list(reversed(read_all('ventas'))))


@app.get('/reportes')
@requires('reportes')
def reports():
    """Matriz dinámica: filas=categorías; columnas=días de la semana (lun-dom)."""
    products = {p['id']: p for p in read_all('productos')}
    sales_by_id = {s['id']: s for s in read_all('ventas') if s['estado'] == 'Confirmada'}
    categories = sorted({products[d['producto_id']]['categoria'] for d in read_all('detalle_ventas') if d['producto_id'] in products and d['venta_id'] in sales_by_id})
    matrix = [[0 for _ in range(7)] for _ in categories]
    indexes = {category: i for i, category in enumerate(categories)}
    for detail in read_all('detalle_ventas'):
        sale = sales_by_id.get(detail['venta_id'])
        product = products.get(detail['producto_id'])
        if sale and product:
            weekday = datetime.fromisoformat(sale['fecha']).weekday()
            matrix[indexes[product['categoria']]][weekday] += int(detail['cantidad'])
    totals = []
    for row in matrix:
        subtotal = 0
        for col in row:
            subtotal += col
        totals.append(subtotal)
    return render_template('reports.html', categories=categories, matrix=matrix, totals=totals, weekday_totals=[sum(row[i] for row in matrix) for i in range(7)])


@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', message='No tenés permiso para entrar en esta sección.'), 403


@app.errorhandler(400)
def bad_request(e):
    return render_template('error.html', message='Solicitud inválida. Volvé a intentar.'), 400


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', message='Ocurrió un error interno. Revisá los archivos CSV.'), 500


setup()
if __name__ == '__main__':
    app.run(debug=False, port=5000)
