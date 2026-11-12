# YouMuDow — Modernización integral (diseño)

Fecha: 2026-11-12 · Rama: `feature/modernize-optimize`

## 1. Intención y por qué

YouMuDow es un descargador de música/vídeo de escritorio (Tkinter + yt-dlp) que
funciona bien y está bien estructurado, pero **se ve y se siente anticuado**: tipografía
diminuta, widgets hechos a mano con hover rudimentario, una tabla de resultados sin
miniaturas y sin estados de carga/error diseñados, y un sistema de tema triplicado.

El objetivo es convertir la aplicación existente en un producto moderno, rápido y
agradable **sin reescribirla desde cero y sin perder ninguna funcionalidad**. La persona
que encarga el trabajo prioriza la calidad del resultado final por encima de la velocidad
de entrega.

## 2. Objetivos, no-objetivos y anti-objetivos

**Objetivos**
- UI visiblemente más moderna, coherente y fluida (2026, no años 90).
- Menor tiempo de arranque y menor consumo innecesario de recursos.
- Código más limpio, menos duplicado, más fácil de mantener.
- Toda la funcionalidad actual conservada, con datos/persistencia compatibles.
- Tests que respalden cada fase; cobertura no inferior a la actual (87 %).

**No-objetivos**
- Añadir funciones nuevas de negocio (no se inventan prestaciones).
- Cambiar la arquitectura en capas (ya es correcta).
- Migrar de framework.

**Anti-objetivos (fallaría aunque técnicamente funcionara)**
- Un "lavado de cara" solo cosmético sin mejorar el código ni el rendimiento.
- Efectos visuales exagerados o diseños genéricos "de plantilla IA".
- Optimizaciones marginales a costa de legibilidad.
- Romper configuraciones, historial o persistencia existentes.

## 3. Restricciones

- **Tkinter** (decisión del encargado, confirmada): se mantiene el framework. No hay
  dependencias nuevas de runtime; solo `yt-dlp` y `Pillow` (ya presentes).
- Python `>=3.10`.
- `ruff` (línea 100), `mypy` estricto salvo `youmudow.ui.*` (ignorado a propósito), y
  `pytest` con `fail_under = 70` en cobertura.
- La capa `youmudow.ui.*` no debe volverse un obstáculo de tipos (el `Tk` es dinámico).

## 4. Estado actual (hallazgos)

### 4.1 Arquitectura (sana)
Capas limpias y sin dependencias circulares: `domain` (modelos, enums, validadores) →
`adapters` (yt-dlp) → `services` (descarga, búsqueda, historial, miniaturas, entorno,
notificaciones, actualizador) → `app` (controller, state, events, config) → `ui` (window,
widgets, styles). 141 tests, ~87 % cobertura. Los flujos de red ya corren en hilos daemon.

### 4.2 Por qué se siente anticuado (UI)
1. **Tipografía diminuta**: cuerpo 10 px, títulos 14 px (`ui/styles/constants.py`).
2. **Dos mundos de widgets que se pisan**: `tk.Button` hechos a mano (Search/Cancel/Stop,
   Download, Open Folder, Add All, Queue, OPTIONS, Retry, Clear) conviven con `ttk`
   (Treeview, Combobox, Notebook). Cada botón `tk` repite el mismo bloque `_theme` +
   `add_hover_effect` con bindings `<Enter>/<Leave>`.
3. **Tema triplicado**:
   - `ui/styles/styles.py` (`StyleManager`, ttk/clam);
   - `ui/styles/theme_apply.py` (walk recursivo sobre widgets `tk`);
   - `ui/widgets/results_table.py::_style_treeview` (una tercera copia del estilo del Treeview).
4. **Tabla de resultados sin miniaturas** (solo título/uploader/duración) — lo que más
   transmite "programa viejo".
5. **Sin estados de carga/error/empty diseñados**: "Searching..." inserta una fila de texto
   en la tabla; no hay spinner ni empty-state.
6. **Detalle** con miniatura cargada de forma síncrona con `urlopen` en hilo, sin caché y
   sin cancelación por URL obsoleta (parcial: hay guard de `_last_thumb_url`).
7. **Iconografía** inconsistente: emojis (↺, 🌐, 🗑) solo en el menú contextual del historial.

### 4.3 Rendimiento
- Arranque razonable: el icono se genera programáticamente (sin assets) y los checks
  (clipboard, entorno yt-dlp) se difieren a `after(...)`/hilos.
- **Miniaturas sin caché**: cada selección re-descarga la imagen (red).
- **Repintado de tema** recorre todo el árbol de widgets en cada cambio y se superpone con
  el estilo ttk.
- Notificaciones de estado con throttle de 0.25 s (correcto); el snapshot copia listas
  pequeñas (aceptable).
- `browser_profiles.get_available_browsers()` se cachea 30 s (bien); se llama repetidamente
  desde `options_panel` en cada `update_for_video`.

### 4.4 Código (duplicación / complejidad)
- **`_write_atomic` + `_backup_corrupt` duplicados** íntegramente en `app/config.py` y
  `services/history_service.py`.
- **3 bucles casi idénticos** de resolución de miniaturas en `app/controller.py`
  (`_perform_search`, `_perform_search_url`, `search_playlist`).
- `ui/window.py` (570 líneas) aún concentra cableado de tema, teclado, búsqueda y descarga.
- `ui/widgets/options_panel.py` (566 líneas) construye 6 filas de formulario a mano con
  bloques casi idénticos.
- `app/config.py` mezcla accesores genéricos (`get`, `get_str`) con properties específicas.

## 5. Enfoques considerados

- **A — Pulido profundo sobre Tkinter (elegido).** Tokens de diseño, un solo sistema de
  tema, librería de componentes propia (canvas), miniaturas asíncronas con caché, estados
  diseñados, y simplificación del código. Sin dependencias nuevas. Conserva todo.
- **B — `customtkinter`.** Look moderno ya hecho, pero añade dependencia, menos control y
  obliga a reescribir toda la capa UI actual (riesgo alto, beneficio incierto).
- **C — Migrar a Qt/PySide o Flet.** Look/rendimiento nativos, pero es reescribir la app
  entera: contra las restricciones del encargado. Descartado.

Decisión del encargado: **A**.

## 6. Decisiones de diseño (el "cómo")

### 6.1 Tokens de diseño — una sola fuente de verdad
- Ampliar `ui/styles/constants.py` con una **escala tipográfica** explícita (roles, no
  tamaños sueltos): `display` (18 semibold), `h1` (15 semibold), `h2` (13 semibold),
  `body` (11), `small` (10), `label` (10 semibold, mayúsculas + letter-spacing), `mono` (10).
- Mantener la escala de espaciado (`xs..2xl`) y añadir `3xl` si hace falta.
- `Colors` (dataclass) ya es buena; añadir solo roles que falten (p. ej. `ON_PRIMARY`,
  `SURFACE_HOVER`) si el componente los pide. Sin romper los tests actuales de colores.

### 6.2 Un solo sistema de tema
Unificar los tres mecanismos en uno:
- `StyleManager` (ttk) absorbe el estilo del Treeview que hoy vive en
  `results_table._style_treeview`.
- `apply_theme_colors` (walk `tk`) se mantiene como el único repintado del árbol `tk`.
- Una única función `apply_theme(root, colors)` orquesta ambas; los botones y demás dejan
  de auto-estilarse a mano.
- El toggle de tema pasa a ser una sola llamada (`apply_theme`) + persistencia.

### 6.3 Librería de componentes propia (`ui/widgets/components/`)
- **`RoundedButton`** (canvas, radio ~8 px): variantes `primary/secondary/danger/ghost`,
  estados hover/pressed/disabled, feedback visual sutil. Sustituye a todos los `tk.Button`
  hechos a mano y elimina los bloques `_theme` + `add_hover_effect`.
- **`Card`** (Frame con borde sutil y fondo `surface`).
- **`SearchEntry`** con placeholder real y anillo de foco.
- **`Spinner`** (arco animado en canvas) para estados de carga.
- **`EmptyState`** (icono + texto + acción opcional).
- Se conserva `ttk` para Treeview/Combobox/Notebook (con estilo coherente).

### 6.4 Resultados como lista de tarjetas con miniaturas (cambio visual mayor)
Sustituir el `Treeview` de resultados por una **lista desplazable de tarjetas** (canvas),
cada una con miniatura a la izquierda y título/uploader/duración a la derecha, con hover y
selección múltiple. Se conservan **todas** las interacciones actuales: seleccionar, doble
clic → descargar, clic derecho → abrir en navegador, `Add All` para playlists. **Además se
conserva la navegación por teclado** que hoy da el Treeview: flechas ↑/↓ para mover la
selección y `Enter` (o doble clic) para descargar, integradas con los atajos existentes
(`Ctrl+D`, `Ctrl+Q`). *Decisión del constructor*: si la lista de tarjetas resultara
inestable en algún tamaño, hay plan B (documentado en 6.6) de mantener Treeview con
columna de imagen.

### 6.5 Pipeline de miniaturas (asíncrono + caché)
- Añadir `cache_dir()` a `paths.py` (`~/.cache/youmudow` en Linux, `%LOCALAPPDATA%` en
  Windows) y un **`ThumbnailCache`** con caché en disco + LRU en memoria (~200 entradas).
- Un cargador asíncrono único (cola + hilo daemon) descarga, cachea y entrega `PhotoImage`
  por `after()` al hilo principal. Las tarjetas cargan solo las miniaturas visibles
  (lazy) y cancelan las que quedaron fuera de vista.
- Reutiliza `Pillow` (ya es dependencia). Se elimina el `urlopen` síncrono del detail panel.

### 6.6 Estados y feedback
- Spinner/estado de carga durante búsqueda y carga de miniaturas.
- Empty-states: "Sin resultados", "Historial vacío", "Cola vacía".
- Errores con mensaje claro y acción de reintento donde aplique.
- Transiciones sutiles (hover/focus), nunca animaciones estridentes.

### 6.7 Rendimiento
- **Lazy imports** de módulos pesados (`PIL`, `urllib.request`) solo donde se usan.
- Medir el arranque (timer interno opcional en modo debug) y optimizar lo que aparezca.
- Caché de miniaturas (el mayor ahorro de red/CPU).
- Repintado de tema en una sola pasada.
- Eliminar llamadas redundantes a `get_available_browsers()` en `options_panel`
  (memorizar el resultado por instancia).

### 6.8 Simplificación de código
- Extraer `_write_atomic`/`_backup_corrupt` a un módulo compartido (p. ej.
  `services/persistence.py`) usado por `config` e `history`.
- Unificar los 3 bucles de miniaturas del controller en un helper.
- Construcción de formularios del `options_panel` basada en datos (fila = spec), no en
  bloques copiados.
- Adelgazar `window.py` (extraer el manejo de tema y atajos).

## 7. Plan por fases (prioridad por impacto/riesgo)

Cada fase termina con: tests verdes (`ruff` + `mypy` + `pytest`), commit atómico, y smoke
test de arranque en X cuando toque la UI. La rama ya existe (`feature/modernize-optimize`).

- **Fase 0 — Línea base y arnés de verificación.** Registrar estado actual (tests, cobertura,
  tiempo de arranque), confirmar el smoke test de UI y la medición de arranque.
- **Fase 1 — Tokens + sistema de tema único.** Consolidar los 3 sistemas de tema en uno;
  nueva escala tipográfica. (Fundación de todo lo demás.)
- **Fase 2 — Librería de componentes.** `RoundedButton`, `Card`, `SearchEntry`, `Spinner`,
  `EmptyState`; migrar los botones existentes. (Sustituye el hover rudimentario.)
- **Fase 3 — Miniaturas asíncronas + caché.** `ThumbnailCache` + cargador; migrar el detail
  panel; dejar la infraestructura lista para las tarjetas.
- **Fase 4 — Resultados como tarjetas.** Lista desplazable con miniaturas y selección
  múltiple, preservando interacciones.
- **Fase 5 — Estados de carga/empty/error + feedback.** Spinners y empty-states en búsqueda,
  historial y cola.
- **Fase 6 — Rendimiento.** Lazy imports, medición de arranque, eliminación de trabajo
  redundante; comparar antes/después.
- **Fase 7 — Simplificación de código.** Dedup de persistencia y miniaturas, formulario por
  datos, adelgazar `window.py`/`options_panel.py`.
- **Fase 8 — Validación final.** Suite completa + cobertura, smoke test en X, revisión de
  logs/consola, resumen técnico.

## 8. Qué queda al constructor

- Detalles de implementación de los componentes canvas y del layout de tarjetas (dentro de
  los tokens y variantes definidos aquí).
- Orden exacto de migración de cada widget dentro de las fases.
- Estrategia de caché concreta (nombres de archivo por `video_id`, TTL, evicción).
- Cualquier decisión menor que no cambie el comportamiento ni el alcance.

## 9. Preservación de funcionalidades (compromiso)

- No se elimina ninguna funcionalidad, flujo, atajo de teclado, opción de descarga ni
  entrada de menú.
- La persistencia (`config.json`, `history.json`) mantiene formato y ubicación; se lee y
  escribe de forma compatible.
- Las interacciones de la tabla de resultados (selección simple/múltiple, doble clic,
  clic derecho, playlist "Add All") se conservan 1:1 en la lista de tarjetas.
- Cualquier cambio de comportamiento o eliminación se consulta antes de aplicarse.
