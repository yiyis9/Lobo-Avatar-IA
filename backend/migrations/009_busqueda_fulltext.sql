-- Índices de texto completo para acelerar la recuperación de fuentes del kiosko.
-- Amplía también el texto extraído de archivos; los datos actuales se conservan.
USE lobo_upvt_db;

ALTER TABLE preguntas_frecuentes
    ADD FULLTEXT INDEX ft_preguntas_busqueda (pregunta, palabras_clave);

ALTER TABLE informacion_institucional
    ADD FULLTEXT INDEX ft_informacion_busqueda (clave, titulo, contenido, categoria);

ALTER TABLE documentos_institucionales
    MODIFY COLUMN contenido_extraido MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
    ADD FULLTEXT INDEX ft_documentos_busqueda (nombre_archivo, contenido_extraido);
