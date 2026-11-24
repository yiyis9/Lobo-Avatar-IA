-- Añade instrucciones descriptivas para los gestos del avatar en ambos módulos.
-- Migración aditiva: conserva todas las preguntas, fichas y valores de animación actuales.
USE lobo_upvt_db;

ALTER TABLE preguntas_frecuentes
    ADD COLUMN accion_avatar VARCHAR(500) NOT NULL DEFAULT '';

ALTER TABLE informacion_institucional
    ADD COLUMN accion_avatar VARCHAR(500) NOT NULL DEFAULT '';
