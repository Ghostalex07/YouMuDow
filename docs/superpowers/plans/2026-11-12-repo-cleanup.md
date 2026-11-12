# Plan — limpieza y reestructuración de YouMuDow

Diseño: `docs/superpowers/specs/2026-11-12-repo-cleanup-design.md`
Regla: un commit por etapa; gates obligatorios al final de cada una
(`ruff check src/ tests/`, `ruff format --check src/ tests/`, `PYTHONPATH=src python3 -m mypy`,
`PYTHONPATH=src python3 -m pytest`).

## Etapa 1 — Higiene del repositorio

- Borrar `ai.txt`, `robots.txt`, `build/`, `dist/`, `src/youmudow.egg-info/`,
  `UNKNOWN.egg-info/`.
- Crear `src/youmudow/py.typed` y declararlo como package-data.
- `CHANGELOG.md`: entradas de limpieza bajo `[Unreleased]`.
- Comprobar que ningún fichero del repo referencia lo borrado.

## Etapa 2 — Adaptador yt-dlp

- Extraer `ytdlp_args.py`, `ytdlp_parsing.py`, `ytdlp_process.py`, `ytdlp_files.py`.
- `ytdlp_adapter.py` queda como orquestación + reexportes compatibles.
- Reescribir los tests de métodos privados contra las funciones nuevas.

## Etapa 3 — Servicio de descargas

- Extraer `download_events.py`, `download_queue.py`, `download_worker.py`.
- `download_service.py` mantiene reexportes; `app/state.py` importa de `download_queue`.
- Actualizar `services/__init__.py` si aporta claridad.

## Etapa 4 — Panel de detalle

- Extraer `options_panel.py` y `queue_panel.py`.
- `detail_panel.py` queda en ficha + miniatura + composición.
- Actualizar `window.py` (llamadas internas) y los tests que tocan atributos privados.

## Etapa 5 — Ventana principal

- Extraer `menubar.py`, `startup_checks.py`, `actions.py`.
- Mover el repintado recursivo a `ui/styles/theme_apply.py` con tabla de reglas.
- `window.py` queda como composición y wiring.
- Añadir tests unitarios de `theme_apply` (sin ventana).

## Etapa 6 — Cierre

- Tests nuevos para los módulos extraídos (objetivo: subir UI a >= 75%).
- `docs/architecture.md` y `README.md` sincronizados con la estructura real.
- Evaluar quitar `ignore_errors` de `youmudow.ui.*` en `mypy`; si no es viable,
  dejar la excepción justificada.
- Gates completos + `git diff --stat` revisado.

## Criterios de aceptación

1. Ningún módulo de `src/` supera ~600 líneas ni una clase ~450. `window.py`
   (570) y `options_panel.py` (565) se aceptan: son raíces de composición con
   métodos pequeños, y seguir partiéndolas añadiría indirección sin ganancia.
2. Los imports públicos existentes siguen funcionando (fachadas).
3. 0 errores de ruff/mypy; suite completa en verde; cobertura >= 81%.
4. Comportamiento observable idéntico (misma UI, mismo `config.json`).
