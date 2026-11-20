"""Library tab: totals, breakdowns and integrity tools."""

import tkinter as tk
from collections.abc import Callable

from youmudow.domain.sizes import format_size
from youmudow.i18n import t
from youmudow.services.library_store import LibraryStats
from youmudow.ui.styles.constants import FONT, SPACING, _c


class LibraryPanel(tk.Frame):
    """Read-only summary over the SQLite library plus two maintenance actions."""

    def __init__(
        self,
        parent: tk.Widget,
        stats_provider: Callable[[], LibraryStats],
        on_check: Callable[[], list[str]],
        on_requeue: Callable[[], int],
        on_open_folder: Callable[[], None],
        on_scan: Callable[[], list] | None = None,
        on_import: Callable[[list], int] | None = None,
    ) -> None:
        super().__init__(parent, bg=_c("bg"))
        self._stats_provider = stats_provider
        self._on_check = on_check
        self._on_requeue = on_requeue
        self._missing: list[str] = []
        self._on_scan = on_scan
        self._on_import = on_import
        self._scanned: list = []
        self._build(on_open_folder)

    def _build(self, on_open_folder: Callable[[], None]) -> None:
        header = tk.Frame(self, bg=_c("bg"))
        header.pack(fill="x", padx=SPACING["md"], pady=(SPACING["md"], SPACING["sm"]))
        tk.Label(
            header,
            text=t("Library"),
            bg=_c("bg"),
            fg=_c("text"),
            font=FONT["h1"],
        ).pack(side="left")

        self._summary = tk.Label(
            header,
            text="",
            bg=_c("bg"),
            fg=_c("text_secondary"),
            font=FONT["body"],
        )
        self._summary.pack(side="left", padx=SPACING["md"])

        buttons = tk.Frame(header, bg=_c("bg"))
        buttons.pack(side="right")
        for label, command in (
            (t("Refresh"), self.refresh),
            (t("Check library"), self._check),
            (t("Re-download missing"), self._requeue),
            (t("Open folder"), on_open_folder),
            (t("Scan folder"), self._scan),
            (t("Import files"), self._import_files),
        ):
            tk.Button(
                buttons,
                text=label,
                command=command,
                bg=_c("surface"),
                fg=_c("text"),
                activebackground=_c("hover"),
                activeforeground=_c("text"),
                relief="flat",
                bd=0,
                font=FONT["label"],
                padx=SPACING["sm"],
                pady=4,
            ).pack(side="left", padx=(0, SPACING["xs"]))

        self._body = tk.Text(
            self,
            bg=_c("surface"),
            fg=_c("text"),
            font=FONT["mono"],
            relief="flat",
            bd=0,
            height=18,
            wrap="word",
            padx=SPACING["md"],
            pady=SPACING["sm"],
        )
        self._body.pack(fill="both", expand=True, padx=SPACING["md"], pady=(0, SPACING["md"]))
        self._body.configure(state="disabled")

    def _scan(self) -> None:
        self._scanned = list(self._on_scan()) if self._on_scan is not None else []
        self.refresh()

    def _import_files(self) -> None:
        if not self._scanned or self._on_import is None:
            return
        self._on_import(self._scanned)
        self._scanned = []
        self.refresh()

    # -- rendering -------------------------------------------------------

    def refresh(self) -> None:
        stats = self._stats_provider()
        self._summary.configure(
            text=t(
                "{count} downloads · {size}",
                count=stats.get("count", 0),
                size=format_size(int(stats.get("total_bytes", 0))),
            )
        )
        lines: list[str] = []
        lines.extend(self._section(t("By format"), stats.get("by_format", [])))
        lines.extend(self._section(t("By channel"), stats.get("by_uploader", [])))
        lines.extend(self._section(t("By month"), stats.get("by_month", [])))
        if self._scanned:
            lines.append("")
            lines.append(
                t("{count} files in the folder are not in the library", count=len(self._scanned))
            )
            lines.extend(f"  · {item.path.name}" for item in self._scanned[:10])
        if self._missing:
            lines.append("")
            lines.append(t("Missing files: {count}", count=len(self._missing)))
            lines.extend(f"  · {name}" for name in self._missing[:10])
        self._body.configure(state="normal")
        self._body.delete("1.0", "end")
        self._body.insert("1.0", "\n".join(lines) or t("Nothing downloaded yet."))
        self._body.configure(state="disabled")

    @staticmethod
    def _section(title: str, rows: list[tuple[str, int, int]]) -> list[str]:
        if not rows:
            return []
        lines = [title]
        for name, count, size in rows:
            lines.append(f"  {name or '-'}  ·  {count}  ·  {format_size(size)}")
        lines.append("")
        return lines

    # -- actions ---------------------------------------------------------

    def _check(self) -> None:
        self._missing = self._on_check()
        self.refresh()

    def _requeue(self) -> None:
        self._on_requeue()
        self._missing = []
        self.refresh()
