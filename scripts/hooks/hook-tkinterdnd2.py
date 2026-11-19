"""Bundle the TkDND extension that ``tkinterdnd2`` loads at runtime."""

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("tkinterdnd2")
