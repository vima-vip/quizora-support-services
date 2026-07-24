import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Dict, List, Optional
import uuid
from datetime import datetime

SHEET_FAQ_NAME = "AUTO_QUIZORA"  # nombre del sheet que muestras en la captura 
SHEET_VENTAS_DOC = "QUIZORA_Ventas"
SHEET_VENTAS_NAME = "REGISTROS_SUSCRIPCION"

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]




def get_client():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "service_account.json",  # pon este JSON en tu repo o como volumen
        scope
    )
    return gspread.authorize(creds)

def buscar_faq(mensaje: str) -> Optional[Dict]:
    gc = get_client()
    sh = gc.open(SHEET_NAME)
    sheet = sh.worksheet(SHEET_FAQ_NAME)
    rows = sheet.get_all_records()

    mensaje_lower = mensaje.lower()

    for row in rows:
        if row["activa"].strip().lower() != "si":
            continue

        keyword = str(row["keyword"]).lower().strip()
        # matching simple: si el keyword está contenido en el mensaje
        if keyword and keyword in mensaje_lower:
            return {
                "respuesta": row["respuesta"],
                "keyword": keyword
            }

    return None

def registrar_venta(datos: dict):
    """
    datos debe contener: nombres, primer_apellido, especialidad, dni, codigo_transaccion_yape
    """
    gc = get_client()
    sh = gc.open(SHEET_VENTAS_DOC)
    sheet = sh.worksheet(SHEET_VENTAS_NAME)

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
    sh = gc.open(SHEET_NAME)
    sheet = sh.worksheet(SHEET_VENTAS_NAME)
    return sheet.get_all_records()

def actualizar_notas_admin(row_index: int, nota: str):
    gc = get_client()
    sh = gc.open(SHEET_NAME)
    sheet = sh.worksheet(SHEET_VENTAS_NAME)
    # notas_admin es la columna 13 según tu estructura [file:1]
    sheet.update_cell(row_index, 13, nota)

def actualizar_registro_ventas(
    row_index: int,
    usuario_generado: str,
    password_generado_hash: str,
    fecha_activacion_iso: str
):
    gc = get_client()
    sh = gc.open(SHEET_NAME)
    sheet = sh.worksheet(SHEET_VENTAS_NAME)
    sheet.update_cell(row_index, 10, usuario_generado)       # usuario_generado [file:1]
    sheet.update_cell(row_index, 11, password_generado_hash) # password_generado [file:1]
    sheet.update_cell(row_index, 12, fecha_activacion_iso)   # fecha_activacion [file:1]
    
def actualizar_notas_admin(row_index: int, nota: str):
    gc = get_client()
    sh = gc.open(SHEET_VENTAS_DOC)
    sheet = sh.worksheet(SHEET_VENTAS_NAME)
    sheet.update_cell(row_index, 12, nota)  # notas_admin