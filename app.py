from flask import render_template, request, redirect, url_for, flash
from bson.objectid import ObjectId
from config import app, mongo
from flask import send_from_directory

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/<collection>')
def index(collection):
    if collection not in ["empleados", "clientes", "bebidas", "platos", "proveedores", "pedidos", "inventario", "reservaciones", "pagos", "mesas"]:
        return redirect(url_for('home'))

    documentos = mongo.db[collection].find()
    return render_template('index.html', collection=collection, documentos=documentos)

# Agregar 
@app.route('/add/<collection>', methods=['POST'])
def add_document(collection):
    if collection == "empleados":
        data = {
            'nombre': request.form['nombre'],
            'puesto': request.form['puesto'],
            'salario': int(request.form['salario']),
            'telefono': request.form['telefono']
        }
    elif collection == "clientes":
        data = {
            'nombre': request.form['nombre'],
            'telefono': request.form['telefono'],
            'email': request.form['email'],
            'direccion': request.form['direccion']
        }
    elif collection == "bebidas":
        data = {
            'nombre': request.form['nombre'],
            'precio': int(request.form['precio']),
            'descripcion': request.form['descripcion'],
            'categoria': request.form['categoria']
        }
    elif collection == "platos":
        data = {
            'nombre': request.form['nombre'],
            'precio': int(request.form['precio']),
            'descripcion': request.form['descripcion'],
            'categoria': request.form['categoria']
        }
    elif collection == "proveedores":
        data = {
            'nombre': request.form['nombre'],
            'contacto': request.form['contacto'],
            'telefono': request.form['telefono'],
            'producto': request.form['producto'],
            'direccion': request.form['direccion']
        }
    elif collection == "pedidos":
        cliente_id = request.form['cliente_id']
        plato_id = request.form['plato_id']
        cantidad = int(request.form['cantidad'])
        
        data = {
            'cliente_id': ObjectId(cliente_id),
            'platos': [
                {
                    'plato_id': ObjectId(plato_id),
                    'cantidad': cantidad
                }
            ],
            'fecha': request.form['fecha'],
            'estado': request.form['estado']
        }
    elif collection == "inventario":
        data = {
            'producto': request.form['producto'],
            'cantidad': int(request.form['cantidad']),
            'unidad': request.form['unidad'],
            'proveedor': request.form['proveedor']
        }
    elif collection == "reservaciones":
        data = {
            'cliente': request.form['cliente'],
            'mesa': int(request.form['mesa']),
            'fecha': request.form['fecha'],
            'hora': request.form['hora'],
            'estado': request.form['estado']
        }
    elif collection == "pagos":
        data = {
            'cliente': request.form['cliente'],
            'monto': int(request.form['monto']),
            'metodo': request.form['metodo'],
            'estado': request.form['estado']
        }
    elif collection == "mesas":
        data = {
            'numero': int(request.form['numero']),
            'capacidad': int(request.form['capacidad']),
            'ocupada': request.form['ocupada'] == 'true'
        }

    mongo.db[collection].insert_one(data)
    flash(f'{collection[:-1].capitalize()} agregado correctamente', 'success')
    return redirect(url_for('index', collection=collection))

# Editar
@app.route('/edit/<collection>/<id>', methods=['GET', 'POST'])
def edit_document(collection, id):
    documento = mongo.db[collection].find_one({"_id": ObjectId(id)})

    if request.method == 'POST':
        if collection == "empleados":
            data = {
                'nombre': request.form['nombre'],
                'puesto': request.form['puesto'],
                'salario': int(request.form['salario']),
                'telefono': request.form['telefono']
            }
        elif collection == "clientes":
            data = {
                'nombre': request.form['nombre'],
                'telefono': request.form['telefono'],
                'email': request.form['email'],
                'direccion': request.form['direccion']
            }
        elif collection == "bebidas":
            data = {
                'nombre': request.form['nombre'],
                'precio': int(request.form['precio']),
                'descripcion': request.form['descripcion'],
                'categoria': request.form['categoria']
            }
        elif collection == "platos":
            data = {
                'nombre': request.form['nombre'],
                'precio': int(request.form['precio']),
                'descripcion': request.form['descripcion'],
                'categoria': request.form['categoria']
            }
        elif collection == "proveedores":
            data = {
                'nombre': request.form['nombre'],
                'contacto': request.form['contacto'],
                'telefono': request.form['telefono'],
                'producto': request.form['producto'],
                'direccion': request.form['direccion']
            }
        elif collection == "pedidos":
            cliente_id = request.form['cliente_id']
            plato_id = request.form['plato_id']
            cantidad = int(request.form['cantidad'])
            
            data = {
                'cliente_id': ObjectId(cliente_id),
                'platos': [
                    {
                        'plato_id': ObjectId(plato_id),
                        'cantidad': cantidad
                    }
                ],
                'fecha': request.form['fecha'],
                'estado': request.form['estado']
            }
        elif collection == "inventario":
            data = {
                'producto': request.form['producto'],
                'cantidad': int(request.form['cantidad']),
                'unidad': request.form['unidad'],
                'proveedor': request.form['proveedor']
            }
        elif collection == "reservaciones":
            data = {
                'cliente': request.form['cliente'],
                'mesa': int(request.form['mesa']),
                'fecha': request.form['fecha'],
                'hora': request.form['hora'],
                'estado': request.form['estado']
            }
        elif collection == "pagos":
            data = {
                'cliente': request.form['cliente'],
                'monto': int(request.form['monto']),
                'metodo': request.form['metodo'],
                'estado': request.form['estado']
            }
        elif collection == "mesas":
            data = {
                'numero': int(request.form['numero']),
                'capacidad': int(request.form['capacidad']),
                'ocupada': request.form['ocupada'] == 'true'
            }

        mongo.db[collection].update_one({"_id": ObjectId(id)}, {"$set": data})
        flash(f'{collection[:-1].capitalize()} actualizado correctamente', 'success')
        return redirect(url_for('index', collection=collection))

    return render_template('edit.html', collection=collection, documento=documento)

# Eliminar documento
@app.route('/delete/<collection>/<id>')
def delete_document(collection, id):
    mongo.db[collection].delete_one({"_id": ObjectId(id)})
    flash(f'{collection[:-1].capitalize()} eliminado correctamente', 'danger')
    return redirect(url_for('index', collection=collection))

if __name__ == '__main__':
    app.run(debug=True)