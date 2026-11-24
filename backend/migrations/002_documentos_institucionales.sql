-- Add public PDF attachments to institutional information without changing existing rows.
CREATE TABLE IF NOT EXISTS documentos_institucionales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    informacion_id INT NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    archivo_key CHAR(36) NOT NULL UNIQUE,
    mime_type VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    tamano_bytes INT UNSIGNED NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_documentos_informacion
        FOREIGN KEY (informacion_id) REFERENCES informacion_institucional(id) ON DELETE RESTRICT,
    INDEX ix_documentos_info_activo (informacion_id, activo)
) ENGINE=InnoDB;
