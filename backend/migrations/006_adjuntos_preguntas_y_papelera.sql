-- Permite asociar documentos a información institucional o preguntas frecuentes.
-- Los registros y archivos ya existentes se conservan.
ALTER TABLE documentos_institucionales
    MODIFY COLUMN informacion_id INT NULL,
    ADD COLUMN pregunta_frecuente_id INT NULL AFTER informacion_id,
    ADD CONSTRAINT fk_documentos_pregunta_frecuente
        FOREIGN KEY (pregunta_frecuente_id) REFERENCES preguntas_frecuentes(id) ON DELETE RESTRICT,
    ADD INDEX ix_documentos_pregunta_activo (pregunta_frecuente_id, activo);

ALTER TABLE preguntas_frecuentes
    ADD COLUMN papelera_en TIMESTAMP NULL,
    ADD INDEX ix_preguntas_papelera_en (papelera_en);
