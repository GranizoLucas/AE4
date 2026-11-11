"""Persistencia CSV: lectura y reemplazo atómico de cada archivo."""
import csv
import os
import tempfile
from pathlib import Path

DATA = Path(__file__).parent / 'data'
SCHEMAS = {
    'usuarios': ['id', 'nombre', 'clave_hash', 'rol', 'activo'],
    'proveedores': ['id', 'nombre', 'telefono', 'activo'],
    'clientes': ['id', 'nombre', 'telefono', 'activo'],
    'productos': ['id', 'nombre', 'categoria', 'precio', 'stock', 'proveedor_id', 'activo'],
    'ventas': ['id', 'fecha', 'cliente_id', 'cajero_id', 'total', 'estado'],
    'detalle_ventas': ['id', 'venta_id', 'producto_id', 'cantidad', 'precio_unitario'],
}


def init_files():
    DATA.mkdir(exist_ok=True)
    for name, fields in SCHEMAS.items():
        path = DATA / f'{name}.csv'
        if not path.exists():
            write_all(name, [])


def read_all(name):
    if name not in SCHEMAS:
        raise ValueError('Archivo desconocido')
    path = DATA / f'{name}.csv'
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != SCHEMAS[name]:
            raise ValueError(f'Cabecera incorrecta en {path.name}')
        return list(reader)


def write_all(name, rows):
    if name not in SCHEMAS:
        raise ValueError('Archivo desconocido')
    DATA.mkdir(exist_ok=True)
    path = DATA / f'{name}.csv'
    fd, temp = tempfile.mkstemp(prefix=name + '_', suffix='.tmp', dir=DATA)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=SCHEMAS[name], extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def next_id(rows):
    return str(max([int(r['id']) for r in rows], default=0) + 1)
