import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Nombres de documentos y hojas
FAQ_DOC_NAME = "AUTO_QUIZORA"
FAQ_SHEET_NAME = "BD"

VENTAS_DOC_NAME = "QUIZORA_Ventas"
VENTAS_SHEET_NAME = "REGISTROS_SUSCRIPCION"

# Ruta del service account
SERVICE_ACCOUNT_PATH = os.getenv(
    "GSPREAD_SERVICE_ACCOUNT_PATH",
    "service_account.json"
)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def get_client():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        SERVICE_ACCOUNT_PATH,
        scope
    )
    return gspread.authorize(creds)


# ===== FAQ (AUTO_QUIZORA / BD) =====

def buscar_faq(mensaje: str) -> Optional[Dict]:
    gc = get_client()
    sh = gc.open(FAQ_DOC_NAME)
    sheet = sh.worksheet(FAQ_SHEET_NAME)

    rows = sheet.get_all_records()
    mensaje_lower = mensaje.lower()

    for row in rows:
        if str(row.get("activa", "")).strip().lower() != "si":
            continue

        keyword = str(row.get("keyword", "")).lower().strip()

        if keyword and keyword in mensaje_lower:
            return {
                "respuesta": row.get("respuesta", ""),
                "keyword": keyword
            }

    return None


def obtener_keywords_quizora() -> List[Dict]:
    gc = get_client()
    sh = gc.open(FAQ_DOC_NAME)
    sheet = sh.worksheet(FAQ_SHEET_NAME)

    return sheet.get_all_records()


# ===== Ventas (QUIZORA_Ventas / REGISTROS_SUSCRIPCION) =====

def registrar_venta(datos: dict):
    """
    Registra una suscripción pendiente.

    datos debe incluir:
    nombres, primer_apellido, especialidad, dni, telefono,
    codigo_transaccion_yape, usuario_generado y password_generado.
    """
    gc = get_client()
    sh = gc.open(VENTAS_DOC_NAME)
    sheet = sh.worksheet(VENTAS_SHEET_NAME)

    id_registro = f"REG-{uuid.uuid4().hex[:8]}"
    fecha_hora = datetime.utcnow().isoformat()

    fila = [
        id_registro,                                     # A: id_registro
        fecha_hora,                                      # B: fecha_hora
        datos.get("nombres", "").strip(),                # C: nombres
        datos.get("primer_apellido", "").strip(),        # D: primer_apellido
        datos.get("especialidad", "").strip(),           # E: especialidad
        datos.get("dni", "").strip(),                    # F: dni
        datos.get("telefono", "").strip(),               # G: telefono
        datos.get("codigo_transaccion_yape", "").strip(),# H: codigo_transaccion_yape
        "Pendiente",                                     # I: estado_verificacion
        datos.get("usuario_generado", "").strip(),       # J: usuario_generado
        datos.get("password_generado", "").strip(),      # K: password_generado
        "",                                              # L: fecha_activacion
        ""                                               # M: notas_admin
    ]

    sheet.append_row(fila, value_input_option="RAW")


def obtener_registros_ventas() -> List[Dict]:
    gc = get_client()
    sh = gc.open(VENTAS_DOC_NAME)
    sheet = sh.worksheet(VENTAS_SHEET_NAME)

    return sheet.get_all_records()


def actualizar_registro_ventas(
    row_index: int,
    usuario_generado: str,
    password_generado: str,
    fecha_activacion_iso: str
):
    """
    Flujo opcional directo a Neon.
    Si lo usas, escribe el usuario y password indicado en J y K.
    """
    gc = get_client()
    sh = gc.open(VENTAS_DOC_NAME)
    sheet = sh.worksheet(VENTAS_SHEET_NAME)

    sheet.batch_update([
        {
            "range": f"J{row_index}",
            "values": [[usuario_generado]]
        },
        {
            "range": f"K{row_index}",
            "values": [[password_generado]]
        },
        {
            "range": f"L{row_index}",
            "values": [[fecha_activacion_iso]]
        }
    ])


def actualizar_notas_admin(row_index: int, nota: str):
    gc = get_client()
    sh = gc.open(VENTAS_DOC_NAME)
    sheet = sh.worksheet(VENTAS_SHEET_NAME)

    sheet.update_cell(row_index, 13, nota)
