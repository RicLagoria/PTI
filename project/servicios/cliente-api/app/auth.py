import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import bcrypt
import jwt
import psycopg
from fastapi import HTTPException, Request
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://agrovision:agrovision@db:5432/agrovision")
JWT_SECRET = os.environ.get("JWT_SECRET", "agrovision-dev-secret-cambiar-en-produccion")
JWT_ALGORITMO = "HS256"
JWT_HORAS_VALIDEZ = int(os.environ.get("JWT_HORAS_VALIDEZ", "12"))


def _conexion():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


# Alias público: datos.py lo usa para hablarle a las mismas tablas sin
# duplicar DATABASE_URL en otro lado.
conexion = _conexion


def hashear_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def obtener_usuario_por_username(username: str) -> Optional[Dict]:
    with _conexion() as con:
        fila = con.execute(
            "SELECT id, username, password_hash, nombre_completo, rol, avatar_url, fecha_alta, ultimo_acceso "
            "FROM usuarios WHERE username = %s",
            (username,),
        ).fetchone()
        return dict(fila) if fila else None


def registrar_acceso(username: str) -> None:
    with _conexion() as con:
        con.execute(
            "UPDATE usuarios SET ultimo_acceso = now() WHERE username = %s",
            (username,),
        )
        con.commit()


def _perfil_publico(usuario: Dict) -> Dict:
    """Lo que viaja al front: todo menos el hash de la contraseña."""
    return {
        "id": usuario["id"],
        "username": usuario["username"],
        "nombre_completo": usuario["nombre_completo"],
        "rol": usuario["rol"],
        "avatar_url": usuario["avatar_url"],
        "fecha_alta": usuario["fecha_alta"].isoformat() if usuario["fecha_alta"] else None,
        "ultimo_acceso": usuario["ultimo_acceso"].isoformat() if usuario["ultimo_acceso"] else None,
    }


def autenticar(username: str, password: str) -> Dict:
    """Valida credenciales contra la base. Lanza HTTPException(401) si no coinciden."""
    usuario = obtener_usuario_por_username(username)
    if usuario is None or not verificar_password(password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    registrar_acceso(username)
    return _perfil_publico(usuario)


def crear_token(perfil: Dict) -> str:
    """
    El perfil completo va adentro del JWT (no solo el username): así el
    front puede mostrar nombre/rol/avatar sin pegarle a la API de nuevo en
    cada pantalla, y las rutas protegidas no necesitan tocar la base en
    cada pedido.
    """
    payload = {
        **perfil,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_HORAS_VALIDEZ),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITMO)


def _token_de(request: Request) -> Optional[str]:
    """
    El token viaja en el header Authorization para los pedidos normales,
    pero Leaflet (teselas) y EventSource (el streaming de análisis) no
    pueden mandar headers custom: para esos dos casos se acepta el mismo
    token como query param (?token=...).
    """
    encabezado = request.headers.get("authorization")
    if encabezado and encabezado.lower().startswith("bearer "):
        return encabezado[7:]
    return request.query_params.get("token")


def usuario_actual(request: Request) -> Dict:
    """Dependency de FastAPI: exige un JWT válido y devuelve el perfil que contiene."""
    token = _token_de(request)
    if not token:
        raise HTTPException(status_code=401, detail="Falta autenticación.")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITMO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="La sesión expiró, iniciá sesión de nuevo.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")
    payload.pop("exp", None)
    return payload
