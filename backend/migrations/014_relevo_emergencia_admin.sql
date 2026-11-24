-- Estado persistente para que la clave de relevo del administrador principal
-- solo pueda canjearse una vez. No altera ni elimina cuentas existentes.
CREATE TABLE IF NOT EXISTS estado_relevo_admin (
    id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
    usada_en TIMESTAMP NULL DEFAULT NULL,
    usada_por_id INT NULL,
    CONSTRAINT fk_estado_relevo_admin_usuario
        FOREIGN KEY (usada_por_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB;

INSERT INTO estado_relevo_admin (id, usada_en, usada_por_id)
VALUES (1, NULL, NULL)
ON DUPLICATE KEY UPDATE id = VALUES(id);
