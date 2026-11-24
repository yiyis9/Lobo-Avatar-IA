-- Store extracted, public PDF text so kiosk questions can retrieve relevant passages.
ALTER TABLE documentos_institucionales
    ADD COLUMN contenido_extraido MEDIUMTEXT NULL;
