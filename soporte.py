from unidecode import unidecode        # pip install unidecode
from rapidfuzz import fuzz             # pip install rapidfuzz
from sheets_client import buscar_faq, obtener_keywords_quizora

# Palabras que indican intención de compra / suscripción
INTENCION_COMPRA_KEYWORDS = [
    "comprar", "inscribirme", "pagar", "suscribirme", "matricularme",
    "adquirir", "comprar suscripción", "crear cuenta", "quiero una cuenta",
    "quiero que me crees una cuenta", "acceso", "como hago para tener una cuenta"
]

# URL del formulario de suscripción del microservicio
FORM_URL = "https://quizora-support.onrender.com/form-suscripcion"


def detectar_intencion_compra(mensaje: str) -> bool:
    m = mensaje.lower()
    return any(kw in m for kw in INTENCION_COMPRA_KEYWORDS)


def normalizar(texto: str) -> str:
    """
    Minúsculas, sin tildes, espacios colapsados.
    Ej: 'Hola, cómo estás?' -> 'hola, como estas?'
    """
    if not texto:
        return ""
    texto = unidecode(texto.lower().strip())
    return " ".join(texto.split())


def encontrar_mejor_faq(mensaje: str, umbral: int = 80):
    """
    Busca el FAQ más parecido al mensaje, usando similitud >= umbral.
    Usa la hoja AUTO_QUIZORA a través de obtener_keywords_quizora().
    Devuelve un dict con 'keyword' y 'respuesta' o None.
    """
    texto_norm = normalizar(mensaje)

    # Traer keywords desde Sheets (AUTO_QUIZORA)
    faqs = obtener_keywords_quizora()  # lista de dicts: {"keyword": ..., "respuesta": ..., "activa": ...}
    activos = [
        f for f in faqs
        if str(f.get("activa", "")).strip().lower() == "si"
    ]

    mejor_ratio = 0
    mejor_faq = None

    for faq in activos:
        kw = faq.get("keyword", "")
        kw_norm = normalizar(kw)

        ratio = fuzz.ratio(texto_norm, kw_norm)  # 0-100
        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor_faq = faq

    if mejor_faq and mejor_ratio >= umbral:
        return mejor_faq
    return None


def procesar_mensaje(mensaje: str):
    # 1. Intentar responder con FAQ usando coincidencia borrosa (>=80 %)
    #    Primero intentamos la búsqueda actual, si buscar_faq ya hace algo útil.
    match = buscar_faq(mensaje)

    if not match:
        # Si buscar_faq no encontró nada exacto, usamos el match borroso
        match = encontrar_mejor_faq(mensaje, umbral=80)

    if match:
        return {
            "mensaje": match["respuesta"],
            "tipo": "faq",
            "keyword": match["keyword"]
        }

    # 2. Detectar intención de compra / suscripción
    if detectar_intencion_compra(mensaje):
        return {
            "mensaje": (
                "Para adquirir tu suscripción en QUIZORA, realiza el pago por Yape "
                "y luego llena el formulario con tus datos y el código de transacción."
            ),
            "tipo": "venta",
            "form_url": FORM_URL
        }

    # 3. Si no se encontró FAQ ni intención de compra, escalar a humano
    return {
        "mensaje": (
            "No encontré una respuesta automática para tu consulta. "
            "Te derivaré con un asesor del equipo de QUIZORA al WhatsApp 924582362."
        ),
        "tipo": "escalar"
    }
