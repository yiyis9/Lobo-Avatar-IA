from pathlib import Path
import json
import re

src = Path(r"C:\Users\irisg\Downloads\Tablero Scrum Lobo UPVT.html")
out = Path(r"C:\Users\irisg\Documents\LoboUPVT\Tablero_Scrum_Lobo_UPVT_actualizado.html")
html = src.read_text(encoding="utf-8")

match = re.search(r"const HU=(\[.*?\]);\s*const GOALS=", html, re.S)
if not match:
    raise SystemExit("No se pudo localizar el backlog de historias.")
stories = json.loads(match.group(1))

def set_story(n, *, title=None, role=None, want=None, purpose=None, criteria=None, tasks=None, ref=None):
    story = stories[n - 1]
    if title is not None: story[3] = title
    if role is not None: story[4] = role
    if want is not None: story[5] = want
    if purpose is not None: story[6] = purpose
    if criteria is not None: story[7] = criteria
    if tasks is not None: story[8] = tasks
    if ref is not None: story[12] = ref

set_story(5, title="Modelo ER y diccionario de datos", role="Desarrolladora",
    want="documentar las ocho tablas vigentes del backend con sus campos, claves y relaciones",
    purpose="explicar la estructura real de lobo_upvt_db y mantener trazabilidad con las migraciones",
    criteria=["El modelo incluye las ocho tablas que declaran los modelos SQLAlchemy vigentes.",
              "El diccionario identifica campos, tipos, PK, FK, UQ y cardinalidades sin añadir entidades inexistentes.",
              "El Product Owner revisa el diagrama ER y el diccionario."],
    tasks=["Contrastar models.py con migraciones 001–018", "Documentar tablas y relaciones", "Revisar el diagrama con el Product Owner"],
    ref="backend/models.py · migraciones 001–018")
set_story(6, title="Esquema MySQL y migraciones", role="Desarrolladora",
    want="mantener la base MySQL alineada con los modelos y migraciones del backend",
    purpose="guardar cuentas, contenido, documentos, consultas y contactos con integridad referencial",
    criteria=["Las migraciones aditivas se aplican en orden sin perder registros existentes.",
              "Las claves foráneas e índices corresponden al esquema vigente.",
              "La búsqueda FULLTEXT cubre preguntas, contenido institucional y texto documental."],
    tasks=["Revisar DDL y migraciones pendientes", "Comprobar claves e índices", "Validar respaldo antes de cambios de esquema"],
    ref="RF02, RF04 · MySQL")
set_story(9, title="API CRUD de preguntas e información institucional", role="Administradora de contenido",
    want="crear, consultar, editar y retirar preguntas frecuentes e información institucional desde el panel",
    purpose="mantener actualizado el contenido que responde el kiosko",
    criteria=["Las rutas validan datos y aplican permisos por rol.",
              "Los cambios se guardan en MySQL y están disponibles en las consultas siguientes.",
              "Las categorías se conservan como campos de clasificación; no se documenta una tabla de categorías que el esquema no tiene."],
    tasks=["Revisar rutas y esquemas Pydantic", "Verificar operaciones CRUD", "Comprobar permisos y lectura posterior desde el kiosko"],
    ref="RF05, RNF09 · backend/routers/admin.py")
set_story(11, title="Errores controlados y registros técnicos", role="Desarrolladora",
    want="manejar fallos de API y base de datos con respuestas controladas",
    purpose="evitar que errores internos interrumpan toda la interacción o expongan datos técnicos",
    criteria=["Los fallos previsibles devuelven códigos HTTP y mensajes controlados.",
              "Los detalles técnicos se registran en backend y no se muestran como secretos al visitante.",
              "Se documentan las fallas reproducibles y su resultado."],
    tasks=["Revisar excepciones de routers y servicios", "Verificar registros técnicos", "Ejecutar casos de error"],
    ref="Fiabilidad · API FastAPI")
set_story(15, title="HTTPS y protección de datos", role="Administradora del sistema",
    want="proteger las solicitudes y los datos personales del kiosko y del panel",
    purpose="reducir exposición de información durante el uso y la operación del sistema",
    criteria=["La API de producción se publica detrás de TLS y el panel y kiosko usan HTTPS.",
              "Las contraseñas se almacenan como hashes y los códigos de recuperación como hashes.",
              "La UPVT aprueba el aviso de privacidad y los periodos de conservación antes de declarar cumplimiento institucional."],
    tasks=["Configurar TLS y FORCE_HTTPS en producción", "Revisar datos y retención", "Solicitar validación institucional del aviso"],
    ref="RNF01–RNF02 · despliegue y privacidad")
set_story(20, title="Historial de consultas", role="Administradora autorizada",
    want="consultar las preguntas, respuestas, módulo, categoría, fecha y metadatos del avatar",
    purpose="dar seguimiento al uso del kiosko y analizar qué información hace falta",
    criteria=["Cada interacción guarda mensaje, respuesta, módulo, categoría y fecha.",
              "El historial incluye preguntas frecuentes, información institucional, saludos, aclaraciones y consultas sin coincidencia.",
              "La clave de solicitud evita duplicados al reintentar."],
    tasks=["Verificar columnas y migración 017", "Revisar registro de los módulos", "Comprobar filtros y conservación del historial"],
    ref="RF04 · migraciones 013 y 017")
set_story(25, title="Gestor de contenido institucional", role="Administradora de contenido",
    want="buscar, crear, editar y retirar preguntas, fichas institucionales y sus archivos adjuntos",
    purpose="actualizar lo que el kiosko puede responder sin tocar código ni reiniciar FastAPI",
    criteria=["El panel permite buscar y filtrar contenido y administrar sus adjuntos.",
              "Los cambios se guardan con las animaciones, emoción y acción del avatar asociadas.",
              "El contenido guardado se utiliza en las consultas siguientes."],
    tasks=["Revisar formularios y filtros", "Verificar gestión de adjuntos", "Comprobar la respuesta del kiosko después de guardar"],
    ref="RF05, RNF09 · panel de contenido")
set_story(26, title="Usuarios, solicitudes y permisos", role="Administradora autorizada",
    want="gestionar cuentas, solicitudes, roles y papelera con permisos protegidos",
    purpose="dar acceso al personal y proteger la cuenta administradora principal",
    criteria=["Las rutas y la interfaz aplican las restricciones correspondientes a cada rol.",
              "La cuenta administradora principal no se elimina desde la papelera.",
              "Las solicitudes y cambios de rol requieren autorización según las reglas del sistema."],
    tasks=["Revisar matrices de permisos", "Comprobar solicitudes y roles", "Verificar protección de administrador principal"],
    ref="RF05 · RBAC y seguridad de cuentas")
set_story(27, title="Respaldos, papelera y estado del servicio", role="Administradora del sistema",
    want="respaldar información, revisar elementos en papelera y conocer el estado de API y MySQL",
    purpose="recuperar contenido y operar el panel con información clara del servicio",
    criteria=["El panel ofrece operaciones de respaldo disponibles para el rol.",
              "La papelera permite revisar y restaurar registros dentro del periodo de retención.",
              "El panel informa el estado de conexión de API y MySQL."],
    tasks=["Revisar respaldos y restauración", "Comprobar papelera y retención", "Validar indicadores de salud"],
    ref="Panel administrativo · respaldo, papelera y salud")
set_story(28, title="Avatar 3D en Unity", role="Visitante del kiosko",
    want="ver el modelo articulado del Lobo UPVT dentro de Unity",
    purpose="presentar al asistente durante la interacción",
    criteria=["El modelo se carga en la escena de Unity sin duplicar avatares.",
              "El tamaño, materiales y postura inicial se revisan en el Editor.",
              "La escena final se valida con el avatar y los recursos actuales."],
    tasks=["Conservar un único modelo activo", "Revisar escala y materiales", "Abrir y validar la escena final"],
    ref="RF08 · validación en Unity")
set_story(29, title="Animaciones y rig del Lobo", role="Visitante del kiosko",
    want="ver al Lobo saludar y acompañar las respuestas con movimientos naturales",
    purpose="hacer que el avatar comunique la intención de sus respuestas",
    criteria=["Los clips disponibles corresponden a los parámetros de animación de la API.",
              "La postura de reposo mantiene las manos abajo.",
              "El saludo se valida visualmente en Unity y no presenta cortes ni deformaciones evidentes."],
    tasks=["Revisar rig y jerarquía de huesos", "Ajustar transiciones del Animator", "Validar saludo, reposo y habla en escena"],
    ref="RF03, RF09 · validación visual pendiente")
set_story(30, title="Interfaz del kiosko Lobo UPVT", role="Aspirante o visitante",
    want="consultar información institucional mediante texto, voz y controles accesibles",
    purpose="encontrar orientación universitaria desde una interfaz sencilla",
    criteria=["El kiosko muestra pregunta, respuesta y subtítulos legibles.",
              "La persona puede reproducir la voz de la respuesta y volver a escucharla.",
              "El formulario de contacto y los controles accesibles son localizables."],
    tasks=["Revisar flujo de consulta", "Validar respuesta con audio y subtítulos", "Comprobar contacto y accesibilidad"],
    ref="RF01, RNF05–RNF06")
set_story(31, title="Cliente de API en Unity", role="Visitante del kiosko",
    want="enviar consultas a FastAPI desde el cliente Unity",
    purpose="recibir respuestas y metadatos para el avatar",
    criteria=["El cliente envía la consulta al endpoint configurado.",
              "La interfaz gestiona errores de red sin bloquear la escena.",
              "La integración se compila y prueba en el Editor con la API disponible."],
    tasks=["Revisar cliente HTTP", "Comprobar configuración de endpoint", "Validar respuesta en escena"],
    ref="RF01, RF03 · validación Unity pendiente")
set_story(32, title="Animación del avatar por metadatos", role="Visitante del kiosko",
    want="ver que la respuesta active la animación y emoción asociadas",
    purpose="hacer congruentes el texto y el comportamiento del Lobo",
    criteria=["Unity interpreta animacion, emocion y accion_avatar recibidas de la API.",
              "Los valores desconocidos usan una animación de respaldo sin detener el kiosko.",
              "Los clips y transiciones se validan con respuestas reales."],
    tasks=["Revisar mapeo de metadatos", "Comprobar animación de respaldo", "Probar respuestas de varias categorías"],
    ref="RF03, RF09")
set_story(35, title="Detección de presencia con cámara", role="Visitante del kiosko",
    want="activar la cámara de forma voluntaria para que el Lobo detecte presencia",
    purpose="iniciar una bienvenida cuando una persona se acerca",
    criteria=["La cámara solo inicia después de conceder permiso y activar la función.",
              "La detección activa la bienvenida sin identificar a la persona.",
              "El comportamiento se valida en el navegador y en distintas condiciones de luz."],
    tasks=["Revisar permiso y activación", "Validar detección local", "Probar condiciones de iluminación"],
    ref="RF06 · kiosko web")
set_story(36, title="Puntos de referencia de rostro y mano", role="Desarrolladora",
    want="detectar presencia y gestos básicos con MediaPipe en el kiosko web",
    purpose="activar saludos y respuestas gestuales sin enviar imágenes al servidor",
    criteria=["El módulo procesa puntos de referencia localmente en el navegador.",
              "No se conserva la imagen ni se usa para reconocer identidad.",
              "Se verifica que el procesamiento no interfiera con la consulta y el audio."],
    tasks=["Revisar carga de MediaPipe", "Comprobar detección de gestos", "Validar detención de cámara al salir"],
    ref="RF07 · privacidad de cámara")
set_story(37, title="Activación del kiosko con visión por computadora", role="Visitante del kiosko",
    want="recibir un saludo amable cuando activo la cámara y el kiosko detecta presencia",
    purpose="comenzar la interacción sin conectar eventos de cámara a Unity cuando se usa el kiosko web",
    criteria=["La cámara requiere permiso explícito.",
              "La detección activa la bienvenida en la interfaz web.",
              "Al dejar de interactuar, el avatar vuelve a reposo según el comportamiento implementado."],
    tasks=["Conectar presencia con bienvenida web", "Validar pausa por inactividad", "Probar el ciclo completo en navegador"],
    ref="RF06 · kiosko web, no integración de cámara con Unity")
set_story(38, title="Privacidad y control de cámara", role="Visitante del kiosko",
    want="saber cuándo la cámara está activa y poder detenerla",
    purpose="usar la detección de presencia con control y transparencia",
    criteria=["La activación depende del permiso y de una acción explícita.",
              "El procesamiento visual ocurre localmente y no guarda ni transmite imágenes.",
              "La cámara se detiene al desactivar la función o salir del kiosko."],
    tasks=["Revisar mensajes de permiso", "Verificar ausencia de almacenamiento de imágenes", "Comprobar cierre de cámara"],
    ref="RNF02, RF06–RF07")
set_story(39, title="Pregunta dictada por voz", role="Visitante del kiosko",
    want="dictar una pregunta y revisar la transcripción antes de enviarla",
    purpose="consultar sin escribir en la pantalla",
    criteria=["El reconocimiento solicita permiso del micrófono y muestra lo reconocido.",
              "La persona puede enviar la transcripción o volver a intentarlo.",
              "Los errores de reconocimiento no cierran la interacción."],
    tasks=["Revisar permiso del micrófono", "Validar transcripción visible", "Probar errores y reintento"],
    ref="Interacción por voz · kiosko")
set_story(40, title="Respuesta hablada y repetición de voz", role="Visitante del kiosko",
    want="escuchar la respuesta del Lobo y repetirla con un control de audio",
    purpose="entender la información sin depender únicamente del texto",
    criteria=["La voz se reproduce desde la respuesta recibida.",
              "El control de audio permite repetir la respuesta actual.",
              "Los subtítulos permanecen visibles durante la reproducción y puede detenerse el audio."],
    tasks=["Revisar voz sintetizada", "Validar el botón de repetir", "Comprobar subtítulos y detención"],
    ref="Accesibilidad del kiosko · audio y subtítulos")
set_story(41, title="Accesibilidad de voz y subtítulos", role="Visitante del kiosko",
    want="ajustar la lectura y presentación de las respuestas",
    purpose="usar el kiosko con distintas necesidades de audición y visión",
    criteria=["Los subtítulos son claros y su posición no tapa los controles principales.",
              "Hay un control identificable para reproducir de nuevo la voz.",
              "Las opciones de accesibilidad se prueban con teclado y pantalla real."],
    tasks=["Revisar ubicación de subtítulos", "Validar botón de audio", "Realizar revisión de contraste y teclado"],
    ref="RNF06 · auditoría pendiente")
set_story(42, title="Medición de rendimiento", role="Desarrolladora",
    want="medir consultas y acciones principales de extremo a extremo",
    purpose="comprobar tiempos reales sin afirmar métricas no medidas",
    criteria=["Se registran tiempos de respuesta con FastAPI, MySQL y Gemini según aplique.",
              "Se mide una carga representativa y se documenta el entorno.",
              "El criterio de menos de 2 segundos se declara cumplido solo si los resultados lo demuestran."],
    tasks=["Definir escenarios y entorno", "Medir latencias", "Documentar cuellos de botella"],
    ref="RNF03, RNF07 · medición pendiente")
set_story(43, title="Pruebas de integración del kiosko", role="Product Owner",
    want="revisar el flujo de texto, voz, búsqueda institucional y metadatos del avatar",
    purpose="comprobar que web, API y MySQL se comportan juntos",
    criteria=["Las pruebas unitarias existentes se distinguen de las pruebas integrales.",
              "Se prueban saludos, búsquedas de contenido, consultas sin coincidencia y registro de historial.",
              "Los casos y resultados quedan documentados; la prueba Unity se identifica por separado."],
    tasks=["Inventariar pruebas automatizadas", "Ejecutar casos de flujo completo", "Registrar defectos y resultados"],
    ref="RF01–RF10 · integración pendiente")
set_story(44, title="Pruebas de carga y concurrencia", role="Desarrolladora",
    want="medir la API y MySQL con consultas simultáneas",
    purpose="conocer la capacidad real antes de instalar el sistema en producción",
    criteria=["Se documenta volumen, equipo, duración y configuración de la prueba.",
              "Se miden latencia, errores y uso de conexiones de base de datos.",
              "No se declara capacidad objetivo sin resultados reproducibles."],
    tasks=["Definir carga de prueba", "Ejecutar y observar métricas", "Preparar reporte de resultados"],
    ref="RNF03, RNF07 · pendiente")
set_story(45, title="Verificación de permisos y seguridad", role="Administradora del sistema",
    want="comprobar que cada rol solo pueda realizar sus acciones autorizadas",
    purpose="proteger las cuentas, el contenido y los datos personales",
    criteria=["Se verifican rutas administrativas con y sin token y con cada rol.",
              "Se comprueba la protección de la cuenta principal y los códigos de recuperación.",
              "Los hallazgos se registran; no se afirma que el sistema sea totalmente seguro."],
    tasks=["Preparar matriz por rol", "Ejecutar pruebas negativas", "Documentar vulnerabilidades y correcciones"],
    ref="RBAC · RNF01–RNF02")
set_story(46, title="Pruebas de usabilidad y accesibilidad", role="Visitante del kiosko",
    want="probar el kiosko y el panel con personas usuarias",
    purpose="detectar barreras reales de comprensión, lectura y navegación",
    criteria=["Se registran participantes, tareas y resultados sin datos personales innecesarios.",
              "Se revisan navegación por teclado, contraste, subtítulos y controles de audio.",
              "Los problemas encontrados se priorizan y se documenta su resolución."],
    tasks=["Preparar guion de tareas", "Realizar sesiones autorizadas", "Priorizar y corregir hallazgos"],
    ref="RNF05–RNF06 · pruebas con usuarios pendientes")
set_story(47, title="Despliegue local y preparación de producción", role="Administradora del sistema",
    want="instalar FastAPI, MySQL y el kiosko en el entorno que se utilizará",
    purpose="operar el sistema con configuración documentada y respaldos",
    criteria=["El entorno local puede iniciarse siguiendo instrucciones reproducibles.",
              "La publicación de producción requiere TLS, configuración segura y validación institucional.",
              "Se verifica el funcionamiento en el equipo objetivo antes de declarar el despliegue terminado."],
    tasks=["Documentar arranque local", "Preparar variables y servicio de producción", "Validar el equipo kiosko"],
    ref="RNF01, RNF04 · despliegue final pendiente")
set_story(48, title="Documentación técnica y diccionario de datos", role="Administradora del sistema",
    want="consultar instalación, operación, mantenimiento y estructura de la base de datos",
    purpose="facilitar soporte y continuidad del proyecto",
    criteria=["La documentación coincide con los modelos y migraciones vigentes.",
              "El diccionario describe las ocho tablas del backend y sus campos.",
              "Las brechas de despliegue, Unity y validación se distinguen de las funciones implementadas."],
    tasks=["Revisar README y API.md", "Entregar el diccionario de datos", "Registrar pasos pendientes de operación"],
    ref="RNF08 · documentación del sistema")

goals = {
    "1":"Alcance, requisitos, backlog inicial y entorno de trabajo.",
    "2":"Modelo de datos real, diccionario, diagrama ER y migraciones MySQL.",
    "3":"Estructura FastAPI, validación, CRUD y catálogo institucional.",
    "4":"Registro, inicio de sesión, RBAC y recuperación de contraseña.",
    "5":"Chat del kiosko, búsqueda en MySQL, respuestas sociales e historial.",
    "6":"Panel administrativo: resumen, perfil, solicitudes y usuarios.",
    "7":"Panel de contenido: preguntas, fichas, documentos, mensajes, respaldos y papelera.",
    "8":"Avatar, rig, animaciones y experiencia visual del kiosko; validar en Unity.",
    "9":"Conexión de cliente, metadatos de animación y recuperación de conexión.",
    "10":"Cámara opcional y visión por computadora en el kiosko web.",
    "11":"Dictado, voz de respuesta, subtítulos y controles de accesibilidad.",
    "12":"Pruebas unitarias, integración, carga, permisos, accesibilidad y usabilidad.",
    "13":"Despliegue, manuales, capacitación, aceptación y memoria final."
}

# Status describes evidence maturity; unchecked acceptance criteria remain unchecked.
status_groups = {
    "test": [2,6,8,9,11,12,13,14,16,17,18,19,20,21,22,23,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,43,45],
    "review": [1,4,5,7,10,48],
    "doing": [3,15,24,41,42,50],
    "todo": [44,46,47,49],
    "done": []
}
status_map = {f"HU-{n:02d}": status for status, numbers in status_groups.items() for n in numbers}
if len(status_map) != len(stories):
    raise SystemExit(f"Status map incomplete: {len(status_map)} statuses for {len(stories)} stories")

new_stories = json.dumps(stories, ensure_ascii=False, separators=(",", ":"))
html = html[:match.start(1)] + new_stories + html[match.end(1):]
goal_match = re.search(r"const GOALS=(\{.*?\});\s*const COLS=", html, re.S)
if not goal_match:
    raise SystemExit("No se pudo localizar la planificación de sprints.")
html = html[:goal_match.start(1)] + json.dumps(goals, ensure_ascii=False, separators=(",", ":")) + html[goal_match.end(1):]

col_match = re.search(r"const COLS=(\[.*?\]);\s*const EPIC=", html, re.S)
cols = [["todo","Pendiente"],["doing","En desarrollo"],["test","Validación técnica"],["review","Validación con PO"],["done","Aceptado"]]
html = html[:col_match.start(1)] + json.dumps(cols, ensure_ascii=False, separators=(",", ":")) + html[col_match.end(1):]

hours = sum(int(x[11]) for x in stories)
points = sum(int(x[10]) for x in stories)
html = html.replace("13 sprints semanales · 50 historias · 600 horas", f"13 sprints · 50 historias · {points} pts · {hours} h estimadas")
html = html.replace('localStorage.setItem("lobo-board"', 'localStorage.setItem("lobo-board-lobo-upvt-v2"')
html = html.replace('localStorage.getItem("lobo-board"', 'localStorage.getItem("lobo-board-lobo-upvt-v2"')
html = html.replace('<span>Historias hechas</span>', '<span>Historias aceptadas</span>')
html = html.replace('<span>Puntos</span>', '<span>Puntos aceptados</span>')
html = html.replace('<p class="note" id="syncnote"></p>', '<p class="note" id="syncnote"></p><p class="note">Estado base sugerido al 20-nov-2026 según revisión del código y documentos del proyecto. Avance estimado ponderado por puntos: desarrollo 25 %, validación técnica 70 %, validación con PO 90 %, aceptado 100 % y pendiente 0 %. No equivale a aceptación formal; los criterios siguen sin marcar hasta validarlos.</p>')

old_stats = '''function sprintStats(n){const hs=H.filter(h=>h.sprint===n);const d=hs.filter(h=>st(h.id)==="done");
  return{n:hs.length,done:d.length,sp:hs.reduce((a,h)=>a+h.sp,0),spDone:d.reduce((a,h)=>a+h.sp,0),hrs:hs.reduce((a,h)=>a+h.hrs,0),hrsDone:d.reduce((a,h)=>a+h.hrs,0)}}'''
new_stats = '''const STATUS_WEIGHT={todo:0,doing:.25,test:.7,review:.9,done:1};
function sprintStats(n){const hs=H.filter(h=>h.sprint===n);const d=hs.filter(h=>st(h.id)==="done");
  return{n:hs.length,done:d.length,sp:hs.reduce((a,h)=>a+h.sp,0),spDone:d.reduce((a,h)=>a+h.sp,0),spProgress:hs.reduce((a,h)=>a+h.sp*(STATUS_WEIGHT[st(h.id)]||0),0),hrs:hs.reduce((a,h)=>a+h.hrs,0),hrsDone:d.reduce((a,h)=>a+h.hrs,0),hrsProgress:hs.reduce((a,h)=>a+h.hrs*(STATUS_WEIGHT[st(h.id)]||0),0)}}'''
if old_stats in html:
    html = html.replace(old_stats, new_stats)
elif "function sprintStats(n)" not in html or "spProgress" not in html:
    raise SystemExit("No se pudo actualizar el cálculo por sprint.")

old_totals = '''function totals(){const T=H.reduce((a,h)=>(a.sp+=h.sp,st(h.id)==="done"&&(a.d+=h.sp,a.n++),a),{sp:0,d:0,n:0});
  $("#totals").innerHTML=`<div class="tot"><b>${T.n}/50</b><span>Historias aceptadas</span></div><div class="tot"><b>${T.d}/${T.sp}</b><span>Puntos aceptados</span></div><div class="tot"><b>${Math.round(T.d/T.sp*100)}%</b><span>Avance total</span></div>`}'''
new_totals = '''function totals(){const T=H.reduce((a,h)=>(a.sp+=h.sp,a.progress+=h.sp*(STATUS_WEIGHT[st(h.id)]||0),st(h.id)==="done"&&(a.d+=h.sp,a.n++),a),{sp:0,progress:0,d:0,n:0});
  $("#totals").innerHTML=`<div class="tot"><b>${T.n}/50</b><span>Historias aceptadas</span></div><div class="tot"><b>${Math.round(T.progress)}/${T.sp}</b><span>Puntos de avance estimado</span></div><div class="tot"><b>${Math.round(T.progress/T.sp*100)}%</b><span>Avance total estimado</span></div>`}'''
if old_totals in html:
    html = html.replace(old_totals, new_totals)
elif "Avance total estimado" not in html:
    raise SystemExit("No se pudo actualizar el indicador total.")

html = html.replace('''<div class="meta"><div class="row"><span>Puntos aceptados</span><b>${s.spDone}/${s.sp}</b></div><div class="bar"><i style="width:${s.sp?s.spDone/s.sp*100:0}%"></i></div>
   <div class="row"><span>Horas de desarrollo</span><b>${s.hrsDone}/${s.hrs} h</b></div></div>''', '''<div class="meta"><div class="row"><span>Avance ponderado</span><b>${Math.round(s.spProgress)}/${s.sp} pts</b></div><div class="bar"><i style="width:${s.sp?s.spProgress/s.sp*100:0}%"></i></div>
   <div class="row"><span>Historias aceptadas</span><b>${s.done}/${s.n}</b></div></div>''')
all_view = re.search(r"function allView\(\)\{.*?\}\nfunction wire\(\)", html, re.S)
if not all_view:
    raise SystemExit("No se pudo actualizar el resumen de sprints.")
all_view_js = '''function allView(){let rows="";for(let n=1;n<=13;n++){const s=sprintStats(n);rows+=`<div class="srow"><button data-n="${n}">Sprint ${n}</button><div><div class="bar"><i style="width:${s.sp?s.spProgress/s.sp*100:0}%"></i></div><div class="g">${esc(GOALS[n])}</div></div><div class="pp">${Math.round(s.spProgress)}/${s.sp} pts · ${s.done}/${s.n} aceptadas</div></div>`}
  $("#view").innerHTML=`<section class="overview"><h2>Avance estimado por sprint</h2>${rows}</section><section class="overview"><h2>Burndown estimado</h2>${burndown()}</section>`;
  document.querySelectorAll(".srow button").forEach(b=>b.onclick=()=>{view="sprint";cur=+b.dataset.n;render()})}
function wire()'''
html = html[:all_view.start()] + all_view_js + html[all_view.end():]
html = html.replace("planRem-=s.sp;actRem-=s.spDone;plan.push(planRem);act.push(actRem)", "planRem-=s.sp;actRem-=s.spProgress;plan.push(planRem);act.push(actRem)")
html = html.replace("if(sprintStats(n).spDone>0)l=n", "if(sprintStats(n).spProgress>0)l=n")
html = html.replace('aria-label="Burndown: puntos restantes por sprint, plan contra avance real"', 'aria-label="Burndown estimado: puntos restantes ponderados por estado, plan contra avance estimado"')
html = html.replace('<h2>Burndown</h2>', '<h2>Burndown estimado</h2>')

html = html.replace("const S={}; // id -> {status, checks:[bool]}", "const S=Object.fromEntries(" + json.dumps(list(status_map.items()), ensure_ascii=False, separators=(",", ":")) + ".map(([id,status])=>[id,{status,checks:[]} ])); // estado inicial según revisión del proyecto")
out.write_text(html, encoding="utf-8")
print(f"{out}\nHistorias={len(stories)}\nCampos/horas estimadas={hours}\nPuntos={points}\nEstado={status_groups}")
