-- Roles con permisos reales (Entrega 5 de PDC).
--
-- Hasta acá la columna `rol` solo se mostraba en el front. Ahora cliente-api e
-- ia-entrenamiento la leen del JWT y restringen las acciones (auth.requiere_rol):
--   lector       ve dashboard, ortomosaicos, historial y exportaciones
--   colaborador  además sube ortomosaicos, corre análisis, sube aportes y entrena
--   admin        además borra aportes y activa modelos
--
-- La restricción evita que un rol mal escrito ("Admin", "lectora") quede en la
-- base y la API lo trate en silencio como el rol más bajo.
-- Idempotente: se puede aplicar de nuevo sobre una base que ya lo tiene.

ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_rol_valido;
ALTER TABLE usuarios ADD CONSTRAINT usuarios_rol_valido
    CHECK (rol IN ('lector', 'colaborador', 'admin'));

COMMENT ON COLUMN usuarios.rol IS 'lector | colaborador | admin. Restringe acciones en cliente-api e ia-entrenamiento (ver 06_roles.sql).';
