-- 1. Creación de la base de datos
CREATE DATABASE IF NOT EXISTS lobo_upvt_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lobo_upvt_db;

-- 2. Tabla de Usuarios del Sistema (Admin, Directivos, Profesores, Alumnos)
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol ENUM('admin', 'admin_contenido', 'directivo', 'profesor', 'alumno') NOT NULL DEFAULT 'alumno',
    matricula_empleado VARCHAR(20) UNIQUE,
    carrera VARCHAR(150), -- Permite guardar carreras completas como 'Ingeniería en Tecnologías de la Información e Innovación Digital'
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    estado_solicitud ENUM('pendiente', 'aprobada', 'rechazada') NOT NULL DEFAULT 'aprobada',
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_usuarios_estado_rol (estado_solicitud, rol)
) ENGINE=InnoDB;

-- 3. Tabla de Base de Conocimientos / Preguntas Frecuentes (FAQ UPVT)
CREATE TABLE IF NOT EXISTS preguntas_frecuentes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    categoria VARCHAR(50) NOT NULL,
    pregunta VARCHAR(255) NOT NULL,
    respuesta MEDIUMTEXT NOT NULL,
    palabras_clave VARCHAR(255),
    dirigido_a ENUM('todos', 'alumnos', 'profesores', 'directivos') NOT NULL DEFAULT 'todos',
    animacion VARCHAR(80) NOT NULL DEFAULT 'idle',
    emocion VARCHAR(80) NOT NULL DEFAULT 'neutral',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_preguntas_frecuentes_pregunta (pregunta),
    INDEX ix_preguntas_activo_categoria (activo, categoria),
    FULLTEXT INDEX ft_preguntas_busqueda (pregunta, palabras_clave)
) ENGINE=InnoDB;

-- 4. Tabla de Logs / Historial de Conversaciones del Kiosko
CREATE TABLE IF NOT EXISTS historial_consultas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NULL,
    pregunta_usuario TEXT NOT NULL,
    respuesta_bot TEXT NOT NULL,
    origen ENUM('kiosko_kinect', 'panel_web') NOT NULL DEFAULT 'kiosko_kinect',
    pregunta_frecuente_id INT NULL,
    fecha_consulta TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    CONSTRAINT fk_historial_pregunta_frecuente FOREIGN KEY (pregunta_frecuente_id) REFERENCES preguntas_frecuentes(id) ON DELETE SET NULL,
    INDEX ix_historial_fecha (fecha_consulta)
) ENGINE=InnoDB;

-- 4. Información institucional administrable e independiente de las preguntas frecuentes
CREATE TABLE IF NOT EXISTS informacion_institucional (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clave VARCHAR(100) NOT NULL UNIQUE,
    titulo VARCHAR(180) NOT NULL,
    contenido MEDIUMTEXT NOT NULL,
    categoria VARCHAR(80) NOT NULL DEFAULT 'General',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_informacion_activa_categoria (activo, categoria),
    FULLTEXT INDEX ft_informacion_busqueda (clave, titulo, contenido, categoria)
) ENGINE=InnoDB;

-- 5. Datos iniciales de prueba (Semilla)
INSERT INTO preguntas_frecuentes (categoria, pregunta, respuesta, palabras_clave, dirigido_a) 
VALUES 
('General', '¿Qué carreras ofrece la UPVT?', 'La UPVT ofrece carreras como Ingeniería en Tecnologías de la Información e Innovación Digital, Ingeniería Mecatrónica, Ingeniería Industrial, Ingeniería en Biotecnología, Ingeniería Mecánica Automotriz, Licenciatura en Comercio Internacional y Aduanas, Ingeniería en Energía y Desarrollo Sostenible', 'carreras, oferta educativa, ingenierias', 'todos'),
('Ubicación', '¿Dónde se ubica la universidad?', 'La UPVT se encuentra en la Carretera Toluca-Almoloya de Juárez Km 5.6, Santiaguito Tlalcilalcalli.', 'ubicacion, direccion, donde esta', 'todos');

-- 6. Usuarios iniciales de prueba según los roles
INSERT IGNORE INTO usuarios (nombre, email, password_hash, rol, matricula_empleado, carrera) 
VALUES 
('Administrador General', 'admin@upvt.edu.mx', 'hash_secret_admin', 'admin', 'EMP-001', 'Ingeniería en Tecnologías de la Información e Innovación Digital'),
('Director de Carrera', 'directivo@upvt.edu.mx', 'hash_secret_dir', 'directivo', 'EMP-010', 'Ingeniería en Tecnologías de la Información e Innovación Digital'),
('Profesor Mtra. Ariana', 'ariana@upvt.edu.mx', 'hash_secret_prof', 'profesor', 'EMP-050', 'Ingeniería en Tecnologías de la Información e Innovación Digital'),
('Alumno Ejemplo', 'alumno@upvt.edu.mx', 'hash_secret_alum', 'alumno', '1324473065', 'Ingeniería en Tecnologías de la Información e Innovación Digital');
