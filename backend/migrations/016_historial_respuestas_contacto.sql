-- Registra si cada mensaje de contacto ya recibió respuesta por correo.
-- Los mensajes existentes se conservan; inicialmente quedan como no respondidos.
USE lobo_upvt_db;

ALTER TABLE mensajes_contacto
    ADD COLUMN contestado BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN contestado_en TIMESTAMP NULL DEFAULT NULL,
    ADD INDEX ix_mensajes_contacto_contestado_fecha (contestado, contestado_en);
