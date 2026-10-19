"""Conversao de imagens de qualquer tamanho/proporcao para .ico."""
from __future__ import annotations

import pytest
from PIL import Image


@pytest.mark.parametrize("size", [(32, 32), (64, 64), (300, 100), (100, 400), (600, 600)])
def test_ensure_ico_file_aceita_qualquer_tamanho(tmp_path, size):
    from steam_epic_bridge.artwork import ensure_ico_file

    source = tmp_path / "icon.png"
    Image.new("RGBA", size, (255, 0, 0, 255)).save(source, format="PNG")

    result = ensure_ico_file(source)

    assert result is not None and result.exists()
    with Image.open(result) as ico:
        assert ico.size[0] == ico.size[1]
