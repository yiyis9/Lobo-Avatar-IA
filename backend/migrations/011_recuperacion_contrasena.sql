-- Códigos de un solo uso para recuperar cuentas administrativas. Migración aditiva.
USE lobo_upvt_db;

CREATE TABLE IF NOT EXISTS codigos_recuperacion_contrasena (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    codigo_hash CHAR(64) NOT NULL,
    intentos INT NOT NULL DEFAULT 0,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expira_en TIMESTAMP NOT NULL,
    usado_en TIMESTAMP NULL,
    CONSTRAINT fk_recuperacion_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX ix_recuperacion_usuario_fecha (usuario_id, creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
