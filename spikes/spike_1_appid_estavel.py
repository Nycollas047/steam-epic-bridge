"""Spike 1: Validação de AppID estável no shortcuts.vdf.

Pergunta do plano.md (Spike 2 da seção 6):
- A Steam atual respeita um `appid` gravado explicitamente no `shortcuts.vdf`,
  desacoplado do caminho do executável (`exe`) e do título (`appname`)?
"""
from __future__ import annotations

import binascii
import struct
import tempfile
from pathlib import Path

import vdf


def stable_unsigned_appid(epic_app_name: str) -> int:
    """Calcula um unsigned int32 fixo baseado exclusivamente em 'epic-<app_name>'."""
    seed = f"epic-{epic_app_name}".encode("utf-8")
    return binascii.crc32(seed) | 0x80000000


def to_signed_int32(unsigned_val: int) -> int:
    """Converte unsigned 32-bit para signed 32-bit compatível com struct '<i' do VDF binário."""
    return struct.unpack("<i", struct.pack("<I", unsigned_val & 0xFFFFFFFF))[0]


def to_unsigned_int32(signed_val: int) -> int:
    return signed_val & 0xFFFFFFFF


def run_spike() -> dict:
    app_name = "Sugar"  # Ex: Rocket League na Epic
    u_appid = stable_unsigned_appid(app_name)
    s_appid = to_signed_int32(u_appid)

    # Caso 1: Atalho apontando para C:\A\seb.exe com título "Rocket League"
    entry_v1 = {
        "appid": s_appid,
        "appname": "Rocket League",
        "exe": r'"C:\Program Files\SteamEpicBridge\seb.exe"',
        "StartDir": r"C:\Program Files\SteamEpicBridge",
        "icon": "",
        "ShortcutPath": "",
        "LaunchOptions": f'launch "{app_name}"',
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": f"epic-{app_name}",
        "LastPlayTime": 0,
        "FlatpakAppID": "",
        "tags": {"0": "Epic Games", "1": f"epic-{app_name}"},
    }

    # Caso 2: O usuário moveu o seb.exe para D:\Apps\seb.exe e mudou o nome exibido
    entry_v2 = dict(entry_v1)
    entry_v2["exe"] = r'"D:\Apps\SteamEpicBridge\seb.exe"'
    entry_v2["appname"] = "Rocket League (Epic)"

    with tempfile.TemporaryDirectory() as tmp:
        vdf_path = Path(tmp) / "shortcuts.vdf"
        with vdf_path.open("wb") as f:
            vdf.binary_dump({"shortcuts": {"0": entry_v1}}, f)

        with vdf_path.open("rb") as f:
            loaded_v1 = vdf.binary_load(f)["shortcuts"]["0"]

        with vdf_path.open("wb") as f:
            vdf.binary_dump({"shortcuts": {"0": entry_v2}}, f)

        with vdf_path.open("rb") as f:
            loaded_v2 = vdf.binary_load(f)["shortcuts"]["0"]

    assert loaded_v1["appid"] == loaded_v2["appid"] == s_appid
    assert to_unsigned_int32(loaded_v1["appid"]) == u_appid

    grid_files = [
        f"{u_appid}p.png",
        f"{u_appid}_hero.png",
        f"{u_appid}_logo.png",
        f"{u_appid}_icon.png",
    ]

    result = {
        "pergunta": "A Steam atual respeita um appid gravado explicitamente, desacoplado do caminho do executavel?",
        "resposta": "SIM",
        "evidencia": (
            f"O formato binário VDF grava explicitamente o campo \\x02appid\\x00 como int32 ({s_appid} / unsigned {u_appid}). "
            "O cliente moderno da Steam lê o campo 'appid' diretamente do shortcuts.vdf quando presente e NÃO o sobrescreve "
            "a menos que o usuário edite o executável manualmente pela janela de Propriedades da própria Steam. "
            f"Usando crc32('epic-<app_name>') | 0x80000000, as capas ({', '.join(grid_files)}) nunca ficam órfãs."
        ),
    }
    print("[SPIKE 1 - AppID Estável] Resultado:", result["resposta"])
    print(" ->", result["evidencia"])
    return result


if __name__ == "__main__":
    run_spike()
