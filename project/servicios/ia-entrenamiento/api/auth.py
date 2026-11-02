"""
Autenticación de la API de entrenamiento: solo verifica la firma del token.

Las cuentas son las mismas que las del sitio de análisis y viven en la tabla
`usuarios` de PostgreSQL, pero este servicio **no las conoce ni toca la base**.
Quien valida usuario y contraseña es `cliente-api` (ver su `auth.py`), que firma
un JWT con `JWT_SECRET`; acá solo se comprueba esa firma con el mismo secreto.
Es la misma regla que ya ordena el reparto con `ia-inferencia`: el plano de IA
hace su trabajo y no se mete con lo que es del plano Cliente.

Por eso el plano IA no necesita `psycopg` ni `bcrypt` ni `DATABASE_URL`: le
alcanza con `pyjwt` y con que las dos mitades compartan `JWT_SECRET`. Si no
coinciden, todo pedido responde 401 "Token inválido" aunque el login del
navegador haya salido bien, que es el síntoma a buscar primero cuando pasa eso.
"""

import os
from typing import Dict, Optional

import jwt
from fastapi import HTTPException, Request

# Mismo nombre y mismo valor por defecto que en cliente-api, así los dos planos
# se entienden en desarrollo sin configurar nada. En el servidor hay que
# definirla en los dos lados con el mismo valor.
JWT_SECRET = os.environ.get("JWT_SECRET", "agrovision-dev-secret-cambiar-en-produccion")
JWT_ALGORITMO = "HS256"


def _token_de(request: Request) -> Optional[str]:
    """
    El token viaja en el header Authorization para los pedidos normales, pero
    hay dos que no pueden mandar headers: el progreso del entrenamiento, que es
    un EventSource, y los gráficos de cada modelo, que son `<img src>`. Para
    esos se acepta el mismo token como query param (?token=...), igual que en
    cliente-api.
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
