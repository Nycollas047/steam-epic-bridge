"""Spike 3: Inspeção do Legendary e fluxo de autenticação OAuth da Epic Games.

Pergunta do plano.md (Spike 4 da seção 6):
- Login da Epic: janela do próprio Legendary (Windows 0.20.14+) ou webview opcional (0.21),
  contra o fluxo atual de colar o SID. O Legendary oferece `--code`, `--token` e `--sid`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def run_spike() -> dict:
    bin_path = Path(__file__).resolve().parent.parent / "steam_epic_bridge" / "bin" / "legendary.exe"
    version_out = "N/A"
    auth_help_out = "N/A"

    if bin_path.exists():
        ver = subprocess.run([str(bin_path), "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        version_out = (ver.stdout or ver.stderr).strip()

        hlp = subprocess.run([str(bin_path), "auth", "--help"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        auth_help_out = (hlp.stdout or hlp.stderr).strip()

    print(f"[SPIKE 3 - Legendary Auth] Binário atual: {version_out}")
    print(auth_help_out)

    result = {
        "pergunta": "Qual o fluxo ideal de login no Legendary contra o fluxo atual de colar SID?",
        "binario_atual": version_out,
        "suporta_code": "--code" in auth_help_out,
        "suporta_sid": "--sid" in auth_help_out,
        "suporta_disable_webview": "--disable-webview" in auth_help_out,
        "evidencia": (
            f"Binário inspecionado: ({version_out}). "
            "A Epic descontinuou/restringiu o fluxo antigo de SID no navegador, fazendo '--sid' falhar com frequência. "
            "O fluxo moderno e estável do Legendary usa:\n"
            "  1) Webview automática ('legendary auth' abre a janela de login direto no Windows quando pywebview está presente, "
            "capturando o authorizationCode automaticamente sem o usuário copiar/colar nada), OU\n"
            "  2) 'legendary auth --code <authorizationCode>' extraindo o campo 'authorizationCode' do JSON exibido pela Epic "
            "(URL oficial: https://www.epicgames.com/id/api/redirect?clientId=34a02cf8f4414e29b15921876da36f9a&responseType=code)."
        ),
    }
    return result


if __name__ == "__main__":
    run_spike()
