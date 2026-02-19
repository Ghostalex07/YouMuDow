# 🛠️ Spartan Downloader Pro

**Spartan Downloader Pro** is a high-performance desktop GUI for managing YouTube downloads. Built with a "function over form" philosophy, it provides a transparent look into the download process, capturing real-time terminal output to ensure maximum reliability and easy debugging.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)

## 🚀 Key Features

* **High-Speed Search:** Uses `--flat-playlist` to fetch metadata instantly without the overhead of full format analysis.
* **Asynchronous Work Queue:** Add multiple tracks to a queue and let the program process them sequentially in the background.
* **Real-Time Debug Logs:** Integrated console that pipes `stdout` and `stderr` directly from `yt-dlp`, allowing you to monitor progress and identify network errors (like HTTP 403) immediately.
* **Anti-Freeze Architecture:** Powered by `threading` and `queue` modules to keep the UI responsive during heavy tasks.
* **Linux-Optimized:** Designed to prevent common memory issues like `Segmentation Faults` by avoiding unstable external image libraries.

## 📋 Prerequisites

Ensure you have the following dependencies installed:

### Linux (Debian/Ubuntu)
```bash
sudo apt update
sudo apt install python3-tk ffmpeg
pip install yt-dlp
