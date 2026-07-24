from sheets_client import buscar_faq

# Palabras que indican intención de compra / suscripción
INTENCION_COMPRA_KEYWORDS = [
    "comprar", "inscribirme", "pagar", "suscribirme", "matricularme",
    "adquirir", "comprar suscripción", "crear cuenta", "quiero una cuenta",
    "quiero que me crees una cuenta", "ya pagué", "ya te pagué"
]

# URL del formulario de suscripción del microservicio
FORM_URL = "https://quizora-support.onrender.com/form-suscripcion"


def detectar_intencion_compra(mensaje: str) -> bool:
    m = mensaje.lower()
    return any(kw in m for kw in INTENCION_COMPRA_KEYWORDS)


def procesar_mensaje(mensaje: str):
    # 1. Intentar FAQ desde AUTO_QUIZORA / BD
    match = buscar_faq(mensaje)
    if match:
        # match tiene: "respuesta" y "keyword"
        return {
            "mensaje": match["respuesta"],
            "tipo": "faq",
            "keyword": match["keyword"]
        }

    # 2. Detectar intención de compra
    if detectar_intencion_compra(mensaje):
        return {
            "mensaje": (
                "Para adquirir tu suscripción en QUIZORA, realiza el pago por Yape "
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
