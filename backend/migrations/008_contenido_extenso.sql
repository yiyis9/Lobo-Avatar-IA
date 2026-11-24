-- Amplía los campos de texto para contenidos institucionales y respuestas extensas.
-- Cambio compatible: MEDIUMTEXT conserva los datos existentes y aumenta la capacidad.
USE lobo_upvt_db;

ALTER TABLE preguntas_frecuentes
    MODIFY COLUMN respuesta MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL;

ALTER TABLE informacion_institucional
    MODIFY COLUMN contenido MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL;
