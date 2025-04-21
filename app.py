from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import os
import types  
import traceback
from functools import wraps
from bson import ObjectId, SON
from bson.errors import InvalidId 


from config import MONGO_URI, SECRET_KEY

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config["MONGO_URI"] = MONGO_URI
app.config["SECRET_KEY"] = SECRET_KEY
mongo = PyMongo(app)

# Configuración de Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.rol = user_data['rol']
        self.nombre_completo = user_data.get('nombre_completo', '')

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.usuarios.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'admin':
            flash('Acceso denegado: Se requieren privilegios de administrador', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Rutas de autenticación
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'] 
        email = request.form['email']
        nombre_completo = request.form['nombre_completo']
        telefono = request.form['telefono']
        
        if mongo.db.usuarios.find_one({'username': username}):
            flash('El nombre de usuario ya está en uso', 'danger')
            return redirect(url_for('registro'))
        
        if mongo.db.usuarios.find_one({'email': email}):
            flash('El correo electrónico ya está registrado', 'danger')
            return redirect(url_for('registro'))
        
        nuevo_usuario = {
            'username': username,
            'password': password,  
            'rol': 'cliente',
            'email': email,
            'nombre_completo': nombre_completo,
            'telefono': telefono,
            'fecha_registro': datetime.utcnow()
        }
        
        mongo.db.usuarios.insert_one(nuevo_usuario)
        flash('Registro exitoso. Por favor inicie sesión.', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_data = mongo.db.usuarios.find_one({'username': username})
        
        if not user_data:
            flash('Usuario no encontrado', 'danger')
        elif not user_data.get('password'):
            flash('Cuenta no configurada correctamente. Contacte al administrador.', 'danger')
        else:
            if user_data['password'] == password:
                user = User(user_data)
                login_user(user)
                flash(f'Bienvenido {user.nombre_completo}!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('home'))
            else:
                flash('Contraseña incorrecta', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('home'))

# Rutas principales
@app.route('/')
def home():
    platos_destacados = list(mongo.db.platos.find().limit(6))
    for plato in platos_destacados:
        plato['_id'] = str(plato['_id'])
        if 'imagen' not in plato or not plato['imagen']:
            plato['imagen'] = 'default.jpg'  
    return render_template('home.html', platos_destacados=platos_destacados)

@app.route('/menu')
def menu():
    platos = list(mongo.db.platos.find())
    bebidas = list(mongo.db.bebidas.find())
    return render_template('menu.html', platos=platos, bebidas=bebidas)

@app.route('/pedidos')
@login_required
def pedidos():
    try:
        # Construir query basado en el rol del usuario
        query = {'usuario_id': ObjectId(current_user.id)} if current_user.rol == 'cliente' else {}
        
        # Lista para almacenar los pedidos procesados
        pedidos_procesados = []
        
        # Obtener cursor de pedidos
        cursor_pedidos = mongo.db.pedidos.find(query).sort('fecha', -1)
        
        for pedido_bruto in cursor_pedidos:

            pedido_son = SON(pedido_bruto)
            
            pedido_procesado = {
                '_id': str(pedido_son.get('_id', '')),
                'usuario_id': str(pedido_son.get('usuario_id', '')),
                'subtotal': float(pedido_son.get('subtotal', 0)),
                'impuestos': float(pedido_son.get('impuestos', 0)),
                'total': float(pedido_son.get('total', 0)),
                'fecha': pedido_son.get('fecha', datetime.utcnow()),
                'estado': pedido_son.get('estado', 'Pendiente'),
                'metodo_pago': pedido_son.get('metodo_pago', 'Efectivo'),
                'notas': pedido_son.get('notas', ''),
                'estado_pago': pedido_son.get('estado_pago', 'Pendiente')
            }
            
            items_brutos = pedido_son.get('items')
            
            if not isinstance(items_brutos, (list, tuple)):
                if hasattr(items_brutos, '__iter__') and not isinstance(items_brutos, (str, bytes, dict)):
                    items_brutos = list(items_brutos)
                else:
                    items_brutos = []
            
            # Procesar cada item individualmente
            items_procesados = []
            for item in items_brutos:
                if not isinstance(item, dict):
                    continue
                    
                item_procesado = {
                    'producto_id': str(item.get('producto_id', '')),
                    'tipo': str(item.get('tipo', '')),
                    'nombre': str(item.get('nombre', '')),
                    'cantidad': int(item.get('cantidad', 0)),
                    'precio_unitario': float(item.get('precio_unitario', 0)),
                    'subtotal': float(item.get('subtotal', 0))
                }
                items_procesados.append(item_procesado)
            
            # Asignar los items procesados
            pedido_procesado['items'] = items_procesados
            
            # Agregar a la lista final
            pedidos_procesados.append(pedido_procesado)
        
        # Verificar el primer pedido
        if pedidos_procesados:
            print("=== DEBUG: Estructura del pedido procesado ===")
            print("ID:", pedidos_procesados[0]['_id'])
            print("Items count:", len(pedidos_procesados[0]['items']))
            print("Tipo de items:", type(pedidos_procesados[0]['items']))
            if pedidos_procesados[0]['items']:
                print("Primer item:", pedidos_procesados[0]['items'][0])
        
        return render_template('pedidos.html', pedidos=pedidos_procesados)
    
    except Exception as e:
        print("=== ERROR DETALLADO ===")
        traceback.print_exc()
        flash('Ocurrió un error al recuperar los pedidos. Por favor intente nuevamente.', 'danger')
        return redirect(url_for('home'))
    
@app.route('/realizar_pedido', methods=['GET', 'POST'])
@login_required
def realizar_pedido():
    if request.method == 'POST':
        try:
            items = request.form.getlist('items[]')
            cantidades = request.form.getlist('cantidades[]')
            
            items_pedido = []
            total_con_impuestos = 0.0
            has_valid_items = False
            
            for item_id, cantidad_str in zip(items, cantidades):
                try:
                    cantidad = int(cantidad_str)
                    if cantidad <= 0:
                        continue
                        
                    producto = None
                    for collection in ['platos', 'bebidas']:
                        if producto is None:
                            producto = mongo.db[collection].find_one(
                                {'_id': ObjectId(item_id), 'activo': True}
                            )
                            if producto:
                                producto['tipo'] = collection[:-1]
                    
                    if not producto:
                        continue
                        
                    precio_con_impuestos = float(producto['precio'])
                    subtotal_con_impuestos = precio_con_impuestos * cantidad
                    
                    items_pedido.append({
                        'producto_id': ObjectId(item_id),
                        'tipo': producto['tipo'],
                        'nombre': producto['nombre'],
                        'cantidad': cantidad,
                        'precio_unitario': precio_con_impuestos,
                        'subtotal': subtotal_con_impuestos
                    })
                    
                    total_con_impuestos += subtotal_con_impuestos
                    has_valid_items = True
                    
                except (ValueError, InvalidId) as e:
                    continue
            
            if not has_valid_items:
                flash('Debe seleccionar al menos un producto válido', 'danger')
                return redirect(url_for('realizar_pedido'))
            
            # Calcular desglose de impuestos (13% incluido)
            impuestos = total_con_impuestos * (13 / 113)
            subtotal_sin_impuestos = total_con_impuestos - impuestos
            
            # Crear documento del pedido
            pedido_data = {
                'usuario_id': ObjectId(current_user.id),
                'items': items_pedido,
                'subtotal': round(subtotal_sin_impuestos, 2),
                'impuestos': round(impuestos, 2),
                'total': round(total_con_impuestos, 2),
                'fecha': datetime.utcnow(),
                'estado': 'Pendiente',
                'metodo_pago': request.form.get('metodo_pago', 'Efectivo'),
                'notas': request.form.get('notas', ''),
                'estado_pago': 'Pendiente'
            }
            
            # Insertar en MongoDB
            result = mongo.db.pedidos.insert_one(pedido_data)
            
            flash('Pedido realizado con éxito!', 'success')
            return redirect(url_for('pedidos'))
            
        except Exception as e:
            flash(f'Error al procesar el pedido: {str(e)}', 'danger')
            return redirect(url_for('realizar_pedido'))
    
    # GET: Mostrar formulario
    platos = list(mongo.db.platos.find({'activo': True}))
    bebidas = list(mongo.db.bebidas.find({'activo': True}))
    
    for p in platos + bebidas:
        p['_id'] = str(p['_id'])
    
    return render_template('realizar_pedido.html',
                         platos=platos,
                         bebidas=bebidas)

@app.route('/cancelar-pedido/<id>', methods=['POST'])
@login_required
def cancelar_pedido(id):
    try:
        pedido = mongo.db.pedidos.find_one({'_id': ObjectId(id)})
        
        if not pedido:
            flash('Pedido no encontrado', 'danger')
            return redirect(url_for('pedidos'))
        
        # Verificar permisos (usuario que hizo el pedido o admin)
        if str(pedido.get('usuario_id', '')) != current_user.id and current_user.rol != 'admin':
            flash('No tienes permiso para cancelar este pedido', 'danger')
            return redirect(url_for('pedidos'))
        
        # Verificar si ya está cancelado
        if pedido.get('estado') == 'Cancelado':
            flash('El pedido ya está cancelado', 'warning')
            return redirect(url_for('pedidos'))
        
        # Verificar si ya está completado
        if pedido.get('estado') in ['Completado', 'Entregado']:
            flash('No se puede cancelar un pedido ya completado', 'danger')
            return redirect(url_for('pedidos'))
        
        # Actualizar estado del pedido
        mongo.db.pedidos.update_one(
            {'_id': ObjectId(id)},
            {'$set': {'estado': 'Cancelado'}}
        )
        
        flash('Pedido cancelado correctamente', 'success')
        return redirect(url_for('pedidos'))
        
    except Exception as e:
        flash(f'Error al cancelar el pedido: {str(e)}', 'danger')
        return redirect(url_for('pedidos'))

# Rutas de gestión (solo admin)
@app.route('/gestion/<collection>')
@login_required
@admin_required
def gestion(collection):
    if collection not in ["usuarios","bebidas", "platos", "proveedores", "pedidos", "inventario", "reservaciones", "pagos", "mesas"]:
        return redirect(url_for('home'))
    
    documentos = list(mongo.db[collection].find())
    for doc in documentos:
        doc['_id'] = str(doc['_id']) 
    
    return render_template('gestion.html', collection=collection, documentos=documentos)

@app.route('/add/<collection>', methods=['GET', 'POST'])
@login_required
@admin_required
def add(collection):
    if collection not in ["usuarios", "bebidas", "platos", "proveedores", "pedidos", "inventario", "reservaciones", "pagos", "mesas"]:
        return redirect(url_for('home'))
    
    if request.method == 'GET':
        return render_template('add.html', collection=collection)
    
    if request.method == 'POST':
        try:
            data = {}
            if collection == "bebidas":
                nombre = request.form.get('nombre', '').strip()
                if not nombre:
                    flash('El nombre es requerido', 'danger')
                    return redirect(url_for('add', collection=collection))
                
                try:
                    precio = float(request.form.get('precio', 0))
                    stock = int(request.form.get('stock', 0))
                except ValueError:
                    flash('Precio y stock deben ser números válidos', 'danger')
                    return redirect(url_for('add', collection=collection))
                
                data = {
                    'nombre': nombre,
                    'precio': precio,
                    'descripcion': request.form.get('descripcion', '').strip(),
                    'categoria': request.form.get('categoria', '').strip(),
                    'imagen': request.form.get('imagen', 'default.jpg').strip(),
                    'stock': stock,
                    'proveedor_id': ObjectId(request.form.get('proveedor_id')) if request.form.get('proveedor_id') else None,
                    'activo': True
                }

            elif collection == "usuarios":
                required_fields = ['username', 'password', 'email', 'nombre_completo', 'telefono', 'rol']
                for field in required_fields:
                    if not request.form.get(field, '').strip():
                        flash(f'El campo {field} es requerido', 'danger')
                        return redirect(url_for('add', collection=collection))
                
                username = request.form['username'].strip()
                email = request.form['email'].strip()
                
                # Verificar si el usuario o email ya existen
                if mongo.db.usuarios.find_one({'username': username}):
                    flash('El nombre de usuario ya está en uso', 'danger')
                    return redirect(url_for('add', collection=collection))
                
                if mongo.db.usuarios.find_one({'email': email}):
                    flash('El correo electrónico ya está registrado', 'danger')
                    return redirect(url_for('add', collection=collection))
                
                data = {
                    'username': username,
                    'password': request.form['password'].strip(),
                    'rol': request.form['rol'].strip(),
                    'email': email,
                    'nombre_completo': request.form['nombre_completo'].strip(),
                    'telefono': request.form['telefono'].strip(),
                    'fecha_registro': datetime.utcnow(),
                    'activo': True
                }
                
                if data['rol'] == 'empleado':
                    try:
                        data['salario'] = float(request.form.get('salario', 0))
                    except ValueError:
                        data['salario'] = 0.0
                    data['puesto'] = request.form.get('puesto', '').strip()
                    data['fecha_contratacion'] = datetime.utcnow()
                elif data['rol'] == 'cliente':
                    data['direccion'] = request.form.get('direccion', '').strip()

            elif collection == "platos":
                nombre = request.form.get('nombre', '').strip()
                if not nombre:
                    flash('El nombre es requerido', 'danger')
                    return redirect(url_for('add', collection=collection))
                
                try:
                    precio = float(request.form.get('precio', 0))
                except ValueError:
                    flash('El precio debe ser un número válido', 'danger')
                    return redirect(url_for('add', collection=collection))
                
                data = {
                    'nombre': nombre,
                    'precio': precio,
                    'descripcion': request.form.get('descripcion', '').strip(),
                    'categoria': request.form.get('categoria', '').strip(),
                    'imagen': request.form.get('imagen', 'default.jpg').strip(),
                    'activo': True,
                    'fecha_creacion': datetime.utcnow()
                }

            elif collection == "proveedores":
                required_fields = ['nombre', 'contacto', 'telefono', 'producto', 'email']
                for field in required_fields:
                    if not request.form.get(field, '').strip():
                        flash(f'El campo {field} es requerido', 'danger')
                        return redirect(url_for('add', collection=collection))
                
                data = {
                    'nombre': request.form['nombre'].strip(),
                    'contacto': request.form['contacto'].strip(),
                    'telefono': request.form['telefono'].strip(),
                    'producto': request.form['producto'].strip(),
                    'direccion': request.form.get('direccion', '').strip(),
                    'email': request.form['email'].strip(),
                    'activo': True,
                    'fecha_registro': datetime.utcnow()
                }

            elif collection == "pedidos":
                try:
                    usuario_id = request.form.get('usuario_id')
                    producto_id = request.form.get('producto_id')
                    cantidad = int(request.form.get('cantidad', 1))
                    precio_unitario = float(request.form.get('precio_unitario', 0))
                    
                    if not usuario_id or not producto_id:
                        flash('Usuario y producto son requeridos', 'danger')
                        return redirect(url_for('add', collection=collection))
                    
                    if cantidad <= 0 or precio_unitario <= 0:
                        flash('Cantidad y precio deben ser mayores a 0', 'danger')
                        return redirect(url_for('add', collection=collection))
                    
                    subtotal = precio_unitario * cantidad
                    impuestos = subtotal * 0.13
                    total = subtotal + impuestos
                    
                    data = {
                        'usuario_id': ObjectId(usuario_id),
                        'items': [{
                            'producto_id': ObjectId(producto_id),
                            'tipo': request.form.get('tipo', 'plato'),
                            'nombre': request.form.get('producto_nombre', '').strip(),
                            'cantidad': cantidad,
                            'precio_unitario': precio_unitario,
                            'subtotal': subtotal
                        }],
                        'subtotal': subtotal,
                        'impuestos': impuestos,
                        'total': total,
                        'fecha': datetime.utcnow(),
                        'estado': request.form.get('estado', 'pendiente'),
                        'estado_pago': 'pendiente',
                        'metodo_pago': request.form.get('metodo_pago', 'efectivo'),
                        'mesa': int(request.form.get('mesa', 0)) if request.form.get('mesa') else None,
                        'empleado_id': ObjectId(request.form.get('empleado_id')) if request.form.get('empleado_id') else None,
                        'notas': request.form.get('notas', '').strip()
                    }
                except (ValueError, InvalidId) as e:
                    flash('Datos del pedido inválidos', 'danger')
                    return redirect(url_for('add', collection=collection))

            elif collection == "inventario":
                producto = request.form.get('producto', '').strip()
                if not producto:
                    flash('El nombre del producto es requerido', 'danger')
                    return redirect(url_for('add', collection=collection))
                
                try:
                    cantidad = int(request.form.get('cantidad', 0))
                    minimo_stock = int(request.form.get('minimo_stock', 0))
                except ValueError:
                    flash('Cantidad y mínimo stock deben ser números válidos', 'danger')
                    return redirect(url_for('add', collection=collection))
                
                data = {
                    'producto': producto,
                    'cantidad': cantidad,
                    'unidad': request.form.get('unidad', '').strip(),
                    'proveedor': request.form.get('proveedor', '').strip(),
                    'proveedor_id': ObjectId(request.form.get('proveedor_id')) if request.form.get('proveedor_id') else None,
                    'minimo_stock': minimo_stock,
                    'ubicacion': request.form.get('ubicacion', '').strip(),
                    'categoria': request.form.get('categoria', '').strip(),
                    'fecha_ultima_compra': datetime.utcnow() if request.form.get('fecha_ultima_compra') else None
                }

            elif collection == "reservaciones":
                try:
                    usuario_id = request.form.get('usuario_id')
                    if not usuario_id:
                        flash('Se requiere un ID de usuario', 'danger')
                        return redirect(url_for('add', collection=collection))
                    
                    fecha_str = request.form.get('fecha')
                    if not fecha_str:
                        flash('La fecha es requerida', 'danger')
                        return redirect(url_for('add', collection=collection))
                    
                    fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
                    hora = request.form.get('hora', '').strip()
                    if not hora:
                        flash('La hora es requerida', 'danger')
                        return redirect(url_for('add', collection=collection))
                    
                    personas = int(request.form.get('personas', 1))
                    mesa = int(request.form.get('mesa', 0))
                    
                    if personas <= 0:
                        flash('El número de personas debe ser mayor a 0', 'danger')
                        return redirect(url_for('add', collection=collection))
                    
                    if mesa <= 0:
                        flash('El número de mesa debe ser mayor a 0', 'danger')
                        return redirect(url_for('add', collection=collection))
                    
                    data = {
                        'usuario_id': ObjectId(usuario_id),
                        'mesa': mesa,
                        'fecha': fecha,
                        'hora': hora,
                        'estado': request.form.get('estado', 'pendiente'),
                        'personas': personas,
                        'notas': request.form.get('notas', '').strip(),
                        'fecha_creacion': datetime.utcnow(),
                        'empleado_id': ObjectId(request.form.get('empleado_id')) if request.form.get('empleado_id') else None
                    }
                except ValueError as e:
                    flash('Formato de fecha incorrecto o datos inválidos', 'danger')
                    return redirect(url_for('add', collection=collection))
                except Exception as e:
                    flash(f'Error al procesar la reservación: {str(e)}', 'danger')
                    return redirect(url_for('add', collection=collection))

            elif collection == "pagos":
                try:
                    usuario_id = request.form.get('usuario_id')
                    pedido_id = int(request.form.get('pedido_id', 0))
                    monto = float(request.form.get('monto', 0))
                    
                    if not usuario_id or pedido_id <= 0 or monto <= 0:
                        flash('Datos del pago inválidos', 'danger')
                        return redirect(url_for('add', collection=collection))
                    
                    data = {
                        'usuario_id': ObjectId(usuario_id),
                        'pedido_id': pedido_id,
                        'monto': monto,
                        'metodo': request.form.get('metodo', 'efectivo'),
                        'estado': request.form.get('estado', 'pendiente'),
                        'fecha': datetime.utcnow(),
                        'transaccion_id': request.form.get('transaccion_id', '').strip(),
                        'codigo_autorizacion': request.form.get('codigo_autorizacion', '').strip()
                    }
                    
                    if data['metodo'] == 'tarjeta':
                        data['detalles'] = {
                            'tipo_tarjeta': request.form.get('tipo_tarjeta', '').strip(),
                            'ultimos_digitos': request.form.get('ultimos_digitos', '').strip()
                        }
                except ValueError as e:
                    flash('Datos del pago inválidos', 'danger')
                    return redirect(url_for('add', collection=collection))

            elif collection == "mesas":
                try:
                    numero = int(request.form.get('numero', 0))
                    capacidad = int(request.form.get('capacidad', 2))
                    
                    if numero <= 0 or capacidad <= 0:
                        flash('Número y capacidad deben ser mayores a 0', 'danger')
                        return redirect(url_for('add', collection=collection))
                    
                    data = {
                        'numero': numero,
                        'capacidad': capacidad,
                        'ocupada': request.form.get('ocupada', 'false') == 'true',
                        'ubicacion': request.form.get('ubicacion', 'Interior').strip(),
                        'caracteristicas': [x.strip() for x in request.form.get('caracteristicas', '').split(',') if x.strip()],
                        'activa': True
                    }
                except ValueError as e:
                    flash('Datos de la mesa inválidos', 'danger')
                    return redirect(url_for('add', collection=collection))

            mongo.db[collection].insert_one(data)
            flash(f'{collection[:-1].capitalize()} agregado correctamente', 'success')
            return redirect(url_for('gestion', collection=collection))
            
        except Exception as e:
            flash(f'Error al agregar: {str(e)}', 'danger')
            return redirect(url_for('add', collection=collection))

@app.route('/edit/<collection>/<id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(collection, id):
    try:
        documento = mongo.db[collection].find_one({'_id': ObjectId(id)})
        if not documento:
            flash('Documento no encontrado', 'danger')
            return redirect(url_for('gestion', collection=collection))
        
        documento['_id'] = str(documento['_id'])

        if request.method == 'POST':
            try:
                data = {}
                if collection == "bebidas":
                    nombre = request.form.get('nombre', '').strip()
                    if not nombre:
                        flash('El nombre es requerido', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))
                    
                    try:
                        precio = float(request.form.get('precio', 0))
                        stock = int(request.form.get('stock', 0))
                    except ValueError:
                        flash('Precio y stock deben ser números válidos', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))
                    
                    data = {
                        'nombre': nombre,
                        'precio': precio,
                        'descripcion': request.form.get('descripcion', '').strip(),
                        'categoria': request.form.get('categoria', '').strip(),
                        'imagen': request.form.get('imagen', documento.get('imagen', 'default.jpg')).strip(),
                        'stock': stock,
                        'proveedor_id': ObjectId(request.form.get('proveedor_id')) if request.form.get('proveedor_id') else None,
                        'activo': request.form.get('activo', 'true') == 'true'
                    }

                elif collection == "usuarios":
                    required_fields = ['username', 'email', 'nombre_completo', 'telefono', 'rol']
                    for field in required_fields:
                        if not request.form.get(field, '').strip():
                            flash(f'El campo {field} es requerido', 'danger')
                            return redirect(url_for('edit', collection=collection, id=id))
                    
                    username = request.form['username'].strip()
                    email = request.form['email'].strip()
                    
                    # Verificar si el usuario o email ya existen (excluyendo el actual)
                    existing_user = mongo.db.usuarios.find_one({
                        'username': username,
                        '_id': {'$ne': ObjectId(id)}
                    })
                    if existing_user:
                        flash('El nombre de usuario ya está en uso', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))
                    
                    existing_email = mongo.db.usuarios.find_one({
                        'email': email,
                        '_id': {'$ne': ObjectId(id)}
                    })
                    if existing_email:
                        flash('El correo electrónico ya está registrado', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))
                    
                    data = {
                        'username': username,
                        'rol': request.form['rol'].strip(),
                        'email': email,
                        'nombre_completo': request.form['nombre_completo'].strip(),
                        'telefono': request.form['telefono'].strip(),
                        'activo': request.form.get('activo', 'true') == 'true'
                    }
                    
                    # Actualizar contraseña si se proporcionó
                    if request.form.get('password'):
                        data['password'] = request.form['password'].strip()
                    
                    if data['rol'] == 'empleado':
                        try:
                            data['salario'] = float(request.form.get('salario', 0))
                        except ValueError:
                            data['salario'] = 0.0
                        data['puesto'] = request.form.get('puesto', '').strip()
                    elif data['rol'] == 'cliente':
                        data['direccion'] = request.form.get('direccion', '').strip()

                elif collection == "platos":
                    nombre = request.form.get('nombre', '').strip()
                    if not nombre:
                        flash('El nombre es requerido', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))
                    
                    try:
                        precio = float(request.form.get('precio', 0))
                    except ValueError:
                        flash('El precio debe ser un número válido', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))
                    
                    data = {
                        'nombre': nombre,
                        'precio': precio,
                        'descripcion': request.form.get('descripcion', '').strip(),
                        'categoria': request.form.get('categoria', '').strip(),
                        'imagen': request.form.get('imagen', documento.get('imagen', 'default.jpg')).strip(),
                        'activo': request.form.get('activo', 'true') == 'true'
                    }

                elif collection == "proveedores":
                    required_fields = ['nombre', 'contacto', 'telefono', 'producto', 'email']
                    for field in required_fields:
                        if not request.form.get(field, '').strip():
                            flash(f'El campo {field} es requerido', 'danger')
                            return redirect(url_for('edit', collection=collection, id=id))
                    
                    data = {
                        'nombre': request.form['nombre'].strip(),
                        'contacto': request.form['contacto'].strip(),
                        'telefono': request.form['telefono'].strip(),
                        'producto': request.form['producto'].strip(),
                        'direccion': request.form.get('direccion', '').strip(),
                        'email': request.form['email'].strip(),
                        'activo': request.form.get('activo', 'true') == 'true'
                    }

                elif collection == "pedidos":
                    data = {
                        'estado': request.form.get('estado', 'pendiente'),
                        'estado_pago': request.form.get('estado_pago', 'pendiente'),
                        'metodo_pago': request.form.get('metodo_pago', 'efectivo'),
                        'mesa': int(request.form.get('mesa', 0)) if request.form.get('mesa') else None,
                        'notas': request.form.get('notas', '').strip()
                    }
                    
                    # Actualizar fecha de entrega si el estado cambió a entregado
                    if request.form.get('estado') == 'entregado' and not documento.get('fecha_entrega'):
                        data['fecha_entrega'] = datetime.utcnow()

                elif collection == "inventario":
                    producto = request.form.get('producto', '').strip()
                    if not producto:
                        flash('El nombre del producto es requerido', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))
                    
                    try:
                        cantidad = int(request.form.get('cantidad', 0))
                        minimo_stock = int(request.form.get('minimo_stock', 0))
                    except ValueError:
                        flash('Cantidad y mínimo stock deben ser números válidos', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))
                    
                    data = {
                        'producto': producto,
                        'cantidad': cantidad,
                        'unidad': request.form.get('unidad', '').strip(),
                        'proveedor': request.form.get('proveedor', '').strip(),
                        'proveedor_id': ObjectId(request.form.get('proveedor_id')) if request.form.get('proveedor_id') else None,
                        'minimo_stock': minimo_stock,
                        'ubicacion': request.form.get('ubicacion', '').strip(),
                        'categoria': request.form.get('categoria', '').strip()
                    }

                elif collection == "reservaciones":
                    try:
                        fecha_str = request.form.get('fecha')
                        if not fecha_str:
                            flash('La fecha es requerida', 'danger')
                            return redirect(url_for('edit', collection=collection, id=id))
                        
                        fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
                        hora = request.form.get('hora', '').strip()
                        if not hora:
                            flash('La hora es requerida', 'danger')
                            return redirect(url_for('edit', collection=collection, id=id))
                        
                        personas = int(request.form.get('personas', 1))
                        mesa = int(request.form.get('mesa', 0))
                        
                        if personas <= 0:
                            flash('El número de personas debe ser mayor a 0', 'danger')
                            return redirect(url_for('edit', collection=collection, id=id))
                        
                        if mesa <= 0:
                            flash('El número de mesa debe ser mayor a 0', 'danger')
                            return redirect(url_for('edit', collection=collection, id=id))
                        
                        data = {
                            'mesa': mesa,
                            'fecha': fecha,
                            'hora': hora,
                            'estado': request.form.get('estado', 'pendiente'),
                            'personas': personas,
                            'notas': request.form.get('notas', '').strip()
                        }
                        
                        # Manejo de cancelación
                        if request.form.get('estado') == 'cancelada' and not documento.get('fecha_cancelacion'):
                            data['fecha_cancelacion'] = datetime.utcnow()
                            data['motivo_cancelacion'] = request.form.get('motivo_cancelacion', '')
                    except ValueError as e:
                        flash('Formato de fecha incorrecto o datos inválidos', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))
                    except Exception as e:
                        flash(f'Error al procesar la reservación: {str(e)}', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))

                elif collection == "pagos":
                    try:
                        monto = float(request.form.get('monto', 0))
                        if monto <= 0:
                            flash('El monto debe ser mayor a 0', 'danger')
                            return redirect(url_for('edit', collection=collection, id=id))
                        
                        data = {
                            'monto': monto,
                            'metodo': request.form.get('metodo', 'efectivo'),
                            'estado': request.form.get('estado', 'pendiente'),
                            'transaccion_id': request.form.get('transaccion_id', '').strip(),
                            'codigo_autorizacion': request.form.get('codigo_autorizacion', '').strip()
                        }
                        
                        if data['metodo'] == 'tarjeta':
                            data['detalles'] = {
                                'tipo_tarjeta': request.form.get('tipo_tarjeta', '').strip(),
                                'ultimos_digitos': request.form.get('ultimos_digitos', '').strip()
                            }
                        
                        if request.form.get('estado') == 'reembolsado' and not documento.get('fecha_reembolso'):
                            data['fecha_reembolso'] = datetime.utcnow()
                            data['motivo_reembolso'] = request.form.get('motivo_reembolso', '')
                    except ValueError as e:
                        flash('Datos del pago inválidos', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))

                elif collection == "mesas":
                    # Validación para mesas
                    try:
                        numero = int(request.form.get('numero', 0))
                        capacidad = int(request.form.get('capacidad', 2))
                        
                        if numero <= 0 or capacidad <= 0:
                            flash('Número y capacidad deben ser mayores a 0', 'danger')
                            return redirect(url_for('edit', collection=collection, id=id))
                        
                        data = {
                            'numero': numero,
                            'capacidad': capacidad,
                            'ocupada': request.form.get('ocupada', 'false') == 'true',
                            'ubicacion': request.form.get('ubicacion', 'Interior').strip(),
                            'caracteristicas': [x.strip() for x in request.form.get('caracteristicas', '').split(',') if x.strip()],
                            'activa': request.form.get('activa', 'true') == 'true'
                        }
                    except ValueError as e:
                        flash('Datos de la mesa inválidos', 'danger')
                        return redirect(url_for('edit', collection=collection, id=id))

                # Actualizar el documento
                mongo.db[collection].update_one({'_id': ObjectId(id)}, {'$set': data})
                flash(f'{collection[:-1].capitalize()} actualizado correctamente', 'success')
                return redirect(url_for('gestion', collection=collection))
                
            except Exception as e:
                flash(f'Error al actualizar: {str(e)}', 'danger')
                return redirect(url_for('edit', collection=collection, id=id))

        return render_template('edit.html', collection=collection, documento=documento)
    
    except Exception as e:
        flash(f'Error al cargar el documento: {str(e)}', 'danger')
        return redirect(url_for('gestion', collection=collection))

# Eliminar documento
@app.route('/delete/<collection>/<id>', methods=['POST'])
@login_required
@admin_required
def delete(collection, id):
    if collection not in ["usuarios", "bebidas", "platos", "proveedores", "pedidos", "inventario", "reservaciones", "pagos", "mesas"]:
        abort(404)
    
    try:
        mongo.db[collection].delete_one({"_id": ObjectId(id)})
        flash(f'{collection[:-1].capitalize()} eliminado correctamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')
    
    return redirect(url_for('gestion', collection=collection))

if __name__ == '__main__':
    app.run(debug=True)