from __future__ import annotations

import logging
import sys
from typing import Callable

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from steam_epic_bridge.artwork import clear_artwork_cache, download_artwork_batch, has_vertical_cover
from steam_epic_bridge.config import Settings, get_settings, load_config_file, save_config_file
from steam_epic_bridge.epic import (
    EpicAuthError,
    EpicError,
    EpicLibraryError,
    ensure_authenticated,
    get_account,
    list_games,
)
from steam_epic_bridge.launcher import launch_game
from steam_epic_bridge.models import SyncResult
from steam_epic_bridge.steam import (
    SteamShortcutsError,
    clear_only_artwork,
    compute_appid,
    ensure_shortcuts_file,
    existing_shortcuts_count,
    is_steam_running,
    latest_backup_path,
    plan_add_games,
    remove_epic_shortcuts,
    restore_shortcuts_backup,
    sync_shortcut_icons,
    sync_shortcuts,
)

LOGGER = logging.getLogger(__name__)
console = Console()


def _configure_logging(settings: Settings) -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        settings.log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(settings.log_path, encoding="utf-8"))
    except Exception:
        pass
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=handlers,
    )


# ============================================================================
# MOTOR ÚNICO (usado tanto pela CLI quanto pela GUI)
# ============================================================================

def get_status(settings: Settings) -> dict:
    shortcuts_path = ensure_shortcuts_file(settings)
    account = get_account(settings)
    try:
        games = list_games(settings) if account else []
        epic_games: int | str = len(games) if account else "Indisponivel"
    except Exception:
        epic_games = "Indisponivel"

    try:
        existing = existing_shortcuts_count(settings)
    except Exception:
        existing = 0

    return {
        "steam_root": str(settings.steam_root),
        "steam_user_id": settings.steam_user_id,
        "shortcuts_path": str(shortcuts_path),
        "epic_account": account,
        "epic_games": epic_games,
        "epic_shortcuts": existing,
        "artwork_enabled": bool(settings.steamgriddb_api_key),
    }


def doctor(settings: Settings) -> dict:
    shortcuts_path = settings.shortcuts_path
    backup_path = latest_backup_path(shortcuts_path) if shortcuts_path else None
    steam_config_ready = bool(shortcuts_path and shortcuts_path.parent.exists())

    try:
        account = ensure_authenticated(settings)
        epic_authenticated = True
        epic_auth_error = None
    except Exception as exc:
        account = None
        epic_authenticated = False
        epic_auth_error = str(exc)

    try:
        epic_games = len(list_games(settings)) if epic_authenticated else None
        epic_library_error = None
    except Exception as exc:
        epic_games = None
        epic_library_error = str(exc)

    return {
        "steam_root_exists": settings.steam_root.exists(),
        "steam_user_id": settings.steam_user_id,
        "steam_config_ready": steam_config_ready,
        "shortcuts_path": str(shortcuts_path) if shortcuts_path else None,
        "backup_available": bool(backup_path and backup_path.exists()),
        "legendary_bin": settings.legendary_bin,
        "epic_account": account,
        "epic_authenticated": epic_authenticated,
        "epic_auth_error": epic_auth_error,
        "epic_games": epic_games,
        "epic_library_error": epic_library_error,
        "artwork_enabled": bool(settings.steamgriddb_api_key),
        "discovered_steam_roots": [str(p) for p in settings.discovery.steam_roots],
        "discovered_steam_user_ids": list(settings.discovery.steam_user_ids),
        "discovered_legendary_bins": [str(p) for p in settings.discovery.legendary_bins],
        "discovered_epic_launchers": [str(p) for p in settings.discovery.epic_launcher_bins],
    }


def sync_library(
    settings: Settings,
    download_artwork: bool = True,
    installed_only: bool = False,
    dry_run: bool = False,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> SyncResult:
    """Sincroniza e corrige atalhos e capas da biblioteca Epic em um único passo idempotente."""
    ensure_authenticated(settings)
    games = list_games(
        settings,
        include_uninstalled=not installed_only,
        progress_callback=progress_callback,
    )
    if installed_only:
        games = [g for g in games if g.is_installed]

    if not games:
        return SyncResult()

    planned_created, planned_skipped = plan_add_games(settings, games)
    if dry_run:
        return SyncResult(planned=planned_created, skipped=planned_skipped)

    created, updated, skipped, backup = sync_shortcuts(settings, games)
    result = SyncResult(
        created=created,
        updated=updated,
        skipped=skipped,
        planned=planned_created,
        backup_path=backup,
    )

    games_with_appid = [(game, compute_appid(settings, game)) for game in games]

    if download_artwork and settings.steamgriddb_api_key:
        downloaded, missing_cover = download_artwork_batch(
            settings,
            games_with_appid,
            progress_callback=progress_callback,
        )
        result.artwork_downloaded = downloaded
        result.missing_artwork = missing_cover
        sync_shortcut_icons(settings)
    else:
        result.missing_artwork = sum(
            1 for _, appid in games_with_appid if not has_vertical_cover(settings.grid_dir, appid)
        )

    return result


def clean(settings: Settings) -> SyncResult:
    return SyncResult(removed=remove_epic_shortcuts(settings))


def restore(settings: Settings) -> SyncResult:
    return SyncResult(backup_path=restore_shortcuts_backup(settings))


def clear_art(settings: Settings) -> int:
    clear_artwork_cache()
    return clear_only_artwork(settings)


# ============================================================================
# INTERFACE DE LINHA DE COMANDO (CLICK)
# ============================================================================

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Steam Epic Bridge (seb) - Sua biblioteca Epic inteira dentro da Steam."""
    if ctx.invoked_subcommand is None:
        from steam_epic_bridge.gui import run_gui

        run_gui()


@cli.command(name="launch")
@click.argument("app_name")
def launch_cmd(app_name: str) -> None:
    """Inicia um jogo da Epic (ou instala se ainda nao estiver instalado)."""
    settings = get_settings()
    _configure_logging(settings)
    code = launch_game(settings, app_name)
    sys.exit(code)


@cli.command()
@click.option("--no-artwork", is_flag=True, help="Nao baixa artes do SteamGridDB.")
@click.option("--installed-only", is_flag=True, help="Sincroniza apenas jogos ja instalados.")
@click.option("--dry-run", is_flag=True, help="Mostra o que seria criado sem alterar o Steam.")
def sync(no_artwork: bool, installed_only: bool, dry_run: bool) -> None:
    """Sincroniza e corrige atalhos e capas da Epic na biblioteca do Steam."""
    settings = get_settings()
    _configure_logging(settings)

    if is_steam_running() and not dry_run:
        console.print("\n[bold red]O Steam esta aberto.[/bold red] Feche o Steam completamente antes de sincronizar.\n")
        return

    if not settings.steamgriddb_api_key and not no_artwork:
        console.print(
            "[yellow]Chave SteamGridDB nao configurada - capas nao serao baixadas.[/yellow]\n"
            "[dim]Configure com: seb setup[/dim]\n"
        )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            sync_task = progress.add_task("[cyan]Sincronizando biblioteca...", total=None)

            def update_progress(title: str, current: int = 0, total: int = 1) -> None:
                progress.update(sync_task, description=f"[cyan]Processando: [bold]{title}[/bold] ({current}/{total})")

            result = sync_library(
                settings,
                download_artwork=not no_artwork,
                installed_only=installed_only,
                dry_run=dry_run,
                progress_callback=update_progress,
            )
            progress.update(sync_task, description="[green]Sincronizacao concluida!", completed=100)
    except (EpicError, SteamShortcutsError) as exc:
        raise click.ClickException(str(exc)) from exc

    if dry_run:
        console.print(f"[bold cyan]Dry-run concluido.[/bold cyan] Novos atalhos previstos: {result.planned}")
        console.print(f"Ja existentes: {result.skipped}\n")
        return

    console.print(
        f"[bold green]Concluido:[/bold green] {result.created} novos, "
        f"{result.updated} corrigidos, {result.missing_artwork} sem capa. Reabra a Steam."
    )


@cli.command()
def status() -> None:
    """Mostra o estado atual do Steam, Epic e artworks."""
    settings = get_settings()
    _configure_logging(settings)
    try:
        data = get_status(settings)
    except (EpicError, SteamShortcutsError) as exc:
        raise click.ClickException(str(exc)) from exc

    table = Table(title="Steam Epic Bridge - Status", border_style="blue")
    table.add_column("Campo", style="bold")
    table.add_column("Valor", overflow="fold")

    labels = {
        "steam_root": "Steam instalado em",
        "steam_user_id": "Usuario Steam detectado",
        "shortcuts_path": "Arquivo shortcuts.vdf",
        "epic_account": "Conta Epic conectada",
        "epic_games": "Jogos na biblioteca Epic",
        "epic_shortcuts": "Atalhos Epic ja no Steam",
        "artwork_enabled": "Capas automaticas (SteamGridDB)",
    }
    for key, label in labels.items():
        val = data.get(key)
        if key == "artwork_enabled":
            val = "Configurada" if val else "Sem chave"
        table.add_row(label, str(val or "Nao detectado"))

    console.print()
    console.print(table)
    console.print()


@cli.command(name="doctor")
def doctor_cmd() -> None:
    """Executa um diagnostico rapido do ambiente."""
    settings = get_settings()
    _configure_logging(settings)
    data = doctor(settings)

    table = Table(title="Steam Epic Bridge - Diagnostico", border_style="cyan")
    table.add_column("Check", style="bold")
    table.add_column("Resultado", overflow="fold")

    checks = [
        ("Steam instalado", "OK" if data["steam_root_exists"] else "Falhou"),
        ("Steam user id", data["steam_user_id"] or "Nao detectado"),
        ("Config do Steam", "OK" if data["steam_config_ready"] else "Nao encontrada"),
        ("Arquivo shortcuts.vdf", data["shortcuts_path"] or "Nao encontrado"),
        ("Backup disponivel", "Sim" if data["backup_available"] else "Nao"),
        ("Legendary", data["legendary_bin"]),
        ("Epic autenticada", data["epic_account"] if data["epic_authenticated"] else (data["epic_auth_error"] or "Falhou")),
        ("Biblioteca Epic", str(data["epic_games"]) if data["epic_games"] is not None else "Indisponivel"),
        ("SteamGridDB", "Configurada" if data["artwork_enabled"] else "Sem chave"),
    ]
    for label, value in checks:
        table.add_row(label, str(value))
    console.print()
    console.print(table)
    console.print()


@cli.command(name="clean")
def clean_cmd() -> None:
    """Remove todos os atalhos Epic e suas capas da biblioteca do Steam."""
    settings = get_settings()
    _configure_logging(settings)
    if is_steam_running():
        console.print("\n[bold red]O Steam esta aberto.[/bold red] Feche o Steam antes de limpar.\n")
        return
    try:
        result = clean(settings)
    except SteamShortcutsError as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[bold]Atalhos removidos:[/bold] {result.removed}")


@cli.command(name="restore")
def restore_cmd() -> None:
    """Restaura o ultimo backup do shortcuts.vdf."""
    settings = get_settings()
    _configure_logging(settings)
    if is_steam_running():
        console.print("\n[bold red]O Steam esta aberto.[/bold red] Feche o Steam antes de restaurar.\n")
        return
    try:
        result = restore(settings)
    except SteamShortcutsError as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[bold green]Backup restaurado com sucesso:[/bold green] {result.backup_path}")


@cli.command(name="restore-backup")
def restore_backup_alias() -> None:
    """Alias para restore."""
    restore_cmd.callback()  # type: ignore[misc]


@cli.command()
def setup() -> None:
    """Configura a chave da SteamGridDB via terminal."""
    console.print(
        Panel(
            "Crie uma chave gratuita em [link=https://www.steamgriddb.com/profile/preferences/api]SteamGridDB Preferences > API[/link]",
            title="Configuracao de Capas",
            border_style="cyan",
        )
    )
    current = load_config_file()
    current_key = current.get("steamgriddb_api_key", "")
    api_key = click.prompt("Cole sua chave de API do SteamGridDB", default=current_key, show_default=False).strip()
    if api_key:
        current["steamgriddb_api_key"] = api_key
        save_config_file(current)
        console.print("[bold green]Chave salva com sucesso.[/bold green]")


@cli.command()
def gui() -> None:
    """Inicia a interface grafica de dois botoes."""
    from steam_epic_bridge.gui import run_gui

    run_gui()


if __name__ == "__main__":
    cli()
