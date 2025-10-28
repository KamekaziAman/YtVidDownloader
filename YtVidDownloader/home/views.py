from django.shortcuts import render
from django.contrib import messages
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.http import FileResponse
import os
import tempfile

try:
    import yt_dlp  # type: ignore
except Exception:
    yt_dlp = None

# Create your views here.


def home(request):
    context = {}
    if request.method == "POST":
        url = request.POST.get("url", "").strip()
        quality_key = request.POST.get("quality", "4").strip()
        validator = URLValidator()
        try:
            validator(url)
            context["submitted_url"] = url
            context["quality"] = quality_key

            if yt_dlp is None:
                messages.error(request, "yt-dlp is not installed in the environment.")
                return render(request, "home/home.html", context)

            # Optional: append FFmpeg to PATH on Windows if present
            ffmpeg_path = r"C:\ffmpeg\bin"
            if os.name == "nt" and os.path.isdir(ffmpeg_path):
                os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + ffmpeg_path

            # Map requested quality to yt-dlp format string
            quality_map = {
                "1": "bestvideo[height<=2160]+bestaudio/best",
                "2": "bestvideo[height<=1440]+bestaudio/best",
                "3": "bestvideo[height<=1080]+bestaudio/best",
                "4": "bestvideo[height<=720]+bestaudio/best",
                "5": "bestvideo[height<=480]+bestaudio/best",
                "6": "bestvideo[height<=360]+bestaudio/best",
                "7": "bestvideo[height<=240]+bestaudio/best",
                "8": "bestvideo[height<=144]+bestaudio/best",
                "9": "bestaudio/best",
            }
            fmt = quality_map.get(quality_key, quality_map["4"])  # default 720p

            target_dir = tempfile.mkdtemp(prefix="ytdl_")
            downloaded_path = {"path": None}

            def hook(d):
                if d.get("status") == "finished":
                    downloaded_path["path"] = d.get("filename")

            ydl_opts = {
                "format": fmt,
                "outtmpl": os.path.join(target_dir, "%(title)s.%(ext)s"),
                "merge_output_format": "mp4",
                "progress_hooks": [hook],
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                file_path = downloaded_path["path"]
                if not file_path or not os.path.exists(file_path):
                    # Fallback: pick newest file in target_dir
                    candidates = sorted(
                        [
                            os.path.join(target_dir, f)
                            for f in os.listdir(target_dir)
                        ],
                        key=lambda p: os.path.getmtime(p),
                        reverse=True,
                    )
                    file_path = candidates[0] if candidates else None

                if not file_path or not os.path.isfile(file_path):
                    messages.error(request, "Download failed. Try a different URL.")
                    return render(request, "home/home.html", context)

                filename = os.path.basename(file_path)
                return FileResponse(open(file_path, "rb"), as_attachment=True, filename=filename)
            except yt_dlp.utils.DownloadError as e:  # type: ignore
                messages.error(request, f"Download error: {e}")
            except Exception as e:
                messages.error(request, f"Unexpected error: {e}")
        except ValidationError:
            messages.error(request, "Please enter a valid URL.")
            context["submitted_url"] = url
    return render(request, "home/home.html", context)
