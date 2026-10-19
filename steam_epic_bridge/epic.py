from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Callable

from steam_epic_bridge.config import Settings
from steam_epic_bridge.models import EpicGame


class EpicError(RuntimeError):
    pass


class EpicAuthError(EpicError):
    pass


class EpicLibraryError(EpicError):
    pass


EPIC_AUTH_REDIRECT_URL = (
    "https://www.epicgames.com/id/login?redirectUrl="
    "https%3A%2F%2Fwww.epicgames.com%2Fid%2Fapi%2Fredirect"
    "%3FclientId%3D34a02cf8f4414e29b15921876da36f9a%26responseType%3Dcode"
)


def _console_python_exe() -> str:
    import sys

    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        console_candidate = exe.with_name("python.exe")
        if console_candidate.exists():
            return str(console_candidate)
    return str(exe)


LEGENDARY_MODULE = "python -m legendary"  # valor de legendary_bin: usar o pacote instalado/embutido


def legendary_argv(settings: Settings) -> list[str]:
    """Prefixo de comando que executa o Legendary, sem os argumentos de cada ação.

    - Executável configurado/encontrado: ele mesmo.
    - Pacote Python (modo código-fonte): o interpretador atual + '-m legendary.cli'.
    - Executável empacotado (PyInstaller): sys.executable é o próprio app, não um
      interpretador; o Legendary embutido roda pelo subcomando oculto 'legendary-passthrough'.
    """
    import sys

    if settings.legendary_bin != LEGENDARY_MODULE:
        return [settings.legendary_bin]
    if getattr(sys, "frozen", False):
        return [sys.executable, "legendary-passthrough"]
    return [_console_python_exe(), "-m", "legendary.cli"]


def _legendary_cmd(settings: Settings, *args: str) -> list[str]:
    return [*legendary_argv(settings), *args]


def _run_legendary(settings: Settings, *args: str) -> subprocess.CompletedProcess[str]:
    command = _legendary_cmd(settings, *args)
    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
    except OSError as exc:
        raise EpicAuthError(
            f"Nao foi possivel executar o Legendary ({exc})."
        ) from exc


def get_account(settings: Settings) -> str | None:
    """Retorna o nome da conta Epic conectada ou None se não estiver autenticada."""
    try:
        result = _run_legendary(settings, "status", "--json")
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout)
        account = payload.get("account")
        if not account or account == "<not logged in>":
            return None
        return str(account)
    except Exception:
        return None


def ensure_authenticated(settings: Settings) -> str:
    result = _run_legendary(settings, "status", "--json")
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise EpicAuthError(
            "Conta Epic nao conectada no Legendary."
            + (f" Detalhe: {stderr}" if stderr else "")
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EpicAuthError("Nao foi possivel interpretar a resposta do Legendary.") from exc

    account = payload.get("account")
    if not account or account == "<not logged in>":
        raise EpicAuthError("Nenhuma conta Epic autenticada encontrada. Conecte sua conta nas Configuracoes.")
    return str(account)


def _extract_code_or_sid(raw: str) -> tuple[str, str]:
    """Extrai authorizationCode ou sid de uma string pura ou JSON colado pelo usuário."""
    text = raw.strip()
    if '"authorizationCode"' in text:
        match = re.search(r'"authorizationCode"\s*:\s*"([^"]+)"', text)
        if match:
            return "--code", match.group(1).strip()
    if '"sid"' in text:
        match = re.search(r'"sid"\s*:\s*"([^"]+)"', text)
        if match:
            return "--sid", match.group(1).strip()
    cleaned = text.strip('"{} \t\n\r')
    return "--code", cleaned


def login(settings: Settings, code: str | None = None, import_egl: bool = False) -> str:
    """Autentica no Legendary via importação do Epic Launcher (--import), código OAuth (--code) ou webview nativa."""
    args = ["auth"]
    if import_egl:
        args.append("--import")
    elif code:
        flag, extracted = _extract_code_or_sid(code)
        args.extend([flag, extracted])

    result = _run_legendary(settings, *args)
    if result.returncode != 0:
        raw = result.stderr.strip() or result.stdout.strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        detail = lines[-1] if lines else "Erro desconhecido"
        raise EpicAuthError(f"Falha ao conectar conta Epic: {detail}")

    return ensure_authenticated(settings)


def logout(settings: Settings) -> None:
    """Desconecta a conta Epic atual do Legendary."""
    _run_legendary(settings, "auth", "--delete")


def legendary_config_dir() -> Path:
    custom = os.getenv("LEGENDARY_CONFIG_PATH")
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".config" / "legendary"


def is_game_installed(app_name: str, cfg_dir: Path | None = None) -> tuple[bool, str | None]:
    """Verifica em O(1) no installed.json se o jogo está instalado e retorna (is_installed, install_path)."""
    base = cfg_dir or legendary_config_dir()
    installed_file = base / "installed.json"
    if not installed_file.exists():
        return False, None
    try:
        data = json.loads(installed_file.read_text(encoding="utf-8"))
        info = data.get(app_name)
        if isinstance(info, dict) and info.get("install_path"):
            return True, str(info["install_path"])
    except Exception:
        pass
    return False, None


def _launch_command_installed(app_name: str) -> str:
    return f'legendary launch "{app_name}"'


def get_epic_install_uri(
    app_name: str,
    namespace: str = "",
    catalog_item_id: str = "",
    cfg_dir: Path | None = None,
) -> str:
    """Constrói a URI do Epic Games Launcher com os 3 IDs (namespace:catalog_item_id:app_name)
    para que clicar em um jogo não instalado abra diretamente a confirmação de download na Epic.
    """
    if not (namespace and catalog_item_id):
        base = cfg_dir or legendary_config_dir()
        meta_file = base / "metadata" / f"{app_name}.json"
        if meta_file.exists():
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
                namespace = namespace or str(data.get("namespace") or meta.get("namespace") or "")
                catalog_item_id = catalog_item_id or str(data.get("catalog_item_id") or meta.get("id") or "")
            except Exception:
                pass
    if namespace and catalog_item_id:
        full_id = f"{namespace}%3A{catalog_item_id}%3A{app_name}"
        return f"com.epicgames.launcher://apps/{full_id}?action=install"
    return f"com.epicgames.launcher://apps/{app_name}?action=install"


def _launch_command_any(app_name: str, namespace: str = "", catalog_item_id: str = "") -> str:
    return get_epic_install_uri(app_name, namespace=namespace, catalog_item_id=catalog_item_id)


def list_games(
    settings: Settings,
    include_uninstalled: bool = True,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> list[EpicGame]:
    payload = None
    last_error = None
    for cmd in ("list", "list-games"):
        res = _run_legendary(settings, cmd, "--json")
        if res.returncode == 0:
            try:
                parsed = json.loads(res.stdout)
                if isinstance(parsed, list):
                    payload = parsed
                    break
            except json.JSONDecodeError:
                last_error = EpicLibraryError("Resposta JSON invalida do Legendary ao listar jogos.")
        else:
            detail = res.stderr.strip() or res.stdout.strip()
            last_error = EpicLibraryError(f"Falha ao consultar a biblioteca Epic. {detail}".strip())

    if payload is None:
        raise last_error or EpicLibraryError("Nao foi possivel listar a biblioteca Epic.")

    games: list[EpicGame] = []
    total = len(payload)

    for i, item in enumerate(payload):
        if item.get("is_dlc"):
            continue
        app_name = item.get("app_name") or item.get("appName")
        title = item.get("app_title") or item.get("title") or app_name
        if not app_name or not title:
            continue
        if str(title).strip().lower().endswith("(test branch)"):
            continue

        if progress_callback:
            progress_callback(f"Lendo biblioteca: {title}", i + 1, total)

        install = item.get("install_path") or item.get("installPath")
        if not install:
            _, install = is_game_installed(app_name)
        is_installed = bool(install)

        if not include_uninstalled and not is_installed:
            continue

        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        namespace = str(item.get("namespace") or meta.get("namespace") or "")
        catalog_id = str(item.get("catalog_item_id") or meta.get("id") or "")

        launch_cmd = (
            _launch_command_installed(app_name)
            if is_installed
            else _launch_command_any(app_name, namespace=namespace, catalog_item_id=catalog_id)
        )

        games.append(
            EpicGame(
                app_name=str(app_name),
                title=str(title),
                launch_command=launch_cmd,
                install_path=str(install) if install else None,
                is_installed=is_installed,
            )
        )

    games.sort(key=lambda g: g.title.lower())
    return games
