import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Nombres de documentos y hojas
FAQ_DOC_NAME = "AUTO_QUIZORA"          # nombre del documento (libro) de FAQ
FAQ_SHEET_NAME = "BD"                  # nombre de la hoja/tab dentro de AUTO_QUIZORA

VENTAS_DOC_NAME = "QUIZORA_Ventas"     # nombre del documento de ventas
VENTAS_SHEET_NAME = "REGISTROS_SUSCRIPCION"  # hoja/tab de ventas

# Ruta del service account (puedes usar variable de entorno en Render)
SERVICE_ACCOUNT_PATH = os.getenv("GSPREAD_SERVICE_ACCOUNT_PATH", "service_account.json")

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
    rows = sheet.get_all_records()  # espera columnas: keyword, respuesta, activa

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


# ===== Ventas (QUIZORA_Ventas / REGISTROS_SUSCRIPCION) =====

def registrar_venta(datos: dict):
    """
    datos debe contener: nombres, primer_apellido, especialidad, dni, codigo_transaccion_yape
    """
    gc = get_client()
    sh = gc.open(VENTAS_DOC_NAME)
    sheet = sh.worksheet(VENTAS_SHEET_NAME)

    id_registro = f"REG-{uuid.uuid4().hex[:8]}"
    fecha_hora = datetime.utcnow().isoformat()

    fila = [
        id_registro,                         # id_registro
        fecha_hora,                          # fecha_hora
        datos.get("nombres", ""),            # nombres
        datos.get("primer_apellido", ""),    # primer_apellido
        datos.get("especialidad", ""),       # especialidad
        datos.get("dni", ""),                # dni
        datos.get("codigo_transaccion_yape", ""),  # codigo_transaccion_yape
        "Pendiente",                         # estado_verificacion
        "",                                  # usuario_generado
        "",                                  # password_generado
        "",                                  # fecha_activacion
        ""                                   # notas_admin
    ]

    sheet.append_row(fila)


def obtener_registros_ventas() -> List[Dict]:
    gc = get_client()
    sh = gc.open(VENTAS_DOC_NAME)
    sheet = sh.worksheet(VENTAS_SHEET_NAME)
    return sheet.get_all_records()


def actualizar_registro_ventas(
    row_index: int,
    usuario_generado: str,
    password_generado_hash: str,
    fecha_activacion_iso: str
):
    gc = get_client()
    sh = gc.open(VENTAS_DOC_NAME)
    sheet = sh.worksheet(VENTAS_SHEET_NAME)
    sheet.update_cell(row_index, 9, usuario_generado)        # usuario_generado
    sheet.update_cell(row_index, 10, password_generado_hash) # password_generado
    sheet.update_cell(row_index, 11, fecha_activacion_iso)   # fecha_activacion


def actualizar_notas_admin(row_index: int, nota: str):
    gc = get_client()
    sh = gc.open(VENTAS_DOC_NAME)
    sheet = sh.worksheet(VENTAS_SHEET_NAME)
    sheet.update_cell(row_index, 12, nota)  # notas_admin
