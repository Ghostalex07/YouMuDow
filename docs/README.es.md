# YouMuDow — guía rápida en español

Descargador de audio y vídeo con interfaz de escritorio (Tkinter) y CLI, sobre
`yt-dlp`. La app completa está traducida al español: si tu sistema está en
español, arranca así sola, y puedes cambiarlo en **Ver → Idioma**.

## Instalar

**Binario** (lo más rápido): descarga el zip de la última release para tu
sistema, descomprímelo y ejecuta `YouMuDow`. Necesita `ffmpeg` en el PATH.

**Desde el código**:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/youmudow          # interfaz gráfica
.venv/bin/youmudow-cli --help
```

## Lo básico

1. Escribe un nombre y pulsa Enter, o pega un enlace. También puedes **arrastrar
   un enlace** del navegador sobre la ventana.
2. Elige formato y calidad, o un preset (**Music 320**, **Video 1080**,
   **Archive FLAC**). El panel de detalle enseña duración y tamaño estimado.
3. **Download Now** descarga al momento; **Add to queue** lo deja en cola.
4. **F1** abre la guía dentro de la app.

## Playlists y canales

Pega una playlist, un `@handle` o una URL de canal (con o sin `/videos`,
`/shorts`, `/streams`). Carga la primera página y **Load more** añade la
siguiente. **Add All** encola todo lo cargado; **Add New** solo lo que no está
en tu biblioteca.

## Cola

Pausa y reanudación, reordenar arrastrando filas, `Delete` para quitar la
seleccionada y `Ctrl+Shift+S` para arrancar. Las descargas fallidas se
reintentan solas y se agrupan por causa, con **Retry failed** para relanzarlas
todas. Si cierras la app, la cola se recupera al volver.

## Biblioteca

Pestaña **Library**: total descargado, reparto por formato, canal y mes,
buscador por título/canal/ruta, comprobación de ficheros perdidos,
**Scan folder** e **Import files** para adoptar descargas antiguas, y
**Find duplicates** (mismo tamaño y duración, conserva la copia más reciente).

## Bandeja y apagado

**View → Keep Running in Tray** deja la cola viva al cerrar la ventana (en Linux
necesita un host de notificaciones). **Queue → Shut down when finished** apaga
el equipo 60 s después de terminar la cola; `Escape` lo cancela y no apaga si
algo falló.

## Servidor sin ventana

```bash
youmudow-cli serve --port 8765 --token SECRETO --output ~/Música
curl -H "Authorization: Bearer SECRETO" \
     -d '{"url":"https://youtu.be/xxxx","format":"mp3"}' \
     http://127.0.0.1:8765/api/downloads
```

Rutas: `POST /api/downloads`, `POST /api/downloads/batch`, `GET /api/downloads`,
`POST /api/queue/pause|resume`, `DELETE /api/queue/{id}`, `GET /api/health` y
`GET /api/events` (SSE). Solo escucha en localhost salvo que pases `--token`.

## Lotes desde la terminal

```bash
youmudow-cli download --from-file canciones.txt --format mp3 --polite --json
youmudow-cli history --limit 20
youmudow-cli queue
```

`--from-file` acepta una URL por línea o un CSV, salta lo que ya está en la
biblioteca y `--json` devuelve `requested/downloaded/skipped/failed`.

## Ficheros

| Qué | Linux | Windows |
|-----|-------|---------|
| Ajustes | `~/.config/youmudow/config.json` | `%APPDATA%\\YouMuDow\\config.json` |
| Biblioteca | `~/.config/youmudow/youmudow.db` | `%APPDATA%\\YouMuDow\\youmudow.db` |
| Registro | `~/.config/youmudow/youmudow.log` | `%APPDATA%\\YouMuDow\\youmudow.log` |

**Modo portable**: con `YMD_PORTABLE=1` o un fichero `youmudow.portable` junto
al ejecutable, todo (ajustes, base de datos, caché y registro) se guarda en
`data/` al lado del binario.

## Si algo va mal

- **Ayuda → Export Diagnostics...** genera un informe con versión, ffmpeg,
  entorno y configuración redactada. Es lo primero que conviene mirar.
- Si YouTube pide iniciar sesión, configura cookies en las opciones o usa
  `--cookies cookies.txt` en la CLI.
- Los binarios no están firmados: macOS y Windows muestran un aviso la primera
  vez.
