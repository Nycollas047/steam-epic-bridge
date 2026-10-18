"""
Testes unitários do Steam Epic Bridge (Arquitetura Simplificada v0.2).
Execute com: python -m pytest tests/ -v
"""
from __future__ import annotations

import inspect
import struct
import sys
from pathlib import Path

import pytest
import vdf

from steam_epic_bridge.config import Settings
from steam_epic_bridge.models import DiscoveryResult, EpicGame


def _make_settings(tmp_path: Path) -> Settings:
    steam_root = tmp_path / "Steam"
    user_id = "12345678"
    (steam_root / "userdata" / user_id / "config" / "grid").mkdir(parents=True, exist_ok=True)
    return Settings(
        steam_root=steam_root,
        steam_user_id=user_id,
        legendary_bin="legendary",
        steamgriddb_api_key=None,
        debug=False,
        # Sem isso, Settings varre a maquina real (Steam, Legendary) a cada teste,
        # e os testes que simulam sys.platform="win32" quebram no Linux.
        discovery=DiscoveryResult(),
    )


def _make_game(app_name: str = "Fortnite", title: str = "Fortnite") -> EpicGame:
    return EpicGame(
        app_name=app_name,
        title=title,
        launch_command=f'legendary launch "{app_name}"',
        is_installed=True,
        install_path=r"C:\Games",
    )


class TestComputeAppid:
    def test_retorna_inteiro(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import compute_appid

        assert isinstance(compute_appid(_make_settings(tmp_path), _make_game()), int)

    def test_determinismo(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import compute_appid

        s, g = _make_settings(tmp_path), _make_game()
        assert compute_appid(s, g) == compute_appid(s, g)

    def test_estavel_mesmo_mudando_exe_ou_titulo(self, tmp_path: Path) -> None:
        """O appid depende exclusivamente de epic-<app_name>, nunca ficando órfão."""
        from steam_epic_bridge.steam import compute_appid

        s1 = _make_settings(tmp_path)
        s1.legendary_bin = r"C:\Antigo\legendary.exe"
        g1 = _make_game("Sugar", "Rocket League")

        s2 = _make_settings(tmp_path)
        s2.legendary_bin = r"D:\Novo\legendary.exe"
        g2 = _make_game("Sugar", "Rocket League - Edicao 2026")

        assert compute_appid(s1, g1) == compute_appid(s2, g2)

    def test_jogos_distintos_ids_distintos(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import compute_appid

        s = _make_settings(tmp_path)
        assert compute_appid(s, _make_game("Fortnite", "Fortnite")) != compute_appid(
            s, _make_game("RocketLeague", "Rocket League")
        )

    def test_bit_31_setado(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import compute_appid

        appid = compute_appid(_make_settings(tmp_path), _make_game())
        assert (appid & 0x80000000) or (appid < 0)

    def test_serializavel_como_int32(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import compute_appid

        appid = compute_appid(_make_settings(tmp_path), _make_game())
        try:
            struct.pack("<i", appid)
        except struct.error as e:
            pytest.fail(f"appid {appid} não é um int32 válido: {e}")


class TestArtworkSufixosEFiltros:
    def test_grid_sufixo_p(self) -> None:
        from steam_epic_bridge.artwork import IMAGE_TYPES

        assert IMAGE_TYPES["grid"][1] == "p"

    def test_hero_sufixo(self) -> None:
        from steam_epic_bridge.artwork import IMAGE_TYPES

        assert IMAGE_TYPES["hero"][1] == "_hero"

    def test_logo_sufixo(self) -> None:
        from steam_epic_bridge.artwork import IMAGE_TYPES

        assert IMAGE_TYPES["logo"][1] == "_logo"

    def test_nome_arquivo_grid_final(self) -> None:
        from steam_epic_bridge.artwork import IMAGE_TYPES

        _, s = IMAGE_TYPES["grid"]
        assert f"9999{s}.png" == "9999p.png"

    def test_filtros_steamgriddb_poster_vertical_na_origem(self) -> None:
        from steam_epic_bridge.artwork import build_steamgriddb_params

        params = build_steamgriddb_params("grid", style="alternate", prefer_animated=True)
        assert params["dimensions"] == "600x900,660x930,342x482"
        assert params["styles"] == "alternate"
        assert params["types"] == "animated,static"
        assert params["mimes"] == "image/png,image/jpeg"


class TestShortcuts:
    def test_adiciona_novo(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import add_games

        c, sk, _ = add_games(_make_settings(tmp_path), [_make_game()])
        assert c == 1 and sk == 0

    def test_idempotente_por_tag_app_name(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import sync_shortcuts

        s, g = _make_settings(tmp_path), _make_game("Sugar", "Rocket League")
        c1, u1, sk1, _ = sync_shortcuts(s, [g])
        assert c1 == 1 and u1 == 0 and sk1 == 0

        # Rodar de novo sem mudanças: idempotente (skipped = 1)
        c2, u2, sk2, _ = sync_shortcuts(s, [g])
        assert c2 == 0 and u2 == 0 and sk2 == 1

        # Se o caminho de instalação mudou, o mesmo atalho (epic-Sugar) é corrigido in-place sem duplicar!
        g_moved = _make_game("Sugar", "Rocket League")
        g_moved.install_path = r"D:\Games\RocketLeague"
        c3, u3, sk3, _ = sync_shortcuts(s, [g_moved])
        assert c3 == 0 and u3 == 1 and sk3 == 0

    def test_backup_gerado(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import add_games

        s = _make_settings(tmp_path)
        add_games(s, [_make_game()])
        _, _, bak = add_games(s, [_make_game("RL", "Rocket League")])
        assert bak and bak.exists()

    def test_remove_atalhos(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import add_games, remove_epic_shortcuts

        s = _make_settings(tmp_path)
        add_games(s, [_make_game()])
        assert remove_epic_shortcuts(s) == 1

    def test_vdf_valido(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import add_games

        s = _make_settings(tmp_path)
        add_games(s, [_make_game()])
        assert s.shortcuts_path is not None
        with s.shortcuts_path.open("rb") as f:
            assert "shortcuts" in vdf.binary_load(f)


class TestMotorUnicoLimpo:
    def test_sem_entry_for_game_privado(self) -> None:
        import steam_epic_bridge.cli as m

        assert "_entry_for_game" not in inspect.getsource(m)

    def test_usa_compute_appid(self) -> None:
        import steam_epic_bridge.cli as m

        assert "compute_appid" in inspect.getsource(m)


class TestMultiplatformLaunch:
    def test_linux_launch_installed_game(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from steam_epic_bridge.steam import _build_exe_and_launch

        monkeypatch.setattr(sys, "platform", "linux")
        settings = _make_settings(tmp_path)
        settings.legendary_bin = "/usr/bin/legendary"

        installed_game = EpicGame(
            app_name="Fortnite",
            title="Fortnite",
            launch_command="legendary launch Fortnite",
            is_installed=True,
            install_path="/home/user/games",
        )

        exe, opts, start_dir = _build_exe_and_launch(settings, installed_game)
        assert exe == "/usr/bin/legendary"
        assert opts == 'launch "Fortnite"'
        assert start_dir == "/home/user/games"

    def test_linux_launch_uninstalled_game(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from steam_epic_bridge.steam import _build_exe_and_launch

        monkeypatch.setattr(sys, "platform", "linux")
        settings = _make_settings(tmp_path)

        uninstalled_game = EpicGame(
            app_name="Fortnite",
            title="Fortnite",
            launch_command="com.epicgames.launcher://apps/Fortnite?action=launch",
            is_installed=False,
            install_path=None,
        )

        exe, opts, start_dir = _build_exe_and_launch(settings, uninstalled_game)
        assert exe == "xdg-open"
        assert opts == '"com.epicgames.launcher://apps/Fortnite?action=launch"'
        assert start_dir == "/tmp"

    def test_linux_flatpak_uses_flatpak_spawn(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from steam_epic_bridge.steam import _build_exe_and_launch

        monkeypatch.setattr(sys, "platform", "linux")
        flatpak_root = tmp_path / ".var" / "app" / "com.valvesoftware.Steam" / ".steam" / "steam"
        (flatpak_root / "userdata" / "12345678" / "config").mkdir(parents=True)
        settings = Settings(
            steam_root=flatpak_root,
            steam_user_id="12345678",
            legendary_bin="/home/deck/.local/bin/legendary",
            steamgriddb_api_key=None,
        )
        installed_game = _make_game("Sugar", "Rocket League")
        exe, opts, _ = _build_exe_and_launch(settings, installed_game)
        assert exe == "flatpak-spawn"
        assert '--host /home/deck/.local/bin/legendary launch "Sugar"' in opts

    def test_epic_install_uri_includes_namespace_and_catalog_id(self, tmp_path: Path) -> None:
        import json
        from steam_epic_bridge.epic import get_epic_install_uri

        meta_dir = tmp_path / "metadata"
        meta_dir.mkdir(parents=True)
        (meta_dir / "Sugar.json").write_text(
            json.dumps(
                {
                    "app_name": "Sugar",
                    "metadata": {
                        "namespace": "9773aa1aa54f4f7b80e44bef04986cea",
                        "id": "530145df28a24424923f5828cc9031a1",
                    },
                }
            ),
            encoding="utf-8",
        )
        uri = get_epic_install_uri("Sugar", cfg_dir=tmp_path)
        assert uri == (
            "com.epicgames.launcher://apps/"
            "9773aa1aa54f4f7b80e44bef04986cea%3A530145df28a24424923f5828cc9031a1%3ASugar"
            "?action=install"
        )

    def test_windows_uninstalled_game_opens_epic_games_store(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from steam_epic_bridge.steam import _build_exe_and_launch

        monkeypatch.setattr(sys, "platform", "win32")
        settings = _make_settings(tmp_path)
        settings.legendary_bin = "python -m legendary"

        uninstalled_game = EpicGame(
            app_name="Sugar",
            title="Rocket League",
            launch_command="com.epicgames.launcher://apps/Sugar?action=install",
            is_installed=False,
            install_path=None,
        )
        exe, opts, _ = _build_exe_and_launch(settings, uninstalled_game)
        assert "explorer.exe" in exe
        assert "com.epicgames.launcher://apps/Sugar?action=install" in opts

