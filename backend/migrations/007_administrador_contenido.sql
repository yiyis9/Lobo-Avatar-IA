-- Migration 007: adds a separate content-administrator account role.
-- Existing roles and records are retained; no rows are deleted or rewritten.
USE lobo_upvt_db;

ALTER TABLE usuarios
    MODIFY COLUMN rol ENUM(
        'admin',
        'admin_contenido',
        'directivo',
        'profesor',
        'alumno'
    ) NOT NULL DEFAULT 'alumno';
