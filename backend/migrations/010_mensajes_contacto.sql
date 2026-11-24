-- Buzón de contacto del kiosko. Migración aditiva: no modifica datos existentes.
USE lobo_upvt_db;

CREATE TABLE IF NOT EXISTS mensajes_contacto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(254) NOT NULL,
    asunto VARCHAR(160) NOT NULL,
    mensaje TEXT NOT NULL,
    leido BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_mensajes_contacto_fecha (creado_en),
    INDEX ix_mensajes_contacto_leido_fecha (leido, creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
