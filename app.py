from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from soporte import procesar_mensaje
from datetime import datetime
from sheets_client import obtener_registros_ventas, actualizar_registro_ventas
from quizora_users import crear_usuario_quizora
# app.py (worker)
from sheets_client import obtener_registros_ventas, actualizar_registro_ventas, actualizar_notas_admin

from sheets_client import registrar_venta


app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)  # permitir peticiones desde el dominio público de QUIZORA

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



@app.get("/form-suscripcion")
def form_suscripcion():
    return render_template("form_suscripcion.html")

@app.post("/registro-suscripcion")
def registro_suscripcion():
    datos = request.json or {}

    try:
        registrar_venta(datos)
        return jsonify({"status": "ok"})
    except Exception as e:
        # aquí podrías logear el error
        return jsonify({"status": "error", "detail": str(e)}), 500

@app.get("/")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})

@app.post("/webhook")
def webhook():
    payload = request.json or {}
    mensaje = payload.get("mensaje", "")
    origen = payload.get("origen", "widget_web")

    respuesta = procesar_mensaje(mensaje)
    respuesta["origen"] = origen
    return jsonify(respuesta)

@app.get("/widget")
def widget():
    # template simple para incrustar o probar directamente
    return render_template("widget.html")

# Worker (puedes llamar manualmente desde un cron HTTP en Render)
@app.post("/procesar_verificados")
def procesar_registros_verificados():
    rows = obtener_registros_ventas()

    for idx, row in enumerate(rows, start=2):  # empiezas en fila 2 por los encabezados
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)