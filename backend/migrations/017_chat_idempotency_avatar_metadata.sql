-- Conserva la identidad de cada petición para evitar consultas duplicadas al reintentar.
USE lobo_upvt_db;

ALTER TABLE historial_consultas
    ADD COLUMN clave_solicitud VARCHAR(64) NULL,
    ADD COLUMN categoria VARCHAR(80) NOT NULL DEFAULT 'Sin clasificar',
    ADD COLUMN accion_avatar VARCHAR(500) NOT NULL DEFAULT '',
    ADD COLUMN animacion VARCHAR(80) NOT NULL DEFAULT 'idle',
    ADD COLUMN emocion VARCHAR(80) NOT NULL DEFAULT 'neutral',
    ADD UNIQUE INDEX uq_historial_clave_solicitud (clave_solicitud);

UPDATE historial_consultas AS h
JOIN preguntas_frecuentes AS p ON p.id = h.pregunta_frecuente_id
SET h.categoria = p.categoria
WHERE h.pregunta_frecuente_id IS NOT NULL;
