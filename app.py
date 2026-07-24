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
)

import gspread
from google.oauth2.service_account import Credentials

# ya no usamos crear_usuario_quizora/asignar_quices_iniciales aquí
# from quizora_users import crear_usuario_quizora, asignar_quices_iniciales

# Config Sheets y QUIZORA
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("QUIZORA_VENTAS_SHEET_ID")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
QUIZORA_API_URL = os.getenv("QUIZORA_API_URL")
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN")  # mismo valor que en QUIZORA


def get_sheet_client():
    """
    Devuelve un cliente gspread autorizado con el service account.
    """
    if not SERVICE_ACCOUNT_JSON:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON no está configurado.")
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_JSON,
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client


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
CORS(app)  # permitir peticiones desde el dominio público de QUIZORA


# Healthcheck
@app.get("/")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


# Widget de chat (iframe)
@app.get("/widget")
def widget():
    return render_template("widget.html")


# Webhook del widget
@app.post("/webhook")
def webhook():
    payload = request.json or {}
    mensaje = payload.get("mensaje", "")
    origen = payload.get("origen", "widget_web")

    respuesta = procesar_mensaje(mensaje)
    respuesta["origen"] = origen
    return jsonify(respuesta)


# Formulario de suscripción + QR (modal de pago)
@app.get("/form-suscripcion")
def form_suscripcion():
    return render_template("modal_pago.html")


# Registro de suscripción: guarda en QUIZORA_Ventas / REGISTROS_SUSCRIPCION
@app.post("/registro-suscripcion")
def registro_suscripcion():
    datos = request.json or {}

    try:
        registrar_venta(datos)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


# DASHBOARD: lista suscripciones pendientes para el admin
@app.get("/admin/suscripciones")
def admin_suscripciones():
    suscripciones = obtener_suscripciones_pendientes()
    return render_template("admin_suscripciones.html", suscripciones=suscripciones)


# Acción de VALIDAR: clic del admin que dispara creación de usuario en QUIZORA
@app.post("/admin/validar-suscripcion")
def validar_suscripcion():
    id_registro = request.form.get("id_registro")
    if not id_registro:
        return redirect(url_for("admin_suscripciones"))

    client = get_sheet_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet("REGISTROS_SUSCRIPCION")

    # 1. Buscar la fila por id_registro
    celdas_id = sheet.findall(id_registro)
    if not celdas_id:
        return redirect(url_for("admin_suscripciones"))

    fila_idx = celdas_id[0].row
    valores = sheet.row_values(fila_idx)
    encabezados = sheet.row_values(1)
    row = {encabezados[i]: valores[i] if i < len(valores) else "" for i in range(len(encabezados))}

    # 2. Marcar estado Verificado en el Sheet
    sheet.update_cell(fila_idx, 8, "Verificado")  # H: estado_verificac

    # 3. Tomar usuario, contraseña y especialidad desde el Sheet
    username = row.get("usuario_generado")
    raw_password = row.get("password_generado")
    specialty_code = row.get("especialidad")
    plan = "premium"

    # 4. Llamar al endpoint interno de QUIZORA
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
        # 5. Actualizar fecha_activacion y notas_admin en el Sheet
        sheet.update_cell(fila_idx, 11, datetime.utcnow().isoformat())  # K: fecha_activacion
        nota = f"Usuario creado en QUIZORA (id={data.get('user_id')})"
        sheet.update_cell(fila_idx, 12, nota)                            # L: notas_admin
    else:
        # Dejar constancia del error
        sheet.update_cell(fila_idx, 12, f"Error al crear usuario: {resp.text}")

    return redirect(url_for("admin_suscripciones"))


# Si de momento no vas a usar el worker directo a Neon, puedes comentarlo o dejarlo:
# @app.post("/procesar_verificados")
# def procesar_verificados():
#     ...


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
