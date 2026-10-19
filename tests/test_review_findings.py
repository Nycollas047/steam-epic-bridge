"""Regressões dos problemas apontados na revisão do PR #1.

1. Atalho manual do usuário não pode ser reivindicado só pelo título.
2. shortcuts.vdf ilegível não pode virar biblioteca vazia (perderia os atalhos do usuário).
3. O comando do Legendary precisa ser executável de verdade (Linux com venv, .exe empacotado).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import vdf
from click.testing import CliRunner

from steam_epic_bridge.config import APP_ID_PREFIX, SHORTCUT_TAG
from steam_epic_bridge.epic import LEGENDARY_MODULE, legendary_argv
from steam_epic_bridge.steam import SteamShortcutsError, sync_shortcuts

from test_corrections import _make_game, _make_settings


def _write_vdf(path: Path, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        vdf.binary_dump({"shortcuts": entries}, handle)


def _read_entries(path: Path) -> dict:
    with path.open("rb") as handle:
        return vdf.binary_load(handle)["shortcuts"]


class TestManualShortcutsAreNotClaimed:
    def test_atalho_manual_com_mesmo_titulo_e_preservado(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        manual = {"appid": 111, "appname": "Fortnite", "exe": "/meu/jogo", "LaunchOptions": "--meu", "tags": {}}
        _write_vdf(settings.shortcuts_path, {"0": manual})

        created, updated, _, _ = sync_shortcuts(settings, [_make_game()])

        entries = _read_entries(settings.shortcuts_path)
        assert (created, updated) == (1, 0)
        assert len(entries) == 2
        assert entries["0"]["exe"] == "/meu/jogo"
        assert entries["0"]["LaunchOptions"] == "--meu"
        assert SHORTCUT_TAG not in entries["0"]["tags"].values()

    def test_atalho_antigo_do_proprio_app_e_migrado(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        legacy = {"appid": 222, "appname": "Fortnite", "exe": "velho", "tags": {"0": SHORTCUT_TAG}}
        _write_vdf(settings.shortcuts_path, {"0": legacy})

        created, updated, _, _ = sync_shortcuts(settings, [_make_game()])

        entries = _read_entries(settings.shortcuts_path)
        assert (created, updated) == (0, 1)
        assert len(entries) == 1
        assert f"{APP_ID_PREFIX}Fortnite" in entries["0"]["tags"].values()


class TestUnreadableShortcutsFile:
    def test_arquivo_corrompido_nao_e_sobrescrito(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.shortcuts_path.parent.mkdir(parents=True, exist_ok=True)
        corrupted = b"\x00\x01lixo que nao e vdf binario"
        settings.shortcuts_path.write_bytes(corrupted)
        backup = settings.shortcuts_path.with_suffix(".vdf.bak")
        backup.write_bytes(b"backup bom anterior")

        with pytest.raises(SteamShortcutsError):
            sync_shortcuts(settings, [_make_game()])

        assert settings.shortcuts_path.read_bytes() == corrupted
        assert backup.read_bytes() == b"backup bom anterior"

    def test_arquivo_vazio_conta_como_biblioteca_vazia(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.shortcuts_path.parent.mkdir(parents=True, exist_ok=True)
        settings.shortcuts_path.write_bytes(b"")

        created, _, _, _ = sync_shortcuts(settings, [_make_game()])

        assert created == 1


class TestLegendaryCommand:
    def test_executavel_configurado_e_usado_como_esta(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.legendary_bin = "/usr/bin/legendary"
        assert legendary_argv(settings) == ["/usr/bin/legendary"]

    def test_modo_codigo_fonte_usa_interpretador_atual(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.legendary_bin = LEGENDARY_MODULE
        argv = legendary_argv(settings)
        assert argv[1:] == ["-m", "legendary.cli"]
        assert Path(argv[0]).name.lower().startswith("python")

    def test_app_empacotado_nao_usa_o_exe_como_python(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _make_settings(tmp_path)
        settings.legendary_bin = LEGENDARY_MODULE
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", "/opt/seb/SteamEpicBridge")
        assert legendary_argv(settings) == ["/opt/seb/SteamEpicBridge", "legendary-passthrough"]

    @pytest.mark.skipif(sys.platform == "win32", reason="caminho de atalho do Linux")
    def test_atalho_linux_nao_grava_comando_composto_como_executavel(self, tmp_path: Path) -> None:
        from steam_epic_bridge.launcher import build_shortcut_command

        settings = _make_settings(tmp_path)
        settings.legendary_bin = LEGENDARY_MODULE
        exe, opts, _ = build_shortcut_command(settings, _make_game())

        assert " " not in exe.strip('"') or Path(exe.strip('"')).exists()
        assert "python -m legendary" not in exe
        assert opts.startswith("-m legendary.cli launch")

    def test_passthrough_repassa_argumentos_ao_legendary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import legendary.cli as legendary_cli

        from steam_epic_bridge.cli import cli

        seen: list[list[str]] = []
        monkeypatch.setattr(legendary_cli, "main", lambda: seen.append(list(sys.argv)))

        result = CliRunner().invoke(cli, ["legendary-passthrough", "launch", "--offline", "Sugar"])

        assert result.exit_code == 0, result.output
        assert seen == [["legendary", "launch", "--offline", "Sugar"]]
