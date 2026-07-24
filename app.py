from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime

from soporte import procesar_mensaje
from sheets_client import (
    obtener_registros_ventas,
    actualizar_registro_ventas,
    actualizar_notas_admin,
    registrar_venta,
)
from quizora_users import crear_usuario_quizora

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
    # template simple para incrustar o probar directamente
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
    # usa el template de pago/suscripción (puede ser modal_pago.html)
    return render_template("modal_pago.html")


# Registro de suscripción: guarda en QUIZORA_Ventas / REGISTROS_SUSCRIPCION
@app.post("/registro-suscripcion")
def registro_suscripcion():
    datos = request.json or {}

    try:
        registrar_venta(datos)
        return jsonify({"status": "ok"})
    except Exception as e:
        # aquí podrías logear el error con logging
        return jsonify({"status": "error", "detail": str(e)}), 500


# Worker: procesa registros Verificados y crea usuarios en Neon
@app.post("/procesar_verificados")
def procesar_verificados():
    rows = obtener_registros_ventas()
    procesados = []

    for idx, row in enumerate(rows, start=2):  # fila 2 = primera después de encabezados
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
