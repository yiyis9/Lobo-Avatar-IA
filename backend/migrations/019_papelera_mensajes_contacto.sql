-- Retención de mensajes de contacto enviados a la papelera (30 días).
-- Migración aditiva: conserva los mensajes existentes.
USE lobo_upvt_db;

ALTER TABLE mensajes_contacto
    ADD COLUMN papelera_en TIMESTAMP NULL,
    ADD INDEX ix_mensajes_contacto_papelera_en (papelera_en);
