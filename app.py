from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import os
import requests

from soporte import procesar_mensaje
from sheets_client import (
    obtener_registros_ventas,
    actualizar_registro_ventas,
    actualizar_notas_admin,
    registrar_venta,
    get_client,  # IMPORTANTE: reutilizar el cliente de sheets_client
)

# Ya no necesitas importar gspread ni Credentials aquí

from quizora_users import crear_usuario_quizora, asignar_quices_iniciales  # si sigues usando el worker

# Config QUIZORA
SPREADSHEET_ID = os.getenv("QUIZORA_VENTAS_SHEET_ID")  # puedes omitir si usas VENTAS_DOC_NAME/VENTAS_SHEET_NAME
QUIZORA_API_URL = os.getenv("QUIZORA_API_URL")
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN")


def obtener_suscripciones_pendientes():
    """
    Usa obtener_registros_ventas() (que ya está configurado con Sheets)
    y devuelve solo las filas en estado Pendiente.
    """
    rows = obtener_registros_ventas()  # lista de dicts con las columnas del Sheet

    pendientes = [
        row for row in rows
        if str(row.get("estado_verificacion", "")).strip().lower() == "pendiente"
    ]

    return pendientes


# Crear la app Flask
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)


# Healthcheck
@app.get("/")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


# Widget de chat
@app.get("/widget")
def widget():
    return render_template("widget.html")


# Webhook
@app.post("/webhook")
def webhook():
    payload = request.json or {}
    mensaje = payload.get("mensaje", "")
    origen = payload.get("origen", "widget_web")

    respuesta = procesar_mensaje(mensaje)
    respuesta["origen"] = origen
    return jsonify(respuesta)


# Formulario de suscripción
@app.get("/form-suscripcion")
def form_suscripcion():
    return render_template("modal_pago.html")



# Registro de suscripción
@app.post("/registro-suscripcion")
def registro_suscripcion():
    datos = request.form.to_dict() or {}

    dni = datos.get("dni", "").strip()
    especialidad = datos.get("especialidad", "").strip()

    # Si faltan datos clave, simplemente mostramos error
    if not dni or not especialidad:
        return render_template(
            "modal_pago.html",
            enviado_ok=False,
            error="Faltan datos de DNI o especialidad para registrar la suscripción."
        ), 400

    try:
        # 1. Revisar si ya existe una fila con mismo DNI y especialidad
        gc = get_client()
        sh = gc.open("QUIZORA_Ventas")              # mismo doc que usas en validar_suscripcion
        sheet = sh.worksheet("REGISTROS_SUSCRIPCION")

        # Leer todas las filas con datos (saltando encabezados)
        all_values = sheet.get_all_values()
        encabezados = all_values[0] if all_values else []

        # Índices de columnas según encabezado
        idx_dni = encabezados.index("dni") if "dni" in encabezados else 5   # F por defecto
        idx_esp = encabezados.index("especialidad") if "especialidad" in encabezados else 4  # E por defecto
        idx_estado = encabezados.index("estado_verificacion") if "estado_verificacion" in encabezados else 7

        existe_duplicado = False
        for row in all_values[1:]:  # desde la fila 2
            if len(row) <= max(idx_dni, idx_esp):
                continue
            dni_existente = row[idx_dni].strip()
            esp_existente = row[idx_esp].strip()
            estado_existente = row[idx_estado].strip() if len(row) > idx_estado else ""

            # Consideramos duplicado si ya hay una suscripción (Pendiente o Verificado) con mismo DNI+especialidad
            if dni_existente == dni and esp_existente == especialidad and estado_existente in ("Pendiente", "Verificado"):
                existe_duplicado = True
                break

        if existe_duplicado:
            # No registramos otra venta, solo avisamos en el mismo modal
            return render_template(
                "modal_pago.html",
                enviado_ok=False,
                error="Ya existe una suscripción pendiente o verificada con este DNI y especialidad. "
                      "Espera la validación o contacta al soporte."
            ), 200

        # 2. Si no hay duplicado, registramos normalmente
        registrar_venta(datos)
        return render_template("modal_pago.html", enviado_ok=True)

    except Exception as e:
        return render_template(
            "modal_pago.html",
            enviado_ok=False,
            error=str(e)
        ), 500


# Dashboard admin
@app.get("/admin/suscripciones")
def admin_suscripciones():
    suscripciones = obtener_suscripciones_pendientes()
    return render_template("admin_suscripciones.html", suscripciones=suscripciones)


# Acción de VALIDAR
@app.post("/admin/validar-suscripcion")
def validar_suscripcion():
    id_registro = request.form.get("id_registro")
    if not id_registro:
        return redirect(url_for("admin_suscripciones"))

    gc = get_client()
    sh = gc.open("QUIZORA_Ventas")  # usamos VENTAS_DOC_NAME de sheets_client
    sheet = sh.worksheet("REGISTROS_SUSCRIPCION")  # VENTAS_SHEET_NAME

    # 1. Buscar la fila por id_registro
    celdas_id = sheet.findall(id_registro)
    if not celdas_id:
        return redirect(url_for("admin_suscripciones"))

    fila_idx = celdas_id[0].row
    valores = sheet.row_values(fila_idx)
    encabezados = sheet.row_values(1)
    row = {encabezados[i]: valores[i] if i < len(valores) else "" for i in range(len(encabezados))}

    # 2. Marcar estado Verificado
    sheet.update_cell(fila_idx, 8, "Verificado")  # H: estado_verificac

    # 3. Tomar usuario, contraseña y especialidad
    username = row.get("usuario_generado")
    raw_password = row.get("password_generado")
    specialty_code = row.get("especialidad")
    plan = "premium"

    # 4. Llamar a QUIZORA
    resp = requests.post(
        f"{QUIZORA_API_URL}/superadmin/api/register",
        json={
            "username": username,
            "password": raw_password,
            "specialty_code": specialty_code,
            "plan": plan,
        },
        headers={"X-QUIZORA-ADMIN-TOKEN": ADMIN_API_TOKEN},
        timeout=10,
    )

    if resp.status_code == 200:
        data = resp.json()
        sheet.update_cell(fila_idx, 11, datetime.utcnow().isoformat())  # K: fecha_activacion
        nota = f"Usuario creado en QUIZORA (id={data.get('user_id')})"
        sheet.update_cell(fila_idx, 12, nota)
    else:
        sheet.update_cell(fila_idx, 12, f"Error al crear usuario: {resp.text}")

    return redirect(url_for("admin_suscripciones"))


# Worker opcional (si sigues usando flujo directo a Neon)
@app.post("/procesar_verificados")
def procesar_verificados():
    rows = obtener_registros_ventas()
    procesados = []

    for idx, row in enumerate(rows, start=2):
        if row["estado_verificacion"] == "Verificado" and not row["usuario_generado"]:
            resultado = crear_usuario_quizora(row)
            nota_extra = ""
            if resultado["num_iniciales_usadas"] == 3:
                nota_extra = "Username creado con 3 iniciales por colisión."

            actualizar_registro_ventas(
                row_index=idx,
                usuario_generado=resultado["username"],
                password_generado_hash=resultado["password_hash"],
                fecha_activacion_iso=datetime.utcnow().isoformat()
            )

            if nota_extra:
                actualizar_notas_admin(idx, nota_extra)

            procesados.append(resultado["username"])

    return jsonify({"procesados": procesados})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
