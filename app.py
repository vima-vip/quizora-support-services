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
import gspread
from google.oauth2.service_account import Credentials

from quizora_users import crear_usuario_quizora, asignar_quices_iniciales

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
    # admin_suscripciones.html mostrará la tabla con botón "Validar"
    return render_template("admin_suscripciones.html", suscripciones=suscripciones)


# Acción de VALIDAR: clic del admin que dispara creación de usuario
@app.post("/admin/validar-suscripcion")
def validar_suscripcion():
    id_registro = request.form.get("id_registro")

    if not id_registro:
        return redirect(url_for("admin_suscripciones"))

    # 1. Leer todas las ventas y encontrar la fila correspondiente
    rows = obtener_registros_ventas()
    row = next((r for r in rows if str(r.get("id_registro")) == id_registro), None)

    if not row:
        return redirect(url_for("admin_suscripciones"))

    # 2. Crear usuario en Neon con tus reglas
    resultado = crear_usuario_quizora(row)

    # 3. Asignar cuestionarios iniciales según especialidad
    specialty_code = row.get("especialidad")
    asignar_quices_iniciales(resultado["user_id"], specialty_code)

    # 4. Actualizar registro de ventas (usuario, hash, fecha activación)
    # aquí usas tu helper actualizar_registro_ventas según su firma
    actualizar_registro_ventas(
        row_index=row.get("row_index"),           # ajusta según cómo lo implementaste
        usuario_generado=resultado["username"],
        password_generado_hash=resultado["password_hash"],
        fecha_activacion_iso=datetime.utcnow().isoformat(),
    )

    # 5. Notas admin
    nota = "Validado desde dashboard admin QUIZORA."
    if resultado["num_iniciales_usadas"] == 3:
        nota += " Username creado con 3 iniciales por colisión."
    actualizar_notas_admin(row.get("row_index"), nota)

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
