# quizora_users.py
import random
import string
from datetime import datetime
from typing import Dict
import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
import os
import hashlib
import os
import base64

SCRYPT_N = 32768
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_SALT_LEN = 16
SCRYPT_KEY_LEN = 32  # tamaño del hash


def generar_password(dni: str) -> str:
    dni_str = str(dni).strip()
    letra_mayus = random.choice(string.ascii_uppercase)
    letra_minus = random.choice(string.ascii_lowercase)
    special = "*"
    return f"{dni_str}{letra_mayus}{letra_minus}{special}"

def get_neon_conn():
    return psycopg2.connect(
        dbname=os.getenv("NEON_DB_NAME"),
        user=os.getenv("NEON_DB_USER"),
        password=os.getenv("NEON_DB_PASSWORD"),
        host=os.getenv("NEON_DB_HOST"),
        port=int(os.getenv("NEON_DB_PORT", "5432")),
        cursor_factory=RealDictCursor
    )

def construir_username(primer_nombre_completo: str, primer_apellido: str, num_iniciales: int) -> str:
    iniciales = primer_nombre_completo[:num_iniciales].lower()
    apellido_lower = primer_apellido.lower()
    return f"{iniciales}{apellido_lower}"

def hashear_password(raw_password: str) -> str:
    # generar salt aleatorio
    salt = os.urandom(SCRYPT_SALT_LEN)

    # derivar clave con scrypt
    key = hashlib.scrypt(
        raw_password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=0,
        dklen=SCRYPT_KEY_LEN,
    )

    salt_b64 = base64.b64encode(salt).decode("utf-8")
    key_b64 = base64.b64encode(key).decode("utf-8")

    # construir string tipo scrypt:32768:8:1$<salt>$<hash>
    return f"scrypt:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}${salt_b64}${key_b64}"

def crear_usuario_quizora(row: Dict) -> Dict:
    primer_nombre_completo = str(row["nombres"]).split()[0].strip()
    primer_apellido = str(row["primer_apellido"]).strip()
    dni = str(row["dni"]).strip()
    specialty_code = row.get("especialidad")  # mapea a specialty_code de user [file:1]
    plan = "premium"  # o "basico", según lo que vendas en este flujo

    conn = get_neon_conn()
    cur = conn.cursor()

    raw_password = generar_password(dni)
    password_hash = hashear_password(raw_password)

    num_iniciales_usadas = 2
    username = construir_username(primer_nombre_completo, primer_apellido, num_iniciales_usadas)

    try:
        cur.execute(
            """
            INSERT INTO public.user (username, password_hash, role, specialty_code, session_token, plan)
            VALUES (%s, %s, %s, %s, NULL, %s)
            RETURNING id;
            """,
            (username, password_hash, "user", specialty_code, plan)
        )
        user_id = cur.fetchone()["id"]
        conn.commit()

    except errors.UniqueViolation:
        conn.rollback()
        num_iniciales_usadas = 3
        username = construir_username(primer_nombre_completo, primer_apellido, num_iniciales_usadas)

        cur.execute(
            """
            INSERT INTO public.user (username, password_hash, role, specialty_code, session_token, plan)
            VALUES (%s, %s, %s, %s, NULL, %s)
            RETURNING id;
            """,
            (username, password_hash, "user", specialty_code, plan)
        )
        user_id = cur.fetchone()["id"]
        conn.commit()

    finally:
        cur.close()
        conn.close()

    return {
        "user_id": user_id,
        "username": username,
        "raw_password": raw_password,
        "password_hash": password_hash,
        "num_iniciales_usadas": num_iniciales_usadas,
    }
    
    
def asignar_quices_iniciales(user_id: int, specialty_code: str):
    conn = get_neon_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id FROM quiz_file
        WHERE specialty_code = %s AND active = TRUE;
        """,
        (specialty_code,)
    )
    quiz_ids = [row["id"] for row in cur.fetchall()]

    for qid in quiz_ids:
        cur.execute(
            """
            INSERT INTO user_quiz (user_id, quizfile_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (user_id, qid)
        )

    conn.commit()
    cur.close()
    conn.close()
