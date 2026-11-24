USE lobo_upvt_db;

ALTER TABLE informacion_institucional
    ADD COLUMN animacion VARCHAR(80) NOT NULL DEFAULT 'Hablar',
    ADD COLUMN emocion VARCHAR(20) NOT NULL DEFAULT 'neutral';
