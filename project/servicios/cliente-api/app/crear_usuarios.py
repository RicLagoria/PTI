"""
Da de alta (o actualiza) las cuentas del equipo en la tabla `usuarios`.

Reutiliza auth.hashear_password así el hash queda garantizado compatible
con el que usa el login — no es una coincidencia de implementación, es el
mismo código.

Uso (con la base ya levantada):
    docker compose -f despliegue/compose.dev.yml run --rm cliente-api python crear_usuarios.py

Es seguro correrlo de nuevo: si el usuario ya existe, actualiza sus datos
(incluida la contraseña) en vez de duplicarlo.

Las contraseñas de acá son temporales para arrancar a usar el sistema, no
hay pantalla para cambiarlas todavía — avisarle a cada uno la suya por
afuera del repo (no van en el historial de git).
"""
import auth

# username = el de GitHub de cada uno, así el avatar sale solo (ver avatar_url).
EQUIPO = [
    {
        "username": "RicLagoria",
        "nombre_completo": "Ricardo Lagoria",
        "rol": "admin",
        "password": "Ricardo2026!",
    },
    {
        "username": "joririarte",
        "nombre_completo": "Jorge Iriarte",
        "rol": "colaborador",
        "password": "Jorge2026!",
    },
    {
        "username": "Obriguera",
        "nombre_completo": "Octavio Briguera",
        "rol": "colaborador",
        "password": "Octavio2026!",
    },
    {
        "username": "carlosjuare",
        "nombre_completo": "Carlos Juarez",
        "rol": "colaborador",
        "password": "Carlos2026!",
    },
    {
        "username": "santigodoy52",
        "nombre_completo": "Santiago Godoy",
        "rol": "colaborador",
        "password": "Santiago2026!",
    },
    {
        "username": "Leguerrero97",
        "nombre_completo": "Lautaro Guerrero",
        "rol": "colaborador",
        "password": "Lautaro2026!",
    },
]


def main():
    with auth._conexion() as con:
        for persona in EQUIPO:
            password_hash = auth.hashear_password(persona["password"])
            avatar_url = f"https://github.com/{persona['username']}.png"
            con.execute(
                """
                INSERT INTO usuarios (username, password_hash, nombre_completo, rol, avatar_url)
                VALUES (%(username)s, %(password_hash)s, %(nombre_completo)s, %(rol)s, %(avatar_url)s)
                ON CONFLICT (username) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    nombre_completo = EXCLUDED.nombre_completo,
                    rol = EXCLUDED.rol,
                    avatar_url = EXCLUDED.avatar_url
                """,
                {
                    "username": persona["username"],
                    "password_hash": password_hash,
                    "nombre_completo": persona["nombre_completo"],
                    "rol": persona["rol"],
                    "avatar_url": avatar_url,
                },
            )
            print(f"OK  {persona['username']:16s} ({persona['nombre_completo']}) -> contraseña: {persona['password']}")
        con.commit()
    print(f"\nListo, {len(EQUIPO)} cuentas creadas/actualizadas.")


if __name__ == "__main__":
    main()
