# Informe de amenazas — AgroVision

**Qué protegemos:**
- Los ortomosaicos de los campos, que son datos del productor.
- Los análisis y las detecciones.
- Las cuentas del equipo.
- Los modelos de IA en uso. Activar un modelo malo cambia los resultados de todos.

**De quién:**
- Alguien de afuera que llega por la red.
- Un usuario válido que intenta hacer más de lo que su rol le permite.
- Fallas propias: un disco que se rompe, un contenedor que se cae o un borrado por error.

Usamos **STRIDE**: un repaso de seis tipos de amenaza, uno por letra.

| Amenaza (STRIDE) | Ejemplo en AgroVision | Mitigación | Estado |
|---|---|---|---|
| **S**uplantación | Alguien entra con la cuenta de otro, o adivina la contraseña | Contraseñas con bcrypt; JWT firmado que vence a las 12 h; límite de 5 logins por minuto por IP (`429`) | Mitigado |
| **T**ampering, manipulación | Alguien modifica un pedido o una respuesta en el camino | TLS en el gateway; el JWT firmado no se puede editar sin el secreto | Mitigado |
| **R**epudio | Alguien niega haber subido una imagen o corrido un análisis | Cada ortomosaico y análisis guarda qué usuario lo hizo; el gateway registra cada pedido | Parcial (no hay log de auditoría aparte) |
| **I**nformation disclosure, fuga | Se lee el tráfico o se accede directo a la base | HTTPS; la base, la API y la IA no publican puertos; un lector recibe `403` antes de saber si una imagen existe | Mitigado |
| **D**enegación de servicio | Se satura la API con pedidos o el disco con subidas | Réplicas de `cliente-api` detrás del gateway; límite en el login; tope de subida (`MAX_UPLOAD_MB`) | Parcial (no hay cuota por usuario) |
| **E**levación de privilegios | Un lector sube imágenes, o un colaborador activa un modelo | Roles verificados en el backend de las dos APIs, no solo escondidos en el front | Mitigado |

## Fallas, no ataques

| Falla | Mitigación | Probado |
|---|---|---|
| Se pierde la base | `backup.sh` y `restaurar.sh` | Sí: [`evidencias/recuperacion.txt`](evidencias/recuperacion.txt) |
| Se cae un contenedor | `healthcheck` y `restart: unless-stopped` | Sí: se ve en `docker compose ps` |
| Se cae una réplica de la API | El gateway reintenta en otra réplica | Sí: Entrega 6, prueba de failover |

## Riesgos que quedan (aceptados para este alcance)

| Riesgo | Por qué se acepta | Qué haría falta |
|---|---|---|
| `JWT_SECRET` y la contraseña de la base tienen valores de desarrollo por defecto | Es el entorno de demo | Pasarlos por `.env` o un gestor de secretos, y que el servicio no arranque sin ellos |
| Dentro de la red de Docker el tráfico va en HTTP | Esa red no es accesible desde afuera | mTLS o `sslmode=require` hacia Postgres, si los servicios van a máquinas distintas |
| El token viaja como `?token=` en teselas y SSE (el navegador no deja poner cabeceras ahí) | Ahora viaja dentro del HTTPS | Cookie `HttpOnly` o un token corto solo para teselas |
| Certificado autofirmado | Es la demo local | Let's Encrypt con un dominio real |
