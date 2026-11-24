-- Trash retention for institutional information and its attached documents.
-- Additive only: existing rows remain available and start outside the trash.
ALTER TABLE informacion_institucional
    ADD COLUMN papelera_en TIMESTAMP NULL,
    ADD INDEX ix_informacion_papelera_en (papelera_en);

ALTER TABLE documentos_institucionales
    ADD COLUMN papelera_en TIMESTAMP NULL,
    ADD INDEX ix_documentos_papelera_en (papelera_en);
