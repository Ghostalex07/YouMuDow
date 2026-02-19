# 🛠️ YouMuDow (YouTube Music Downloader)

**YouMuDow** is a high-performance desktop GUI designed for efficient YouTube media management. Built with a **"function over form"** philosophy, it provides full transparency into the download process by capturing real-time terminal output to ensure maximum reliability and easy debugging.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)

---

## 🚀 Key Features

- ⚡ **High-Speed Search**  
  Uses optimized flags like `--flat-playlist` to fetch metadata instantly without the overhead of full format analysis.

- 🧵 **Asynchronous Work Queue**  
  Add multiple tracks to a queue and let the program process them sequentially in the background.

- 📡 **Real-Time Debug Logs**  
  Integrated console that pipes `stdout` and `stderr` directly from `yt-dlp`, allowing you to monitor progress and detect network errors (like HTTP 403) immediately.

- 🛡️ **Anti-Freeze Architecture**  
  Powered by Python's `threading` and `queue` modules to keep the UI responsive even during heavy download tasks.

- 🐧 **Linux-Optimized**  
  Designed to be lightweight and stable on Linux environments, avoiding common memory issues like `Segmentation Faults`.

- 🖥️ **Dual Display Mode**  
  Toggle between a clean **Normal Mode** for everyday use and an expanded **Debug Mode** for advanced technical monitoring.

---

## 📋 Prerequisites

Ensure you have the following dependencies installed:

### 🐧 Linux (Debian / Ubuntu / Mint)

```bash
sudo apt update
sudo apt install python3-tk ffmpeg
pip install yt-dlp
```

### 🪟 Windows

1. Install **Python 3.x**  
2. Install the core library:
   ```bash
   pip install yt-dlp
   ```
3. Ensure **ffmpeg** is installed and added to your **System PATH**

---

## 🛠️ Installation & Usage

### 1️⃣ Clone the repository

```bash
git clone https://github.com/Ghostalex07/YouMuDow.git
```

### 2️⃣ Navigate to the project directory

```bash
cd YouMuDow
```

### 3️⃣ Run the application

```bash
python3 main.py
```

---

## 📖 How to Use

1. 🔎 **Search**  
   Enter a song name or paste a YouTube URL and click **SEARCH**.

2. 📑 **Select**  
   Click on the desired result in the results table.

3. 🎵 **Choose Format**  
   Select between:
   - MP3 (Audio)
   - MP4 (Video)

4. 📂 **Add to Queue**  
   Click **ADD TO QUEUE** and select your destination folder.

5. 🧪 **Debug (Optional)**  
   If you encounter any issues, click **SHOW DEBUG** to view real-time terminal output.

---

## 🛠️ Technical Details

YouMuDow works as a lightweight wrapper around **yt-dlp**, managing subprocesses to prevent blocking the main GUI event loop.

- **Search Engine**  
  Queries YouTube using the `ytsearch` extractor.

- **Process Handling**  
  Uses `subprocess.Popen` with pipe redirection to capture live logs.

- **Threading Model**  
  Dedicated threads for:
  - Search operations
  - Download worker queue  

  Ensures near 0% UI freeze rate.

---

## 🏗️ Architecture Overview

```
GUI (Tkinter)
   │
   ├── Search Thread → yt-dlp (metadata only)
   │
   └── Download Worker Thread
           └── subprocess.Popen → yt-dlp (download + logs)
```
