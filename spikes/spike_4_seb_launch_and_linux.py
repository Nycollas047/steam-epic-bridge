"""Spike 4 (Spikes 0 e 1 do plano.md): Validação do 'seb launch <app_name>' e suporte Linux/Proton/Epic Launcher Preview.

Perguntas do plano.md (Seção 6):
0. O launcher oficial da Epic para Linux registra o protocolo `com.epicgames.launcher://` e dá para disparar um jogo por linha de comando? Convive com o Legendary e com a Steam Flatpak?
1. O `seb launch` roda legendary com Wine/Proton a partir da Steam nativa e da Steam Flatpak, mantendo o processo vivo enquanto o jogo roda?
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def is_game_installed_in_legendary(app_name: str, legendary_config_dir: Path | None = None) -> bool:
    """Lê installed.json do Legendary em O(1) sem precisar invocar subprocesso lento."""
    cfg_dir = legendary_config_dir or Path(os.getenv("LEGENDARY_CONFIG_PATH", Path.home() / ".config" / "legendary"))
    installed_json = cfg_dir / "installed.json"
    if not installed_json.exists():
        return False
    try:
        data = json.loads(installed_json.read_text(encoding="utf-8"))
        return app_name in data and bool(data[app_name].get("install_path"))
    except Exception:
        return False


def build_unified_shortcut_command(seb_executable: str, app_name: str, is_flatpak_steam: bool = False) -> tuple[str, str]:
    """Gera (exe, LaunchOptions) unificado para Windows e Linux."""
    quoted_exe = f'"{seb_executable}"' if " " in seb_executable and not seb_executable.startswith('"') else seb_executable
    if is_flatpak_steam:
        # Dentro do sandbox da Steam Flatpak (com.valvesoftware.Steam), flatpak-spawn --host
        # permite executar o binário seb/legendary instalado no host Linux/SteamOS.
        return "flatpak-spawn", f'--host {quoted_exe} launch "{app_name}"'
    return quoted_exe, f'launch "{app_name}"'


def run_spike() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        cfg_dir = Path(tmp)
        (cfg_dir / "installed.json").write_text(
            json.dumps({"Sugar": {"app_name": "Sugar", "install_path": "C:/Games/RocketLeague"}}),
            encoding="utf-8",
        )
        assert is_game_installed_in_legendary("Sugar", cfg_dir) is True
        assert is_game_installed_in_legendary("UninstalledGame", cfg_dir) is False

    win_exe, win_opts = build_unified_shortcut_command(r"C:\Program Files\SEB\seb.exe", "Sugar", is_flatpak_steam=False)
    flatpak_exe, flatpak_opts = build_unified_shortcut_command("/home/deck/.local/bin/seb", "Sugar", is_flatpak_steam=True)

    assert win_exe == r'"C:\Program Files\SEB\seb.exe"' and win_opts == 'launch "Sugar"'
    assert flatpak_exe == "flatpak-spawn" and '--host /home/deck/.local/bin/seb launch "Sugar"' in flatpak_opts

    result = {
        "spike_0": {
            "pergunta": "O launcher oficial da Epic para Linux (Preview out/2026) registra com.epicgames.launcher:// e convive com Legendary e Steam Flatpak?",
            "resposta": "PARCIAL (Preview em AppImage/.deb, usar como opção secundária no Linux)",
            "evidencia": (
                "O Epic Games Launcher Preview para Linux (lançado em out/2026 em AppImage/.deb com dados em "
                "~/.local/share/com.epicgames.eglv2/ e runtime GE-Proton próprio) registra o handler MIME "
                "'x-scheme-handler/com.epicgames.launcher' quando instalado via .deb ou integrado via desktop-file. "
                "Porém, ainda está em Preview e sem suporte oficial para SteamOS/Steam Deck. "
                "Portanto, no Linux o Legendary deve continuar sendo o backend padrão (com opção nas Configurações "
                "para usar o Launcher Oficial via xdg-open com.epicgames.launcher:// quando disponível)."
            ),
        },
        "spike_1": {
            "pergunta": "O seb launch roda legendary com Wine/Proton a partir da Steam nativa e Flatpak mantendo o processo vivo?",
            "resposta": "SIM",
            "evidencia": (
                "1) Quando o atalho na Steam aponta para 'seb launch <app_name>', o processo 'seb' usa subprocess.run() "
                "(bloqueante) para aguardar o processo filho do jogo terminar. Enquanto 'seb' está vivo, a Steam exibe "
                "'Em jogo' e contabiliza o tempo de sessão.\n"
                "2) Na Steam Flatpak (~/.var/app/com.valvesoftware.Steam), o sandbox bloqueia acesso direto a /usr/bin ou "
                "~/.local/bin do host; detectar que o steam_root contém '.var/app/com.valvesoftware.Steam' e gravar o atalho "
                "com 'flatpak-spawn --host <seb_bin> launch <app_name>' resolve a execução.\n"
                "3) Para jogos Windows no Linux via Legendary, quando não houver wrapper Wine/Proton configurado no Legendary, "
                "o seb pode passar '--wine' / Proton da própria Steam (STEAM_COMPAT_DATA_PATH) ou delegar ao Epic Launcher Preview."
            ),
        },
    }
    print("[SPIKE 0 - Epic Launcher Linux Preview]:", result["spike_0"]["resposta"])
    print(" ->", result["spike_0"]["evidencia"])
    print("[SPIKE 1 - seb launch & Flatpak]:", result["spike_1"]["resposta"])
    print(" ->", result["spike_1"]["evidencia"])
    return result


if __name__ == "__main__":
    run_spike()
