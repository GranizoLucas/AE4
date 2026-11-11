# SuperGestión AE4 · Programación I

Primera versión funcional de un sistema de gestión de supermercado con **frontend web**, **backend Python** y **persistencia CSV**, desarrollada como punto de partida para investigación, pruebas y defensa oral.

## Cómo instalar y abrir en Windows

1. Instalar Python 3.11 o superior y marcar **Add Python to PATH**.
2. Descomprimir la carpeta completa y abrir una terminal dentro de `supergestion_ae4`.
3. Ejecutar:

```powershell
py -m pip install -r requirements.txt
py app.py
```

4. Abrir http://127.0.0.1:5000/ en el navegador.
5. Ingresar inicialmente con **admin** / **Admin123!**. Son credenciales **solo para demostración local**. No se debe exponer esta aplicación a Internet ni conservar esa clave para usos reales.
6. Detener con `Ctrl + C`.

Si `py` no está disponible, probar `python` en su lugar. Los CSV aparecen automáticamente dentro de `data/` después del primer inicio.

## Orden recomendado de la demostración

1. Entrar como administrador y crear un proveedor.
2. Crear un producto asociado con precio y stock.
3. Registrar un cliente y crear un cajero desde Usuarios.
4. Salir y entrar como cajero. Registrar una venta y comprobar la reducción de stock.
5. Salir, volver como administrador y revisar Reportes. Comparar las cantidades de la matriz con las ventas realizadas.
6. Entrar con un encargado para mostrar que solo ve las opciones autorizadas.

## Conceptos para la defensa oral

- **Roles / RBAC:** `PERMISOS` define qué rol puede acceder a cada sección; `requires()` y `authorized()` verifican la operación en el servidor y no solo ocultan enlaces.
- **Diccionarios:** cada fila CSV se carga como un diccionario con campos nombrados; permiten entender mejor los datos y realizar búsquedas por IDs.
- **Listas:** `read_all()` devuelve una lista de diccionarios.
- **Matriz dinámica:** `reports()` construye una lista de listas; cada fila representa una categoría que figura en las ventas y cada columna un día de la semana. Se recorre para calcular los totales.
- **Persistencia:** `storage.py` guarda cada archivo CSV mediante escritura temporal y `os.replace()` para evitar que un corte a mitad de una escritura parcial destruya un archivo.
- **Seguridad:** las contraseñas se almacenan con PBKDF2-HMAC y sal aleatoria, no reversibles. Un administrador no puede desactivarse a sí mismo ni dejar cero administradores activos.
- **Validaciones:** se revisa existencia de productos/clientes, stock suficiente, campos obligatorios, números válidos, permisos y formularios.

## Alcance de esta primera versión (MVP)

Incluye login, tres roles, alta de productos/proveedores/clientes/usuarios, desactivación lógica, una venta de **un solo producto**, reducción de stock, tablero y reporte matricial por categoría × día semanal.

**Pendiente para versión integradora:** edición de registros, ventas de múltiples productos, estados pendiente/cancelada, restauración de usuarios, ajuste de stock y registro de reposiciones, pruebas automatizadas más completas, diagrama/pseudocódigo, investigación real del supermercado y elaboración de informe, portafolio y bitácoras.

**Limitación técnica conocida:** las escrituras se realizan atómicamente **por cada CSV**, no hay transacción conjunta entre `productos.csv`, `ventas.csv` y `detalle_ventas.csv`, ni bloqueo para varios usuarios simultáneos. Por eso, esta versión se usa **localmente con un único operador a la vez** y no está lista para despliegue público. La protección CSRF es básica. Tampoco hay recuperación de contraseñas ni cambio de contraseña desde la interfaz.

## Estructura

```text
app.py                Flask, rutas, reglas y reportes
storage.py            Lectura/escritura de archivos CSV
templates/            Pantallas HTML con Jinja
static/style.css      Diseño visual
data/*.csv            Datos persistentes (se crean al iniciar)
requirements.txt      Dependencia de Flask
```

## Evidencias a guardar para el portafolio

Capturas del login, roles distintos, alta de producto, venta, archivo CSV antes/después de la venta, reporte de matriz y un error controlado (stock insuficiente). Registrar fecha, autor, qué se probó, resultado esperado y observado.
