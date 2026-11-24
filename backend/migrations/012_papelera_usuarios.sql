-- Papelera reversible para usuarios, con purga automática a los 30 días.
-- Migración aditiva: las cuentas existentes permanecen fuera de la papelera.
USE lobo_upvt_db;

ALTER TABLE usuarios
    ADD COLUMN papelera_en TIMESTAMP NULL,
    ADD INDEX ix_usuarios_papelera_en (papelera_en);
