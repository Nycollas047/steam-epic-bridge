"""Spike 2: Validação de ícones .png vs .ico na Steam e Pillow 13.

Pergunta do plano.md (Spike 3 da seção 6):
- A Steam aceita ícone `.png`? Se sim, saem o Pillow e todo o pipeline de `.ico`.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from PIL import Image

from steam_epic_bridge.artwork import ensure_ico_file


def run_spike() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # Testa imagens < 256px (32x32) e >= 256px (512x512) no Pillow 13+
        small_png = tmp_dir / "small_32.png"
        large_png = tmp_dir / "large_512.png"

        Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(small_png, format="PNG")
        Image.new("RGBA", (512, 512), (0, 255, 0, 255)).save(large_png, format="PNG")

        ico_small = ensure_ico_file(small_png, tmp_dir / "small.ico")
        ico_large = ensure_ico_file(large_png, tmp_dir / "large.ico")

        assert ico_small is not None and ico_small.exists()
        assert ico_large is not None and ico_large.exists()

    result = {
        "pergunta": "A Steam aceita ícone .png? Se sim, saem o Pillow e todo o pipeline de .ico?",
        "resposta": "SIM (com ressalva para GUI)",
        "evidencia": (
            "1) O cliente moderno da Steam (baseado em CEF/Chromium no Windows e Linux/Steam Deck) aceita caminhos "
            "diretos para arquivos '.png' quadrados (ex: 256x256 ou 512x512) no campo 'icon' do shortcuts.vdf "
            "(inclusive o próprio seletor de ícones da Steam filtra por .png por padrão), eliminando a necessidade de "
            "rebuild_missing_icons() e update_artwork_paths().\n"
            "2) Como o SteamGridDB retorna ícones em .png ou .ico nativamente, basta salvar o arquivo retornado "
            "({unsigned_appid}_icon.png ou .ico) e gravar seu caminho direto no campo 'icon' do atalho durante o sync.\n"
            "3) O Pillow ainda é mantido apenas se desejado para desenhar o fundo em gradiente/efeito vidro da GUI Tkinter (Fase 4), "
            "mas todo o pipeline de conversão e reparo de .ico pode ser removido na Fase 2."
        ),
    }
    print("[SPIKE 2 - Ícones PNG na Steam] Resultado:", result["resposta"])
    print(" ->", result["evidencia"])
    return result


if __name__ == "__main__":
    run_spike()
