# YouMuDow — limpieza y reestructuración (diseño)

Fecha: 2026-11-12
Estado: aprobado por el usuario ("haz lo que creas que es mejor... hazlo como en el 2 y borra esas cosas")

## Intención

El repositorio funciona (556 tests, 81,5% de cobertura, ruff/mypy limpios) pero tiene
cuatro god-objects, duplicación entre capas y restos que no pertenecen al proyecto.
El objetivo es dejar una base mantenible **sin cambiar el comportamiento observable
de la aplicación**, con la suite existente como red de seguridad.

## Objetivos

1. Partir `ui/window.py`, `ui/widgets/detail_panel.py`, `adapters/ytdlp_adapter.py`
   y `services/download_service.py` en módulos con una sola responsabilidad.
2. Eliminar duplicación y acoplamiento por atributos privados entre capas.
3. Sustituir la recursión de repintado de tema por una tabla de reglas testeable.
4. Borrar restos: `ai.txt`, `robots.txt` y artefactos locales (`build/`, `dist/`,
   `*.egg-info/`, `UNKNOWN.egg-info/`).
5. Añadir al `[Unreleased]` de `CHANGELOG.md` (que sí corresponde a trabajo
   posterior a v1.2.0, fechado 2026-09-30) la entrada de esta limpieza, y
   actualizar la documentación de arquitectura.
6. Añadir `py.typed` y ampliar la cobertura de la capa UI, hoy en 53–65%.

## No objetivos

- Cambios de funcionalidad, de UI visible o de formato de configuración/historial.
- Migrar de Tkinter.
- Reescribir la app como paquete con otro `import` raíz.

## Anti-objetivos

- Refactor que rompa la API pública de `YtdlpAdapter`, `DownloadService`,
  `DetailPanel`, `StateManager` o el `config.json` existente.
- "Limpiar" borrando tests que fallan en lugar de arreglar la causa.

## Restricciones

- Python >= 3.10, Tkinter, PyInstaller (los entry points no cambian).
- `ruff check`, `ruff format --check`, `mypy` y `pytest` deben seguir en verde
  en cada etapa; un commit por etapa.
- Los tests actuales usan atributos privados de los god-objects: al mover código,
  esos tests se reescriben contra las nuevas unidades puras, no se duplican.

## Enfoques considerados

1. **Limpieza superficial** (borrar restos y arreglar docs): barata, deja el problema
   estructural intacto. Descartada.
2. **Reestructuración por módulos con fachada** (elegida): extraer unidades puras y
   dejar los módulos actuales como fachadas finas que preservan imports y API.
   Permite avanzar por etapas verificables y mantener compatibilidad.
3. **Reescritura total (MVVM + Tkinter tipado estricto)**: máxima calidad teórica,
   riesgo alto y sin tests de UI suficientes para sostenerla. Descartada por riesgo.

## Diseño

### adapters

```
ytdlp_adapter.py   YtdlpAdapter (orquestación: search, metadata, playlist, download)
ytdlp_args.py      funciones puras: args de CLI, selectores de formato/calidad
ytdlp_parsing.py   funciones puras: progreso, JSON, flat playlist, duración, errores
ytdlp_process.py   ejecución de subprocesos, timeouts, señales al process group
```

`ytdlp_adapter.py` reexporta `YtdlpConfig`, `ProgressInfo`, `parse_yt_dlp_error` y
`parse_cookie_error` para no romper `adapters/__init__.py` ni consumidores.

### services

```
download_events.py  DownloadEventType, DownloadProgress, DownloadEvent
download_queue.py   DownloadQueue + is_same_video/find_video_index/find_entry_index
download_worker.py  DownloadWorker
download_service.py DownloadService (orquestación del pool y callbacks)
```

`download_service.py` reexporta los símbolos movidos (`app/state.py` y `services/__init__.py`
los importan desde ahí).

### ui

```
window.py         MainWindow: composición y wiring (~350 líneas)
menubar.py        construcción del menú a partir de callbacks
startup_checks.py chequeos de arranque (clipboard, yt-dlp, entorno YouTube)
actions.py        exportar logs, abrir carpeta, acerca de, actualizar/repair yt-dlp
styles/theme_apply.py  tabla de reglas de repintado por tipo de widget
widgets/detail_panel.py  ficha del vídeo + miniatura
widgets/options_panel.py formato, calidad, subtítulos, cookies, navegador, avanzado
widgets/queue_panel.py   árbol de cola y menú contextual
```

`DetailPanel` conserva los métodos que usa `MainWindow`, delegando en los sub-paneles;
el estado interno (`_format_var`, `_queue_tree`, ...) pasa a los sub-paneles y los
tests se actualizan a la nueva ruta.

### Limpieza de repositorio

- Borrar `ai.txt` y `robots.txt` (decidido por el usuario).
- Borrar `build/`, `dist/`, `src/youmudow.egg-info/`, `UNKNOWN.egg-info/` (artefactos
  locales; ya están en `.gitignore`).
- `CHANGELOG.md`: convertir el `[Unreleased]` actual en `[1.2.0]` y abrir un
  `[Unreleased]` nuevo para esta limpieza.
- `pyproject.toml`: añadir `py.typed` al paquete.
- `docs/architecture.md`: reflejar la nueva estructura de módulos.

## Lo que queda a criterio del implementador

Nombres exactos de helpers privados, orden interno de los métodos y si `mypy` puede
dejar de ignorar `youmudow.ui.*` por completo (se intentará; si el ruido de Tkinter
es alto, se mantiene la excepción documentada).
