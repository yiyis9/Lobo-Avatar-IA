-- Clasifica cada interacción del kiosko para que el panel muestre consultas
-- provenientes de Preguntas y respuestas e Información institucional.
-- Migración aditiva: conserva todas las filas existentes.
ALTER TABLE historial_consultas
    ADD COLUMN modulo VARCHAR(40) NOT NULL DEFAULT 'consulta_anterior';

-- Las filas antiguas permiten identificar la FAQ solo cuando conservan su FK.
UPDATE historial_consultas
SET modulo = 'preguntas_respuestas'
WHERE pregunta_frecuente_id IS NOT NULL;
