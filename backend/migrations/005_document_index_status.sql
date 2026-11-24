-- Track asynchronous document enrichment without blocking uploads.
-- Existing records remain available and start as indexed.
ALTER TABLE documentos_institucionales
    ADD COLUMN estado_indice ENUM('pendiente', 'listo', 'error') NOT NULL DEFAULT 'listo';
