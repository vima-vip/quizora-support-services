from sheets_client import buscar_faq

INTENCION_COMPRA_KEYWORDS = [
    "comprar", "inscribirme", "pagar", "suscribirme", "matricularme",
    "adquirir", "comprar suscripción"
]

FORM_URL = "https://tu-formulario.com"  # reemplaza con tu Google Form o formulario propio

def detectar_intencion_compra(mensaje: str) -> bool:
    m = mensaje.lower()
    return any(kw in m for kw in INTENCION_COMPRA_KEYWORDS)

def procesar_mensaje(mensaje: str):
    # 1. Intentar FAQ desde Sheet 1
    match = buscar_faq(mensaje)
    if match:
        respuesta = {
            "mensaje": match["respuesta"],
            "tipo": "faq",
            "categoria": match["categoria"]
        }
        if match["requiere_humano"]:
            respuesta["escalar"] = True
        return respuesta

    # 2. Detectar intención de compra
    if detectar_intencion_compra(mensaje):
        return {
            "mensaje": (
                "Para adquirir tu suscripción, realiza el pago por Yape "
                "y luego llena el formulario con tus datos y el código de transacción."
            ),
            "tipo": "venta",
            "form_url": FORM_URL
        }

    # 3. Fallback a asesor
    return {
        "mensaje": (
            "No encontré una respuesta automática para tu consulta. "
            "Te derivaré con un asesor del equipo de QUIZORA."
        ),
        "tipo": "escalar"
    }