from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path

from steam_epic_bridge.config import Settings
from steam_epic_bridge.epic import _console_python_exe, get_epic_install_uri, is_game_installed
from steam_epic_bridge.models import EpicGame

_EPIC_URL_PREFIX = "com.epicgames.launcher://"


def _quote(path_str: str) -> str:
    clean = path_str.strip('"')
    return f'"{clean}"' if " " in clean else clean


def build_shortcut_command(settings: Settings, game: EpicGame) -> tuple[str, str, str]:
    """Retorna (exe, LaunchOptions, StartDir) para o atalho no shortcuts.vdf.

    - Quando executado a partir do binário empacotado (.exe / seb CLI instalada),
      todos os atalhos usam o comando único 'seb launch <app_name>'.
    - Mantém compatibilidade direta quando rodado em modo script/testes.
    """
    if getattr(sys, "frozen", False):
        seb_exe = _quote(sys.executable)
        start_dir = str(Path(sys.executable).resolve().parent)
        if settings.is_flatpak_steam and sys.platform != "win32":
            return "flatpak-spawn", f'--host {seb_exe} launch "{game.app_name}"', start_dir
        return seb_exe, f'launch "{game.app_name}"', start_dir

    # Em modo desenvolvimento / testes unitários:
    if sys.platform != "win32":
        if game.launch_command.startswith(_EPIC_URL_PREFIX) or (
            not game.is_installed and settings.launch_backend == "epic_launcher"
        ):
            url = game.launch_command if game.launch_command.startswith(_EPIC_URL_PREFIX) else (
                get_epic_install_uri(game.app_name)
            )
            exe = "flatpak-spawn" if settings.is_flatpak_steam else "xdg-open"
            opts = f'--host xdg-open "{url}"' if settings.is_flatpak_steam else f'"{url}"'
            return exe, opts, "/tmp"

        exe = "flatpak-spawn" if settings.is_flatpak_steam else settings.legendary_bin
        opts = (
            f'--host {_quote(settings.legendary_bin)} launch "{game.app_name}"'
            if settings.is_flatpak_steam
            else f'launch "{game.app_name}"'
        )
        return exe, opts, game.install_path or "/tmp"

    # Windows:
    # Jogo não instalado (ou configurado para abrir via Epic Games Store):
    # abre diretamente o aplicativo da Epic Games Store instalado no PC do usuário.
    if game.launch_command.startswith(_EPIC_URL_PREFIX) or (
        not game.is_installed or settings.launch_backend == "epic_launcher"
    ):
        url = game.launch_command if game.launch_command.startswith(_EPIC_URL_PREFIX) else (
            get_epic_install_uri(game.app_name)
        )
        return r'"C:\Windows\explorer.exe"', f'"{url}"', r"C:\Windows"

    if settings.legendary_bin == "python -m legendary":
        py_exe = _quote(_console_python_exe())
        return (
            r'"C:\Windows\System32\cmd.exe"',
            f'/c {py_exe} -m legendary.cli launch "{game.app_name}"',
            game.install_path or r"C:\Windows\System32",
        )

    legendary = _quote(settings.legendary_bin)
    return (
        r'"C:\Windows\System32\cmd.exe"',
        f'/c {legendary} launch "{game.app_name}"',
        game.install_path or r"C:\Windows\System32",
    )


def launch_game(settings: Settings, app_name: str) -> int:
    """Executa 'seb launch <app_name>':
    - Se não instalado (ou se backend == 'epic_launcher'): abre o aplicativo da Epic Games Store no PC do usuário.
    - Se instalado (e backend == 'legendary'): inicia o jogo diretamente.
    """
    installed, _ = is_game_installed(app_name)
    if not installed or settings.launch_backend == "epic_launcher":
        webbrowser.open(get_epic_install_uri(app_name))
        return 0

    base_cmd = (
        [_console_python_exe(), "-m", "legendary.cli"]
        if settings.legendary_bin == "python -m legendary"
        else [settings.legendary_bin]
    )
    launch_cmd = [*base_cmd, "launch", app_name]
    result = subprocess.run(launch_cmd, check=False)
    return result.returncode
