-- Apply once to an existing database. This migration only adds missing fields/tables.
USE lobo_upvt_db;

CREATE TABLE IF NOT EXISTS informacion_institucional (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clave VARCHAR(100) NOT NULL UNIQUE,
    titulo VARCHAR(180) NOT NULL,
    contenido TEXT NOT NULL,
    categoria VARCHAR(80) NOT NULL DEFAULT 'General',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_informacion_activa_categoria (activo, categoria)
) ENGINE=InnoDB;

DROP PROCEDURE IF EXISTS migrar_lobo_upvt_fastapi_001;
DELIMITER $$
CREATE PROCEDURE migrar_lobo_upvt_fastapi_001()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'usuarios' AND COLUMN_NAME = 'estado_solicitud'
    ) THEN
        ALTER TABLE usuarios ADD COLUMN estado_solicitud ENUM('pendiente', 'aprobada', 'rechazada') NOT NULL DEFAULT 'aprobada';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preguntas_frecuentes' AND COLUMN_NAME = 'animacion'
    ) THEN
        ALTER TABLE preguntas_frecuentes ADD COLUMN animacion VARCHAR(80) NOT NULL DEFAULT 'idle';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preguntas_frecuentes' AND COLUMN_NAME = 'emocion'
    ) THEN
        ALTER TABLE preguntas_frecuentes ADD COLUMN emocion VARCHAR(80) NOT NULL DEFAULT 'neutral';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'historial_consultas' AND COLUMN_NAME = 'pregunta_frecuente_id'
    ) THEN
        ALTER TABLE historial_consultas ADD COLUMN pregunta_frecuente_id INT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'usuarios' AND INDEX_NAME = 'ix_usuarios_estado_rol'
    ) THEN
        ALTER TABLE usuarios ADD INDEX ix_usuarios_estado_rol (estado_solicitud, rol);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preguntas_frecuentes' AND INDEX_NAME = 'ix_preguntas_frecuentes_pregunta'
    ) THEN
        ALTER TABLE preguntas_frecuentes ADD INDEX ix_preguntas_frecuentes_pregunta (pregunta);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preguntas_frecuentes' AND INDEX_NAME = 'ix_preguntas_activo_categoria'
    ) THEN
        ALTER TABLE preguntas_frecuentes ADD INDEX ix_preguntas_activo_categoria (activo, categoria);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'historial_consultas' AND INDEX_NAME = 'ix_historial_fecha'
    ) THEN
        ALTER TABLE historial_consultas ADD INDEX ix_historial_fecha (fecha_consulta);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.KEY_COLUMN_USAGE
        WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'historial_consultas'
          AND COLUMN_NAME = 'pregunta_frecuente_id' AND REFERENCED_TABLE_NAME = 'preguntas_frecuentes'
    ) THEN
        ALTER TABLE historial_consultas
            ADD CONSTRAINT fk_historial_pregunta_frecuente
            FOREIGN KEY (pregunta_frecuente_id) REFERENCES preguntas_frecuentes(id) ON DELETE SET NULL;
    END IF;
END$$
CALL migrar_lobo_upvt_fastapi_001()$$
DROP PROCEDURE migrar_lobo_upvt_fastapi_001$$
DELIMITER ;
