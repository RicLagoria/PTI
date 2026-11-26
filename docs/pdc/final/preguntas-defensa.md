# Preguntas probables de la defensa

Respuestas cortas, para que **cualquiera** de los tres pueda contestar cualquier módulo.

## Arquitectura e infraestructura

**¿Por qué dos planos?**
Entrenar necesita GPU y horas de cómputo; analizar, no. Separados, cada uno va en la máquina que le conviene y se despliega por su cuenta.

**¿Qué es un contenedor y por qué Docker Compose?**
Un contenedor es la app empaquetada con todo lo que necesita: corre igual en cualquier máquina. Compose describe varios contenedores y cómo se conectan, y los levanta con un comando.

**¿Qué vista del 4+1 muestra el diagrama de la diapositiva?**
La física: qué corre dónde y cómo se conectan los nodos.

## Comunicación y middleware

**¿Por qué el análisis es síncrono y el entrenamiento asíncrono?**
El análisis necesita las detecciones para seguir y dura segundos. El entrenamiento dura horas, así que se encola y responde `202` al instante.

**¿Qué caso de concurrencia resolvieron?**
Dos workers tomaban el mismo entrenamiento, porque leer y marcar eran dos pasos. Se resolvió con un lock atómico (`O_EXCL`): antes había 17 repetidos y después 0.

**¿Qué es un contrato y cómo saben que se cumple?**
Un OpenAPI por servicio. `verificar_contratos.py` compara la API real con el contrato y falla si difieren.

**¿Cómo funciona el descubrimiento?**
Cada `ia-inferencia` se anuncia en `registro-servicios` y late cada 5 s. Si deja de latir, vence. `cliente-api` le pide al registro las instancias vivas.

## Seguridad

**¿Dónde se controla el rol, en el front o en el back?**
En el back, en las dos APIs, con `requiere_rol()`. El front solo esconde botones. Si alguien llama a la API a mano, igual recibe `403`.

**¿Por qué el rol va dentro del JWT y no se consulta en la base?**
El token está firmado, así que nadie puede cambiarle el rol sin el secreto. Además, verificarlo no le pega a la base en cada pedido.

**¿Qué pasa si roban un token?**
Vence a las 12 h y viaja solo por HTTPS. Queda como riesgo aceptado: no hay revocación antes de que venza.

**¿Por qué un certificado autofirmado?**
Es la demo local. En producción iría Let's Encrypt con un dominio real.

**¿Qué es STRIDE?**
Seis tipos de amenaza:
- **S**uplantación;
- **T**ampering, o manipulación;
- **R**epudio;
- **I**nformation disclosure, o fuga de información;
- **D**enegación de servicio;
- **E**levación de privilegios.

En el informe hay, para cada una, qué la frena.

**¿Probaron el backup?**
Sí. Se restaura en una base aparte y se comparan las filas tabla por tabla: coinciden las 4.

## Patrones y escalabilidad

**El gateway, ¿es proxy o fachada?**
Las dos cosas:
- **Proxy:** en `/api` reenvía el pedido tal cual y agrega TLS, límites y balanceo.
- **Fachada:** para el usuario es una sola puerta que esconde ocho servicios.

**¿Por qué se puede escalar `cliente-api` y no la base?**
La API no guarda estado propio: la sesión está en el JWT, los datos en PostGIS y los archivos en un volumen compartido. La base sí tiene estado; escalarla pediría réplicas o particionamiento.

**¿Qué algoritmo de balanceo usan?**
Round-robin, el que nginx trae por defecto. Se ve en el reparto parejo entre las 3 réplicas.

**¿Por qué no mejora 3 veces con 3 réplicas?**
Las tres comparten la misma máquina (los mismos núcleos), la base y el disco. Escalar solo rinde cuando la capa que escalás es el cuello de botella.

**¿Por qué miden p95 y no el promedio?**
El promedio esconde a los usuarios con peor suerte. El p95 dice cuánto espera el 95 % de los pedidos.

**¿Qué pasa si se cae una réplica?**
El gateway reintenta en otra (`proxy_next_upstream`), así que el usuario no ve el error. Docker la vuelve a levantar.
