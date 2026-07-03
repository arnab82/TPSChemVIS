"""Install and launch the desktop Jmol application.

Jmol is distributed as a cross-platform Java application. The installer here
downloads the official binary archive, extracts Jmol.jar into the user's
asbuilder config directory, and launches it with the local Java runtime.
"""

from __future__ import annotations

import html
import os
import platform
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from asbuilder import config as cfg

Progress = Callable[[str], None]

_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_GZIP_SIGNATURE = b"\x1f\x8b"
_SOURCEFORGE_DIRECT_RE = re.compile(
    r"https?://(?:downloads\.sourceforge\.net|[^\"'<>\s]+\.dl\.sourceforge\.net)/[^\"'<>\s]+",
    re.IGNORECASE,
)
_SOURCEFORGE_FILE_RE = re.compile(
    r"href=[\"'](?P<href>/projects/jmol/files/[^\"']+\?download|/projects/jmol/files/[^\"']+/download)[\"']",
    re.IGNORECASE,
)


class JmolError(RuntimeError):
    """Raised when Jmol cannot be installed or launched."""


def jmol_jar_path() -> Path:
    return cfg.jmol_jar()


def is_jmol_installed() -> bool:
    return jmol_jar_path().exists()


def find_java() -> str | None:
    java = shutil.which("java")
    if java:
        return java

    if platform.system() == "Darwin":
        java_home = shutil.which("/usr/libexec/java_home")
        if java_home:
            try:
                result = subprocess.run(
                    [java_home],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
            except Exception:
                result = None
            if result is not None and result.returncode == 0:
                candidate = Path(result.stdout.strip()) / "bin" / "java"
                if candidate.exists():
                    return str(candidate)
    return None


def desktop_label() -> str:
    system = platform.system() or "Unknown"
    machine = platform.machine() or "unknown"
    return f"{system} {machine}"


def _sourceforge_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": "TPSChemVIS/0.1 Jmol installer",
            "Accept": (
                "application/zip, application/gzip, application/x-gzip, "
                "application/octet-stream, text/html;q=0.8, */*;q=0.5"
            ),
        },
    )


def _archive_kind(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            head = handle.read(4)
    except OSError:
        return None
    if head in _ZIP_SIGNATURES:
        return "zip"
    if head.startswith(_GZIP_SIGNATURE):
        return "tar.gz"
    return None


def _download_once(url: str, destination: Path, emit: Progress) -> tuple[str, str]:
    with urllib.request.urlopen(_sourceforge_request(url), timeout=90) as response:
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "unknown")
        if final_url != url:
            emit(f"Resolved to {final_url}")
        with destination.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                emit(f"Downloaded {destination.stat().st_size / (1024 * 1024):.1f} MB")
    return final_url, content_type


def _clean_sourceforge_url(url: str) -> str:
    url = html.unescape(url).replace("\\/", "/").strip()
    url = url.rstrip(".,);]")
    return urllib.parse.urljoin("https://sourceforge.net", url)


def _extract_sourceforge_download_url(page_bytes: bytes, base_url: str) -> str | None:
    text = page_bytes[: 2 * 1024 * 1024].decode("utf-8", errors="ignore")
    text = html.unescape(text).replace("\\/", "/")

    candidates: list[str] = []
    meta = re.search(r"url\s*=\s*(https?://[^\"'<>\s]+)", text, re.IGNORECASE)
    if meta:
        candidates.append(meta.group(1))
    candidates.extend(match.group(0) for match in _SOURCEFORGE_DIRECT_RE.finditer(text))
    candidates.extend(match.group("href") for match in _SOURCEFORGE_FILE_RE.finditer(text))

    for candidate in candidates:
        url = _clean_sourceforge_url(candidate)
        if url == base_url:
            continue
        if "sourceforge.net" in urllib.parse.urlparse(url).netloc and (
            "download" in url or ".zip" in url.lower() or ".tar.gz" in url.lower() or ".tgz" in url.lower()
        ):
            return url
    return None


def _download_jmol_archive(download_url: str, archive_path: Path, emit: Progress) -> str:
    url = download_url
    seen: set[str] = set()
    for attempt in range(1, 5):
        if url in seen:
            break
        seen.add(url)
        emit(f"Downloading Jmol from {url}")
        final_url, content_type = _download_once(url, archive_path, emit)
        kind = _archive_kind(archive_path)
        if kind is not None:
            return kind

        page_bytes = archive_path.read_bytes()
        next_url = _extract_sourceforge_download_url(page_bytes, final_url)
        if next_url is not None and next_url not in seen:
            emit("SourceForge returned a mirror page; following the direct download link.")
            url = next_url
            continue

        preview = page_bytes[:120].decode("utf-8", errors="replace").replace("\n", " ").strip()
        raise JmolError(
            "SourceForge did not return a supported Jmol archive "
            f"(content-type={content_type}, url={final_url}, attempt={attempt}). "
            f"Response started with: {preview!r}"
        )
    raise JmolError("SourceForge did not provide a supported Jmol archive after following redirects.")


def _extract_jmol_jar(archive_path: Path, archive_kind: str, destination: Path) -> None:
    if archive_kind == "zip":
        try:
            with zipfile.ZipFile(archive_path) as zf:
                jar_members = [name for name in zf.namelist() if name.endswith("Jmol.jar")]
                if not jar_members:
                    raise JmolError("Downloaded Jmol zip did not contain Jmol.jar")
                jar_member = sorted(jar_members, key=len)[0]
                with zf.open(jar_member) as src, destination.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        except zipfile.BadZipFile as exc:
            raise JmolError("Downloaded Jmol file was not a valid zip archive.") from exc
        return

    if archive_kind == "tar.gz":
        try:
            with tarfile.open(archive_path, mode="r:gz") as tf:
                jar_members = [member for member in tf.getmembers() if member.name.endswith("Jmol.jar")]
                if not jar_members:
                    raise JmolError("Downloaded Jmol tar.gz did not contain Jmol.jar")
                jar_member = sorted(jar_members, key=lambda member: len(member.name))[0]
                src = tf.extractfile(jar_member)
                if src is None:
                    raise JmolError("Could not read Jmol.jar from downloaded tar.gz")
                with src, destination.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        except tarfile.TarError as exc:
            raise JmolError("Downloaded Jmol file was not a valid tar.gz archive.") from exc
        return

    raise JmolError(f"Unsupported Jmol archive type: {archive_kind}")


def install_jmol(
    download_url: str = cfg.JMOL_LATEST_URL,
    progress: Progress | None = None,
) -> Path:
    """Download the latest Jmol binary archive and extract Jmol.jar.

    The same Jmol.jar is used on macOS, Windows, and Linux. We still report the
    desktop platform because launch behavior and Java availability are platform
    specific in compiled GUI builds.
    """
    emit = progress or (lambda _msg: None)
    cfg.JMOL_DIR.mkdir(parents=True, exist_ok=True)

    emit(f"Detected desktop: {desktop_label()}")
    emit(f"Downloading Jmol from {download_url}")
    with tempfile.TemporaryDirectory(prefix="asbuilder_jmol_") as tmpdir:
        tmp = Path(tmpdir)
        archive_path = tmp / "jmol-latest.download"
        archive_kind = _download_jmol_archive(download_url, archive_path, emit)

        emit(f"Extracting Jmol.jar from {archive_kind}")
        _extract_jmol_jar(archive_path, archive_kind, jmol_jar_path())

    java = find_java()
    if java:
        cfg.set_value("jmol_command", java)
        emit(f"Java runtime: {java}")
    else:
        emit("Java runtime not found. Install Java, then Jmol can be launched.")
    emit(f"Installed {jmol_jar_path()}")
    return jmol_jar_path()


def _command_parts(command: str) -> list[str]:
    if Path(command).exists():
        return [command]
    parts = shlex.split(command, posix=(platform.system() != "Windows"))
    return parts or [command]


def launch_jmol(molden_path: str | Path | None = None) -> None:
    jar = jmol_jar_path()
    if not jar.exists():
        raise JmolError("Jmol is not installed yet. Use Install Jmol first.")

    java = cfg.jmol_command()
    if java == "jmol":
        java = find_java() or java
    args = [*_command_parts(java), "-jar", str(jar)]
    if molden_path is not None:
        args.append(str(molden_path))

    popen_kwargs: dict = {}
    if platform.system() == "Windows":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **popen_kwargs)
    except FileNotFoundError as exc:
        raise JmolError(
            "Could not find Java. Install a Java runtime, or configure the Jmol command."
        ) from exc
    except OSError as exc:
        if os.name == "posix" and exc.errno == 8:
            raise JmolError("Could not launch Jmol. Check that Java can run Jmol.jar.") from exc
        raise
