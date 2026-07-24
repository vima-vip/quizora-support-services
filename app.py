from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import os

from soporte import procesar_mensaje
from sheets_client import (
    obtener_registros_ventas,
    actualizar_registro_ventas,
    actualizar_notas_admin,
    registrar_venta,
)
from quizora_users import procesar_registro_ventas  # usa crear_usuario_quizora + asignar quices + actualizar sheet

import gspread
from google.oauth2.service_account import Credentials

# Config Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("QUIZORA_VENTAS_SHEET_ID")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")


def get_sheet_client():
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_JSON,
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client


def obtener_suscripciones_pendientes():
    """
    Lee la hoja REGISTROS_SUSCRIPCION y devuelve solo las filas en estado Pendiente.
    """
    client = get_sheet_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet("REGISTROS_SUSCRIPCION")

    rows = sheet.get_all_records()  # usa fila 1 como encabezados

    pendientes = [
        row for row in rows
        if str(row.get("estado_verificac", "")).strip().lower() == "pendiente"
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
    # admin_suscripciones.html mostrará la tabla con botón "Validar"
    return render_template("admin_suscripciones.html", suscripciones=suscripciones)


# Acción de VALIDAR: clic del admin que dispara creación de usuario
@app.post("/admin/validar-suscripcion")
def validar_suscripcion():
    id_registro = request.form.get("id_registro")

    if not id_registro:
        return redirect(url_for("admin_suscripciones"))

    client = get_sheet_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet("REGISTROS_SUSCRIPCION")

    # Buscar la fila por id_registro
    celdas_id = sheet.findall(id_registro)
    if not celdas_id:
        return redirect(url_for("admin_suscripciones"))

    fila_idx = celdas_id[0].row

    # Leer la fila completa (A-L) y armar dict con encabezados
    valores = sheet.row_values(fila_idx)
    encabezados = sheet.row_values(1)

    row_dict = {encabezados[i]: valores[i] if i < len(valores) else "" for i in range(len(encabezados))}

    # Marcar estado_verificac como Verificado en el Sheet
    sheet.update_cell(fila_idx, 8, "Verificado")  # H: estado_verificac

    # Procesar registro: crear usuario en Neon, asignar quices, actualizar credenciales y fecha_activacion
    procesar_registro_ventas(row_dict)

    # Opcional: notas_admin
    actualizar_notas_admin(fila_idx, "Validado desde dashboard admin QUIZORA.")

    return redirect(url_for("admin_suscripciones"))


# Worker antiguo: si deseas seguir procesando verificados en lote vía API
@app.post("/procesar_verificados")
def procesar_verificados():
    rows = obtener_registros_ventas()
    procesados = []

    for idx, row in enumerate(rows, start=2):  # fila 2 = primera después de encabezados
        if row["estado_verificacion"] == "Verificado" and not row["usuario_generado"]:
            # aquí podrías reutilizar procesar_registro_ventas(row) directamente
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
