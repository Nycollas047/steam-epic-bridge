import subprocess
from pathlib import Path


def build() -> None:
    print("Iniciando build comercial do Steam Epic Bridge (seb)...")
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    main_script = project_root / "SteamEpicBridge.py"

    if not main_script.exists():
        print(f"Erro: {main_script} nao encontrado.")
        return

    legendary_bin = project_root / "steam_epic_bridge" / "bin" / "legendary.exe"
    command = [
        "python", "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "SteamEpicBridge",
        "--hidden-import", "vdf",
        "--hidden-import", "psutil",
        "--hidden-import", "requests",
        "--hidden-import", "click",
        "--hidden-import", "rich",
        "--hidden-import", "PIL",
        "--collect-submodules", "legendary",
    ]
    if legendary_bin.exists():
        command.extend(["--add-binary", f"{legendary_bin};bin"])
    command.append(str(main_script))

    subprocess.run(command, check=True, cwd=str(project_root))
    print("\nBuild concluido com sucesso! Executavel gerado em 'dist/SteamEpicBridge.exe'.")


if __name__ == "__main__":
    build()
