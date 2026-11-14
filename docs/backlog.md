# YouMuDow — Backlog técnico

> Punto de partida: `main` @ `2edf772` (merge del PR #35, 2026-11-13).
> Suite: 727 tests en verde. `ruff` + `mypy` (estricto también en `youmudow.ui.*`) + `pytest` verdes en CI.
> Este documento recoge lo que **quedó pendiente** tras las revisiones de código de la
> modernización (PR #34) y del tipado de la UI (PR #35), más los riesgos detectados
> durante el trabajo. No es una lista de deseos: todo lo marcado como **verificado**
> se comprobó en el código o en una ejecución real.

## Cómo usar este documento

- **P1** = puede afectar al usuario o romper el CI. Atender primero.
- **P2** = deuda técnica que encarece el próximo cambio.
- **P3** = pulido de UX, sin riesgo.
- Cada entrada dice *qué*, *dónde*, *por qué importa* y *cómo arreglarlo*.
- Las líneas de código pueden haberse desplazado; usa los nombres de función como ancla.

---

## P1 — Riesgos que conviene cerrar pronto

### 1. Test flaky: SIGABRT intermitente de la suite (hilo daemon + GC)

**Verificado.** En 3 sesiones distintas la suite completa abortó de forma intermitente
(`Fatal Python error: Aborted`, con el hilo principal en *Garbage-collecting*). Se
reprodujo también sobre la rama base sin los cambios, así que **es preexistente**, no
una regresión. Un caso concreto ya se corrigió (`test_startup_checks.py`, donde un
`Mock` se resolvía de forma perezosa desde un hilo daemon); el patrón general sigue ahí.

- **Dónde:** cualquier test que arranque un hilo daemon que toque objetos de Python
  mientras el hilo principal bombea el bucle de Tk. Sospechoso principal actual:
  `ThumbnailLoader` (`src/youmudow/services/thumbnail_loader.py`), que se crea por
  defecto en `DetailPanel` (ver P2.1).
- **Por qué importa:** un CI rojo aleatorio cuesta tiempo y erosiona la confianza en la suite.
- **Cómo arreglarlo:**
  1. Garantizar `ThumbnailLoader.shutdown()` en el *teardown* de todo test que construya
     un `DetailPanel`/`MainWindow`.
  2. Valorar un fixture de sesión en `tests/conftest.py` que falle si quedan hilos vivos
     (`threading.enumerate()` antes/después), para que el problema se vea como test rojo
     determinista y no como abort del intérprete.
  3. Opcional: `pytest-timeout` para acotar cuelgues.

### 2. El test que invoca `mypy` en subprocess acopla el job de tests al entorno de Pillow

**Verificado.** `tests/unit/test_typing.py::test_mypy_passes_on_ui_package` lanza
`python -m mypy src/youmudow/ui` dentro del job de tests. Cuando el typecheck falló por
la deriva de Pillow (ver P1.3), **los 3 jobs de tests fallaron en cascada** por este
test, no por defectos independientes.

- **Por qué importa:** un fallo de tipos tumba 4 jobs en vez de 1, y el diagnóstico se
  vuelve confuso.
- **Cómo arreglarlo:** dejar ese test solo con las aserciones de configuración
  (`pyproject.toml` sin `ignore_errors`) y mover la comprobación real de `mypy` al job
  `typecheck`, que ya lo ejecuta. Alternativa: marcarlo `@pytest.mark.slow` y excluirlo
  del job de tests.
- **✅ Arreglado (2026-11-14):** eliminado `test_mypy_passes_on_ui_package`; las
  aserciones de configuración se quedan y el typecheck real lo hace solo el job
  `typecheck`. Añadido el test guardián
  `TestNoDuplicateTypecheck::test_no_test_module_shells_out_to_mypy`, que falla si
  cualquier módulo de `tests/` vuelve a invocar mypy por subprocess.

### 3. Deriva de versión de Pillow entre local y CI

**Verificado.** `pyproject.toml` exige `Pillow>=10.0.0`, pero el entorno local de
desarrollo tiene **Pillow 9.0.1** y el CI instala **12.x**. Eso ya provocó un CI rojo:
Pillow 9 no trae `py.typed` (el `# type: ignore[import-untyped]` hace falta) y Pillow 12
sí (el ignore sobra y `warn_unused_ignores = true` lo marca). Además Pillow 12 retiró el
alias de módulo `Image.LANCZOS`.

- **Estado:** mitigado con `_lanczos_filter()` en
  `src/youmudow/ui/widgets/components/thumbnail.py`, que prefiere
  `Image.Resampling.LANCZOS` y cae al alias antiguo.
- **Por qué importa:** el entorno local no reproduce el del CI; cualquier dependencia
  nueva puede repetir el problema.
- **Cómo arreglarlo:**
  1. Recrear el entorno local con las versiones de `pyproject.toml`
     (`python -m pip install -e ".[dev]"` en un venv limpio).
  2. Fijar un rango explícito (p. ej. `Pillow>=10,<13`) y/o añadir una fila de matriz
     que pruebe la versión mínima.

### 4. `DetailPanel` construye un `ThumbnailLoader` real cuando no se le inyecta

**Verificado.** `src/youmudow/ui/widgets/detail_panel.py` (~línea 30):

```python
thumbnail_loader: ThumbnailLoader | None = None
...
self._thumbnail_loader = thumbnail_loader if thumbnail_loader is not None else ThumbnailLoader(...)
```

- **Por qué importa:** cualquier test que construya un `DetailPanel` sin loader crea un
  hilo daemon y escribe en el caché real del usuario (`~/.cache/youmudow`). Es la vía
  más probable hacia el flaky de P1.1.
- **Cómo arreglarlo:** hacer el loader obligatorio en el constructor (el único sitio de
  producción ya lo inyecta desde `MainWindow`), o aceptar una interfaz mínima
  (`Protocol`) y usar un doble no-op en tests.

---

## P2 — Deuda técnica (mantenibilidad)

### 1. `SearchEntry` obliga a enganchar atajos sobre su widget privado

**Verificado.** `src/youmudow/ui/widgets/search_bar.py` hace
`inner_entry = self._entry._entry` y enlaza ahí `Ctrl+Return`, `Ctrl+V`, `Ctrl+A`,
`Ctrl+BackSpace`. El componente expone `get/set/clear/focus_set`, pero no una forma
pública de añadir atajos.

- **Por qué importa:** cualquier cambio interno de `SearchEntry` rompe la barra sin que
  el compilador ni los tipos avisen.
- **Cómo arreglarlo:** añadir `SearchEntry.bind_shortcut(sequence, handler)` (o
  `bind_key`) y usarlo desde `SearchBar`.

### 2. El placeholder vive en la variable compartida (`search_var`)

**Verificado (decisión consciente en el PR #35).** Cuando el campo está vacío,
`search_var.get()` devuelve el texto del placeholder. Los consumidores deben usar
`get_query()`; si alguien usa `search_var` directamente, obtiene el placeholder como si
fuera una búsqueda.

- **Por qué importa:** es una trampa fácil de pisar en código futuro (p. ej. un nuevo
  atajo o una vista que lea la variable).
- **Cómo arreglarlo:** separar `query_var` (nunca contiene el placeholder) de una
  etiqueta visual de placeholder dibujada aparte, o encapsular todo acceso en
  `SearchBar.get_query()/set_query()` y no exponer `search_var`.

### 3. `_download_service` se lee con `getattr` desde `options_panel`

**Verificado.** `src/youmudow/ui/widgets/options_panel.py`:

```python
ds = getattr(self._mw._controller, "_download_service", None)
if ds is not None:
    ds.set_max_concurrent(val)
```

`_download_service` es un atributo privado de `AppController` y no está en
`AppControllerProtocol` (decisión documentada en el ledger del PR #35).

- **Por qué importa:** si se renombra el atributo, la concurrencia deja de aplicarse en
  silencio.
- **Cómo arreglarlo:** exponer `AppController.set_max_concurrent(n: int)` público,
  añadirlo al protocolo y llamarlo directo.

### 4. El patrón *backing store + property read-only* de `MainWindow` es verboso

**Verificado.** Para satisfacer `MainWindowProtocol` (miembros `@property` read-only),
`MainWindow` guarda `_controller_impl`, `_search_bar_impl`, `_results_cards_impl`,
`_status_bar_impl`, `_history_panel_impl`, `_main_content_frame_impl`,
`_selected_video_impl`, `_notebook_widget`, `_detail_panel_widget`, `_tk_root`, y expone
una property por cada uno.

- **Por qué importa:** duplica la superficie de nombres y hace más difícil leer la clase.
- **Cómo arreglarlo:** un descriptor pequeño reutilizable (p. ej.
  `readonly_property(backing_name)`) o permitir en el protocolo atributos mutables allí
  donde la ventana realmente los reasigna.

### 5. `configure_widget()` no cubre todos los `configure()` de Tk

**Verificado.** `src/youmudow/ui/typed.py`: `configure_widget(widget, **options: str)`.
No admite `state` como `Literal` ni la forma posicional/dict, así que varios sitios
vuelven a `widget.configure(...)` directo.

- **Cómo arreglarlo:** añadir una sobrecarga que acepte `Mapping[str, Any]` y tipos
  `Literal` para `state`, o un helper `set_state(widget, enabled)`.

### 6. `write_atomic()` no hace `fsync` del directorio padre

**Verificado.** `src/youmudow/services/persistence.py`: hace `flush` + `os.fsync` del
fichero y `os.replace`, pero no sincroniza el directorio que contiene el rename.

- **Por qué importa:** en un corte de energía justo tras el rename, el directorio puede
  no estar persistido. Riesgo bajo, pero es exactamente el tipo de fallo que esta
  función existe para evitar.
- **Cómo arreglarlo:** abrir el directorio (`os.open(path.parent, os.O_DIRECTORY)`) y
  `os.fsync` tras el `os.replace` (con `try/except` para plataformas sin `O_DIRECTORY`).

### 7. Cobertura por debajo del objetivo que se fijó el plan (86,6 % vs ≥87 %)

**Verificado.** La cobertura quedó en ~86,6 % en el PR #35 (86,91 % en `main` antes).
Supera el umbral duro del proyecto (`fail_under = 70`) y el baseline, pero no el ≥87 %
aspiracional del plan.

- **Cómo arreglarlo:** `PYTHONPATH=src python3 -m pytest --cov=youmudow --cov-report=term-missing`
  y cubrir las ramas con más líneas sin ejecutar (normalmente manejo de errores de
  `ThumbnailLoader`, `OptionsPanel` y `window`).

---

## P3 — UX y pulido

### 1. El desplegable de historial no se maneja con teclado

**Verificado.** `src/youmudow/ui/widgets/components/search_entry.py` enlaza en el
`Listbox` `Double-Button-1`, `Return` y `FocusOut`, pero no `Up`/`Down`/`Escape` dentro
de la lista.

- **Qué falta:** bajar/seleccionar con flechas y cerrar con `Escape` sin ratón.
- **Dónde:** `_ensure_history_listbox()`.
- **Cómo:** enlazar `<Up>`/`<Down>` para mover `selection_clear`/`selection_set` y
  `<Escape>` a `close_history()`.

### 2. No hay botón visible para limpiar la búsqueda

Hoy existe `Ctrl+N` (que ya limpia el componente y cierra el desplegable tras el fix
`fbdffb8`), pero no un control visible en la barra. Un botón "×" dentro de `SearchEntry`
sería descubrible para quien no conoce atajos.

### 3. No hay forma de vaciar el caché de miniaturas

**Verificado.** `ThumbnailCache` (`src/youmudow/services/thumbnail_cache.py`) está
acotado por número de entradas (`max_entries=200`) y borra el fichero del LRU al
expulsar, pero no hay acción de usuario ni comando para vaciarlo, ni un tope en bytes.

- **Cómo:** añadir "Clear thumbnail cache" al menú (junto a las acciones de
  mantenimiento) y, opcionalmente, un tope de tamaño total.

### 4. Miniaturas sin reintento

Si la descarga de una miniatura falla (red, 404), la tarjeta se queda sin imagen hasta
que se vuelve a buscar. Un reintento manual (clic derecho → "Retry thumbnail") o
automático con backoff sería suficiente.

### 5. Estados de error poco explícitos en las tarjetas

Las tarjetas muestran título/uploader/duración; un fallo de metadatos deja campos
vacíos sin explicación. Valorar un estado por tarjeta ("metadata unavailable").

---

## P4 — Proceso y herramientas

### 1. La rama `feature/ui-typing-and-wiring` sigue existiendo

Se mantuvo a propósito como punto de vuelta atrás. Cuando ya no haga falta:

```bash
git branch -d feature/ui-typing-and-wiring
git push origin --delete feature/ui-typing-and-wiring
```

### 2. El workflow de release no se ha probado de punta a punta tras el tipado

El release `v1.3.0` salió antes del PR #35. Conviene publicar la siguiente versión
(p. ej. `v1.4.0`) y comprobar que `release.yml` construye el ejecutable con el nuevo
`pyproject.toml` (sin el override de mypy) y con Pillow 12.

### 3. Falta un paso de "entorno limpio" documentado

`docs/contributing.md` debería indicar crear un venv e instalar
`pip install -e ".[dev]"` para que local case con CI (ver P1.3).

---

## Apéndice — Cómo reproducir las comprobaciones

```bash
# Suite + cobertura
PYTHONPATH=src python3 -m pytest --cov=youmudow --cov-report=term-missing

# Tipos (estricto en toda la UI)
PYTHONPATH=src python3 -m mypy

# Lint y formato
ruff check src/ tests/
ruff format --check src/ tests/

# Arranque real (necesita X)
PYTHONPATH=src python3 scripts/smoke_boot.py
```
