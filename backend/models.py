from datetime import datetime
import os
import hmac

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        Index("ix_usuarios_estado_rol", "estado_solicitud", "rol"),
        Index("ix_usuarios_papelera_en", "papelera_en"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    correo: Mapped[str] = mapped_column("email", String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(
        Enum("admin", "admin_contenido", "directivo", "profesor", "alumno", name="rol_usuario"),
        nullable=False,
        default="alumno",
    )
    matricula_empleado: Mapped[str | None] = mapped_column(String(20), unique=True)
    carrera: Mapped[str | None] = mapped_column(String(150))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    estado_solicitud: Mapped[str] = mapped_column(
        Enum("pendiente", "aprobada", "rechazada", name="estado_solicitud"),
        nullable=False,
        default="aprobada",
    )
    creado_en: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
    papelera_en: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)

    consultas: Mapped[list["HistorialConsulta"]] = relationship(back_populates="usuario")

    @property
    def es_admin_principal(self) -> bool:
        configured_email = os.getenv("PRINCIPAL_ADMIN_EMAIL", "").strip().casefold()
        return bool(
            configured_email
            and self.rol == "admin"
            and hmac.compare_digest(self.correo.casefold(), configured_email)
        )


class EstadoRelevoAdmin(Base):
    __tablename__ = "estado_relevo_admin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usada_en: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    usada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)


class CodigoRecuperacionContrasena(Base):
    __tablename__ = "codigos_recuperacion_contrasena"
    __table_args__ = (Index("ix_recuperacion_usuario_fecha", "usuario_id", "creado_en"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    codigo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    creado_en: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
    expira_en: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    usado_en: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)


class PreguntaFrecuente(Base):
    __tablename__ = "preguntas_frecuentes"
    __table_args__ = (
        Index("ix_preguntas_activo_categoria", "activo", "categoria"),
        Index("ft_preguntas_busqueda", "pregunta", "palabras_clave", mysql_prefix="FULLTEXT"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False, default="General")
    pregunta: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    respuesta: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    palabras_clave: Mapped[str | None] = mapped_column(String(255))
    accion_avatar: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    dirigido_a: Mapped[str] = mapped_column(
        Enum("todos", "alumnos", "profesores", "directivos", name="dirigido_a"),
        nullable=False,
        default="todos",
    )
    animacion: Mapped[str] = mapped_column(String(80), nullable=False, default="idle")
    emocion: Mapped[str] = mapped_column(String(80), nullable=False, default="neutral")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
    papelera_en: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)

    consultas: Mapped[list["HistorialConsulta"]] = relationship(back_populates="pregunta_frecuente")
    documentos: Mapped[list["DocumentoInstitucional"]] = relationship(back_populates="pregunta_frecuente")


class InformacionInstitucional(Base):
    __tablename__ = "informacion_institucional"
    __table_args__ = (
        Index("ix_informacion_activa_categoria", "activo", "categoria"),
        Index("ft_informacion_busqueda", "clave", "titulo", "contenido", "categoria", mysql_prefix="FULLTEXT"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clave: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    titulo: Mapped[str] = mapped_column(String(180), nullable=False)
    contenido: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    categoria: Mapped[str] = mapped_column(String(80), nullable=False, default="General")
    accion_avatar: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    animacion: Mapped[str] = mapped_column(String(80), nullable=False, default="Hablar", server_default="Hablar")
    emocion: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral", server_default="neutral")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
    papelera_en: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    documentos: Mapped[list["DocumentoInstitucional"]] = relationship(back_populates="informacion")


class DocumentoInstitucional(Base):
    __tablename__ = "documentos_institucionales"
    __table_args__ = (
        Index("ix_documentos_info_activo", "informacion_id", "activo"),
        Index("ft_documentos_busqueda", "nombre_archivo", "contenido_extraido", mysql_prefix="FULLTEXT"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informacion_id: Mapped[int | None] = mapped_column(
        ForeignKey("informacion_institucional.id", ondelete="RESTRICT"), nullable=True
    )
    pregunta_frecuente_id: Mapped[int | None] = mapped_column(
        ForeignKey("preguntas_frecuentes.id", ondelete="RESTRICT"), nullable=True
    )
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    archivo_key: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/pdf")
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    contenido_extraido: Mapped[str | None] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=True)
    estado_indice: Mapped[str] = mapped_column(
        Enum("pendiente", "listo", "error", name="estado_indice_documento"),
        nullable=False,
        default="listo",
        server_default="listo",
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
    papelera_en: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)

    informacion: Mapped[InformacionInstitucional | None] = relationship(back_populates="documentos")
    pregunta_frecuente: Mapped[PreguntaFrecuente | None] = relationship(back_populates="documentos")

    @property
    def url(self) -> str:
        return f"/api/v1/documentos/{self.id}/archivo"

    @property
    def texto_indexado(self) -> bool:
        return bool((self.contenido_extraido or "").strip())


class HistorialConsulta(Base):
    __tablename__ = "historial_consultas"
    __table_args__ = (
        Index("ix_historial_fecha", "fecha_consulta"),
        Index("uq_historial_clave_solicitud", "clave_solicitud", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    mensaje: Mapped[str] = mapped_column("pregunta_usuario", Text, nullable=False)
    respuesta: Mapped[str] = mapped_column("respuesta_bot", Text, nullable=False)
    origen: Mapped[str] = mapped_column(
        Enum("kiosko_kinect", "panel_web", name="origen_consulta"),
        nullable=False,
        default="kiosko_kinect",
    )
    pregunta_frecuente_id: Mapped[int | None] = mapped_column(
        ForeignKey("preguntas_frecuentes.id", ondelete="SET NULL")
    )
    categoria: Mapped[str] = mapped_column(String(80), nullable=False, default="Sin clasificar", server_default="Sin clasificar")
    modulo: Mapped[str] = mapped_column(String(40), nullable=False, default="consulta_general", server_default="consulta_general")
    clave_solicitud: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accion_avatar: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    animacion: Mapped[str] = mapped_column(String(80), nullable=False, default="idle", server_default="idle")
    emocion: Mapped[str] = mapped_column(String(80), nullable=False, default="neutral", server_default="neutral")
    fecha_consulta: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)

    usuario: Mapped[Usuario | None] = relationship(back_populates="consultas")
    pregunta_frecuente: Mapped[PreguntaFrecuente | None] = relationship(back_populates="consultas")


class MensajeContacto(Base):
    __tablename__ = "mensajes_contacto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    correo: Mapped[str] = mapped_column(String(254), nullable=False)
    asunto: Mapped[str] = mapped_column(String(160), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    leido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    contestado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    creado_en: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
    contestado_en: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
