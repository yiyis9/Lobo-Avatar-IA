from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


def validar_nombre_persona(value: str) -> str:
    value = " ".join(value.split())
    if len(value) < 2 or not any(char.isalpha() for char in value):
        raise ValueError("Escribe un nombre válido usando letras.")
    if any(not (char.isalpha() or char in " -'’") for char in value):
        raise ValueError("El nombre solo puede contener letras, espacios, guiones o apóstrofos.")
    return value


def validar_contrasena_segura(value: str) -> str:
    if any(char.isspace() for char in value):
        raise ValueError("La contraseña no puede contener espacios.")
    if not any(char.islower() for char in value):
        raise ValueError("La contraseña debe incluir una letra minúscula.")
    if not any(char.isupper() for char in value):
        raise ValueError("La contraseña debe incluir una letra mayúscula.")
    if not any(char.isdigit() for char in value):
        raise ValueError("La contraseña debe incluir un número.")
    if not any(not char.isalnum() for char in value):
        raise ValueError("La contraseña debe incluir un símbolo.")
    return value


class ChatTurn(APIModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200)


class ChatRequest(APIModel):
    mensaje: str = Field(min_length=2, max_length=1000)
    contexto: list[ChatTurn] = Field(default_factory=list, max_length=6)
    request_id: str | None = Field(default=None, min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class ContactoCreate(APIModel):
    nombre: str = Field(min_length=2, max_length=100)
    correo: str = Field(min_length=5, max_length=254)
    asunto: str = Field(min_length=2, max_length=160)
    mensaje: str = Field(min_length=5, max_length=5000)
    website: str | None = Field(default=None, max_length=200)

    @field_validator("correo")
    @classmethod
    def validar_correo_contacto(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1] or any(char.isspace() for char in value):
            raise ValueError("Ingresa un correo electrónico válido.")
        return value


class ContactoResponse(APIModel):
    id: int
    nombre: str
    correo: str
    asunto: str
    mensaje: str
    leido: bool
    contestado: bool = False
    creado_en: datetime
    contestado_en: datetime | None = None


class ContactoLeidoRequest(APIModel):
    leido: bool


class ContactoRespuestaRequest(APIModel):
    mensaje: str = Field(min_length=1, max_length=20000)
    adjuntos: list["ContactoAdjuntoRequest"] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validar_tamano_adjuntos(self) -> "ContactoRespuestaRequest":
        if sum(len(item.contenido_base64) for item in self.adjuntos) > 24_000_000:
            raise ValueError("Los archivos superan el tamaño permitido para un correo.")
        return self


class ContactoAdjuntoRequest(APIModel):
    nombre: str = Field(min_length=1, max_length=255)
    contenido_base64: str = Field(min_length=4, max_length=24_000_000)

    @field_validator("nombre")
    @classmethod
    def validar_nombre_adjunto(cls, value: str) -> str:
        value = value.strip()
        if any(char in value for char in "\r\n"):
            raise ValueError("El nombre del archivo no es válido.")
        extension = value.rsplit(".", 1)[-1].lower() if "." in value else ""
        if extension not in {"pdf", "png", "jpg", "jpeg", "gif", "webp", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"}:
            raise ValueError("Ese tipo de archivo no está permitido para adjuntar.")
        return value


ContactoRespuestaRequest.model_rebuild()


class PreguntaAdjuntoResponse(APIModel):
    id: int
    nombre_archivo: str
    mime_type: str
    tamano_bytes: int
    activo: bool = True
    creado_en: datetime
    papelera_en: datetime | None = None
    estado_indice: Literal["pendiente", "listo", "error"] = "listo"
    url: str
    texto_indexado: bool = False


class ChatResponse(APIModel):
    respuesta: str
    accion_avatar: str = ""
    animacion: str = "idle"
    emocion: str = "neutral"
    consulta_id: int | None = Field(default=None, serialization_alias="consultaId")
    fuente_documental: str | None = Field(default=None, serialization_alias="fuenteDocumental")
    url_documento: str | None = Field(default=None, serialization_alias="urlDocumento")
    mapa_url: str | None = Field(default=None, serialization_alias="mapaUrl")
    video_url: str | None = Field(default=None, serialization_alias="videoUrl")
    documentos: list[PreguntaAdjuntoResponse] = Field(default_factory=list)


class VoiceTranscriptionResponse(APIModel):
    transcripcion: str = Field(min_length=1, max_length=1000)


class VoiceSynthesisRequest(APIModel):
    texto: str = Field(min_length=1, max_length=2000)


class GenerarAccionAvatarRequest(APIModel):
    tipo: Literal["pregunta", "informacion"]
    titulo: str = Field(min_length=2, max_length=255)
    categoria: str = Field(default="General", max_length=80)
    contenido: str = Field(min_length=1, max_length=20000)
    palabras_clave: str = Field(default="", max_length=255)
    archivos: list[str] = Field(default_factory=list, max_length=20)


class GenerarAccionAvatarResponse(APIModel):
    accion_avatar: str = Field(min_length=1, max_length=500)
    animacion: Literal["idle", "Hablar", "Explicar", "Saludo", "Pensar", "Celebrar"] = "Hablar"
    emocion: Literal["neutral", "happy"] = "neutral"
    metodo: Literal["gemini", "local"] = "gemini"


class PreguntaCreate(APIModel):
    categoria: str = Field(min_length=1, max_length=50)
    pregunta: str = Field(min_length=3, max_length=255)
    respuesta: str = Field(min_length=1, max_length=1_000_000)
    palabras_clave: str | None = Field(default=None, max_length=255)
    accion_avatar: str = Field(default="", max_length=500)
    dirigido_a: Literal["todos", "alumnos", "profesores", "directivos"] = "todos"
    animacion: Literal["idle", "Hablar", "Explicar", "Saludo", "Pensar", "Celebrar"] = "Hablar"
    emocion: str = Field(default="neutral", max_length=80)
    activo: bool = True


class PreguntaUpdate(PreguntaCreate):
    pass


class PreguntaConDocumentoRequest(PreguntaUpdate):
    archivo_nombre: str | None = Field(default=None, max_length=255)
    archivo_base64: str | None = Field(default=None, max_length=14_000_000)
    archivos_nombres: list[str] = Field(default_factory=list, max_length=20)
    archivos_base64: list[str] = Field(default_factory=list, max_length=20)
    contenido_publico_confirmado: bool = False

    @model_validator(mode="after")
    def validar_adjuntos(self) -> "PreguntaConDocumentoRequest":
        if self.archivos_nombres or self.archivos_base64:
            if self.archivo_nombre or self.archivo_base64:
                raise ValueError("Envía los archivos en un solo formato.")
            if len(self.archivos_nombres) != len(self.archivos_base64):
                raise ValueError("Cada archivo debe tener un nombre y contenido completos.")
            if any(len(encoded) > 14_000_000 for encoded in self.archivos_base64):
                raise ValueError("Cada archivo adjunto debe pesar como máximo 10 MB.")
            if sum(map(len, self.archivos_base64)) > 28_000_000:
                raise ValueError("El tamaño conjunto de los archivos supera el límite permitido.")
        elif bool(self.archivo_nombre) != bool(self.archivo_base64):
            raise ValueError("Selecciona archivos completos o deja los adjuntos vacíos.")
        return self


class PreguntaResponse(APIModel):
    id: int
    categoria: str
    pregunta: str
    respuesta: str
    palabras_clave: str | None
    accion_avatar: str = ""
    dirigido_a: str
    animacion: str
    emocion: str
    activo: bool
    creado_en: datetime
    documentos: list[PreguntaAdjuntoResponse] = Field(default_factory=list)


class PreguntasPaginadasResponse(APIModel):
    items: list[PreguntaResponse]
    total: int
    pagina: int
    por_pagina: int
    paginas: int
    categorias: list[str]


class RegistroRequest(APIModel):
    nombre: str = Field(min_length=2, max_length=100)
    correo: str = Field(min_length=5, max_length=100)
    contrasena: str = Field(min_length=12, max_length=256)
    clave_autorizacion: str | None = Field(default=None, max_length=256)
    clave_relevo: str | None = Field(default=None, max_length=256)
    rol: Literal["admin", "admin_contenido"] = "admin_contenido"
    carrera: str | None = Field(default=None, max_length=150)

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        value = value.lower()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Ingresa un correo válido.")
        return value

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, value: str) -> str:
        return validar_nombre_persona(value)

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena_segura(cls, value: str) -> str:
        return validar_contrasena_segura(value)


def validar_correo_cuenta(value: str) -> str:
    value = value.strip().lower()
    if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1] or any(char.isspace() for char in value):
        raise ValueError("Ingresa un correo válido.")
    return value


class RecuperarContrasenaRequest(APIModel):
    correo: str = Field(min_length=5, max_length=100)

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return validar_correo_cuenta(value)


class RestablecerContrasenaRequest(RecuperarContrasenaRequest):
    codigo: str = Field(pattern=r"^\d{6}$")
    contrasena_nueva: str = Field(min_length=12, max_length=256)

    @field_validator("contrasena_nueva")
    @classmethod
    def validar_contrasena_segura(cls, value: str) -> str:
        return validar_contrasena_segura(value)


class LoginRequest(APIModel):
    correo: str = Field(min_length=5, max_length=100)
    contrasena: str = Field(min_length=1, max_length=256)

    @field_validator("correo")
    @classmethod
    def normalizar_correo(cls, value: str) -> str:
        return value.lower()


class PerfilUpdate(APIModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    contrasena_actual: str | None = Field(default=None, min_length=1, max_length=256)
    contrasena_nueva: str | None = Field(default=None, min_length=12, max_length=256)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validar_nombre_persona(value)

    @field_validator("contrasena_nueva")
    @classmethod
    def validar_contrasena_segura(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validar_contrasena_segura(value)

    @model_validator(mode="after")
    def validar_cambio(self) -> "PerfilUpdate":
        if self.nombre is None and self.contrasena_nueva is None:
            raise ValueError("Indica un nombre nuevo o una contraseña nueva.")
        if bool(self.contrasena_actual) != bool(self.contrasena_nueva):
            raise ValueError("Para cambiar la contraseña indica la contraseña actual y la nueva.")
        return self


class UsuarioResponse(APIModel):
    id: int
    nombre: str
    correo: str
    rol: str
    matricula_empleado: str | None
    carrera: str | None
    activo: bool
    estado_solicitud: str
    creado_en: datetime
    es_admin_principal: bool = False


class DecisionSolicitud(APIModel):
    decision: Literal["aprobar", "rechazar"]


class EstadoUsuario(APIModel):
    activo: bool


class RolUsuarioUpdate(APIModel):
    rol: Literal["admin", "admin_contenido", "directivo", "profesor", "alumno"]


class InformacionCreate(APIModel):
    clave: str = Field(min_length=2, max_length=100)
    titulo: str = Field(min_length=2, max_length=180)
    contenido: str = Field(min_length=1, max_length=1_000_000)
    categoria: str = Field(default="General", min_length=1, max_length=80)
    accion_avatar: str = Field(default="", max_length=500)
    animacion: Literal["idle", "Hablar", "Explicar", "Saludo", "Pensar", "Celebrar"] = "Hablar"
    emocion: Literal["neutral", "happy"] = "neutral"
    activo: bool = True


class InformacionConDocumentoRequest(InformacionCreate):
    archivo_nombre: str | None = Field(default=None, max_length=255)
    archivo_base64: str | None = Field(default=None, max_length=14_000_000)
    archivos_nombres: list[str] = Field(default_factory=list, max_length=20)
    archivos_base64: list[str] = Field(default_factory=list, max_length=20)
    contenido_publico_confirmado: bool = False

    @model_validator(mode="after")
    def validar_adjuntos(self) -> "InformacionConDocumentoRequest":
        if self.archivos_nombres or self.archivos_base64:
            if self.archivo_nombre or self.archivo_base64:
                raise ValueError("Envía los archivos en un solo formato.")
            if len(self.archivos_nombres) != len(self.archivos_base64):
                raise ValueError("Cada archivo debe tener un nombre y contenido completos.")
            if any(len(encoded) > 14_000_000 for encoded in self.archivos_base64):
                raise ValueError("Cada archivo adjunto debe pesar como máximo 10 MB.")
            if sum(map(len, self.archivos_base64)) > 28_000_000:
                raise ValueError("El tamaño conjunto de los archivos supera el límite permitido.")
        elif bool(self.archivo_nombre) != bool(self.archivo_base64):
            raise ValueError("Selecciona archivos completos o deja los adjuntos vacíos.")
        return self


class DocumentoInstitucionalResponse(APIModel):
    id: int
    nombre_archivo: str
    mime_type: str
    tamano_bytes: int
    activo: bool
    creado_en: datetime
    papelera_en: datetime | None = None
    estado_indice: Literal["pendiente", "listo", "error"] = "listo"
    url: str
    texto_indexado: bool


class InformacionResponse(InformacionCreate):
    id: int
    creado_en: datetime
    actualizado_en: datetime
    papelera_en: datetime | None = None
    documentos: list[DocumentoInstitucionalResponse] = Field(default_factory=list)
    analisis_gemini: bool = False


class InformacionPublicaResponse(APIModel):
    id: int
    clave: str
    titulo: str
    contenido: str
    categoria: str
    accion_avatar: str = ""
    animacion: str = "Hablar"
    emocion: str = "neutral"
    activo: bool
    creado_en: datetime
    actualizado_en: datetime


class DocumentoPublicoResponse(APIModel):
    id: int
    nombre_archivo: str
    mime_type: str
    tamano_bytes: int
    titulo_informacion: str
    categoria: str
    url: str


class ImportarInformacionRequest(APIModel):
    nombre_archivo: str = Field(min_length=1, max_length=200)
    texto: str | None = Field(default=None, max_length=50000)
    archivo_base64: str | None = Field(default=None, max_length=14000000)
    contenido_publico_confirmado: bool = False


class BorradorInformacion(APIModel):
    clave: str = Field(min_length=2, max_length=100)
    titulo: str = Field(min_length=2, max_length=180)
    contenido: str = Field(min_length=1)
    categoria: str = Field(default="General", min_length=1, max_length=80)
    animacion: Literal["idle", "Hablar", "Explicar", "Saludo", "Pensar", "Celebrar"] = "Hablar"
    accion_avatar: str = Field(default="", max_length=500)
    emocion: Literal["neutral", "happy"] = "neutral"


class ImportarInformacionResponse(APIModel):
    borradores: list[BorradorInformacion]
    fuente_guardada: bool
    fuente_ya_existia: bool = False
    fuente_activa: bool = True
    fuente_titulo: str
    aviso_analisis: str | None = None
    analisis_gemini: bool = False
    analisis_visual_gemini: bool = False
    analisis_visual_pendiente: bool = False


class HistorialResponse(APIModel):
    id: int
    usuario_id: int | None
    mensaje: str
    respuesta: str
    origen: str
    pregunta_frecuente_id: int | None
    categoria: str
    modulo: str
    fecha_consulta: datetime


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RegistroPendienteResponse(APIModel):
    id: int
    estado: str = "pendiente"
    mensaje: str = "Solicitud enviada para autorización."
