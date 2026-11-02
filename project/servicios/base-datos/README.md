# base-datos

PostgreSQL + PostGIS para todo el proyecto (no solo para el login). Cualquier
otro servicio que necesite guardar algo más que archivos en disco —
detecciones para el dashboard, registro de entrenamientos, lo que sea— usa
esta misma base, cada uno con sus propias tablas. `cliente-api` solo es dueño
de la tabla `usuarios`.

## Qué levanta

La imagen oficial `postgis/postgis` (Postgres + la extensión PostGIS ya
instalada, no hace falta Dockerfile propio). Los archivos de `init/` se corren
en orden, automáticamente, la primera vez que el contenedor arranca con el
volumen de datos vacío:

- `01_esquema.sql` — la extensión PostGIS y la tabla `usuarios`.
- `02_analisis.sql` — `ortomosaicos`, `analisis` y `detecciones`.
- `03_segmentacion.sql` — el contorno de cada detección: lo que aporta un modelo
  de segmentación por encima de uno de detección.
- `04_escala.sql` — a qué escala corrió cada análisis. Dos corridas del mismo
  ortomosaico con el mismo modelo pueden dar resultados muy distintos solo por
  esto, así que sin la columna no se sabría cuál fue cuál.
- `05_cascada.sql` — un análisis puede recorrer el campo varias veces, a
  escalas distintas, así que `analisis.escala` pasa a ser `analisis.escalas` y
  cada detección guarda de qué pasada salió. Reemplaza a la columna de 04, que
  este archivo migra y borra.

## Aplicar una migración a una base que ya existe

Postgres corre `init/` **una sola vez**, al crear el volumen: sobre una base que
ya tiene datos hay que aplicar los archivos nuevos a mano. Están escritos para
que repetirlo no haga nada (`IF NOT EXISTS` en todo):

```bash
docker compose -f despliegue/compose.dev.yml exec -T db psql -U agrovision -d agrovision < project/servicios/base-datos/init/03_segmentacion.sql
docker compose -f despliegue/compose.dev.yml exec -T db psql -U agrovision -d agrovision < project/servicios/base-datos/init/04_escala.sql
docker compose -f despliegue/compose.dev.yml exec -T db psql -U agrovision -d agrovision < project/servicios/base-datos/init/05_cascada.sql
```

Sin eso, `cliente-api` falla al guardar las detecciones de un análisis, porque
inserta en columnas que todavía no existen.

Ya está sumada a `despliegue/compose.dev.yml` y `despliegue/compose.cliente.yml`
como servicio `db`. No hace falta nada manual para levantarla, sale con el
resto: `docker compose -f despliegue/compose.dev.yml up --build`.

## Dar de alta a los usuarios del equipo

El esquema crea la tabla vacía. Para cargar las cuentas del equipo (con
contraseña ya hasheada), una vez que la base esté arriba:

```bash
docker compose -f despliegue/compose.dev.yml run --rm cliente-api python crear_usuarios.py
```

Ese script vive en `cliente-api/app/crear_usuarios.py` (no acá) porque
reutiliza el mismo hasheo de contraseñas que usa el login, así quedan
garantizadas compatibles. Es seguro correrlo de nuevo: si el usuario ya
existe, actualiza sus datos en vez de duplicarlo. Las contraseñas que carga
están en el propio script — avisale a cada uno la suya por afuera del repo.

## Si necesitás resetear la base en desarrollo

```bash
docker compose -f despliegue/compose.dev.yml down
rm -rf datos/db      # borra el volumen de datos, se vuelve a crear vacío
docker compose -f despliegue/compose.dev.yml up --build
```

## Conectarse a mano (debug)

En `compose.dev.yml` el puerto 5432 queda expuesto al host. Con `psql` o
cualquier cliente:

```bash
psql postgresql://agrovision:agrovision@localhost:5432/agrovision
```

En `compose.cliente.yml` (el de despliegue real) el puerto **no** se expone
afuera a propósito — solo los demás contenedores de la misma red le pueden
hablar a `db`.
