from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFilter, ImageTk

from steam_epic_bridge.cli import clean, restore, sync_library
from steam_epic_bridge.config import get_settings, load_config_file, save_config_file
from steam_epic_bridge.epic import EPIC_AUTH_REDIRECT_URL, get_account, login, logout
from steam_epic_bridge.models import SyncResult
from steam_epic_bridge.steam import existing_shortcuts_count, is_steam_running


_STRINGS: dict[str, dict[str, str]] = {
    "pt-BR": {
        "subtitle": "Sua biblioteca Epic inteira pronta para jogar na Steam",
        "settings_btn": "⚙  Configurações",
        "start_btn": "▶  Iniciar",
        "running_btn": "⏳  Sincronizando...",
        "ready": "Pronto para sincronizar e corrigir sua biblioteca.",
        "steam_open": "Atenção: Feche a Steam completamente antes de iniciar.",
        "epic_missing": "Conecte sua conta Epic para continuar.",
        "no_key_warn": "Sem chave SteamGridDB (sincronizando sem capas)...",
        "back_btn": "← Voltar",
        "save_btn": "Salvar Configurações",
        "saved_msg": "Configurações salvas com sucesso.",
        "disconnected": "Desconectada",
        "shortcuts_lbl": "Atalhos na Steam",
        "checking": "Verificando...",
        "connected_as": "Conectado",
        "not_connected": "Não conectado",
        "browse_btn": "Procurar",
    },
    "en": {
        "subtitle": "Your entire Epic library ready to play on Steam",
        "settings_btn": "⚙  Settings",
        "start_btn": "▶  Start",
        "running_btn": "⏳  Syncing...",
        "ready": "Ready to sync and repair your library.",
        "steam_open": "Warning: Close Steam completely before starting.",
        "epic_missing": "Connect your Epic account to continue.",
        "no_key_warn": "No SteamGridDB key (syncing without covers)...",
        "back_btn": "← Back",
        "save_btn": "Save Settings",
        "saved_msg": "Settings saved successfully.",
        "disconnected": "Disconnected",
        "shortcuts_lbl": "Steam Shortcuts",
        "checking": "Checking...",
        "connected_as": "Connected",
        "not_connected": "Not connected",
        "browse_btn": "Browse",
    },
}


def _render_glass_background(width: int, height: int, card_box: tuple[int, int, int, int]) -> Image.Image:
    """Gera fundo desfocado em gradiente roxo/azul/verde-água e compõe o cartão escuro com efeito vidro."""
    base = Image.new("RGBA", (width, height), (13, 15, 26, 255))
    draw = ImageDraw.Draw(base)

    # Bolhas de cor suave (roxo, azul profundo, verde-água) para desfoque gaussiano
    draw.ellipse((-80, -60, int(width * 0.65), int(height * 0.75)), fill=(98, 42, 168, 210))
    draw.ellipse((int(width * 0.25), int(height * 0.10), width + 60, height + 60), fill=(24, 92, 195, 210))
    draw.ellipse((int(width * 0.15), int(height * 0.45), int(width * 0.85), height + 90), fill=(16, 155, 148, 185))

    blurred = base.filter(ImageFilter.GaussianBlur(radius=55))

    # Camada escura geral para contraste elegante
    overlay = Image.new("RGBA", (width, height), (10, 12, 20, 135))
    composed = Image.alpha_composite(blurred, overlay)

    # Cartão central semitransparente (efeito vidro) com cantos bem arredondados e borda fina
    card_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_layer)
    card_draw.rounded_rectangle(
        card_box,
        radius=28,
        fill=(18, 21, 32, 205),
        outline=(255, 255, 255, 42),
        width=1,
    )
    return Image.alpha_composite(composed, card_layer)


class BridgeGUI:
    WIDTH = 640
    HEIGHT = 420

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Steam Epic Bridge")
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(background="#0d0f1a")

        self.settings = get_settings()
        self._busy = False
        self._bg_photo: ImageTk.PhotoImage | None = None

        self._setup_styles()
        self._build_main_view()
        self._build_settings_view()
        self._show_main_view()

    def _t(self, key: str) -> str:
        lang = self.settings.language if self.settings.language in _STRINGS else "pt-BR"
        return _STRINGS[lang].get(key, _STRINGS["pt-BR"][key])

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        bg = "#141826"
        fg = "#f1f5f9"
        accent = "#2563eb"
        border = "#2d3548"

        style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 9))
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Section.TLabel", background=bg, foreground="#60a5fa", font=("Segoe UI", 9, "bold"))
        style.configure("Muted.TLabel", background=bg, foreground="#94a3b8", font=("Segoe UI", 8))
        style.configure(
            "Secondary.TButton",
            background="#262c3d",
            foreground="#e2e8f0",
            bordercolor="#3b445e",
            padding=(10, 5),
            font=("Segoe UI", 9),
        )
        style.map("Secondary.TButton", background=[("active", "#323a50")])
        style.configure(
            "Primary.TButton",
            background=accent,
            foreground="#ffffff",
            bordercolor=accent,
            padding=(12, 6),
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        style.configure(
            "TEntry",
            fieldbackground="#0d101b",
            foreground=fg,
            bordercolor=border,
            insertcolor=fg,
            padding=4,
        )
        style.configure("TCheckbutton", background=bg, foreground=fg, indicatorbackground="#0d101b")
        style.map(
            "TCheckbutton",
            background=[("active", bg)],
            foreground=[("active", "#60a5fa")],
            indicatorcolor=[("selected", accent), ("!selected", "#0d101b")],
        )

        style.configure(
            "TCombobox",
            fieldbackground="#0d101b",
            background="#262c3d",
            foreground=fg,
            bordercolor=border,
            arrowcolor=fg,
            padding=4,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#0d101b"), ("!disabled", "#0d101b")],
            selectbackground=[("readonly", "#0d101b")],
            selectforeground=[("readonly", fg)],
            background=[("readonly", "#262c3d"), ("active", "#323a50")],
            foreground=[("readonly", fg)],
            bordercolor=[("focus", accent)],
        )
        self.root.option_add("*TCombobox*Listbox.background", "#0d101b")
        self.root.option_add("*TCombobox*Listbox.foreground", fg)
        self.root.option_add("*TCombobox*Listbox.selectBackground", accent)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    # ========================================================================
    # TELA PRINCIPAL: CARTÃO DE VIDRO COM DOIS BOTÕES (Configurações | Iniciar)
    # ========================================================================

    def _build_main_view(self) -> None:
        self.main_canvas = tk.Canvas(
            self.root,
            width=self.WIDTH,
            height=self.HEIGHT,
            highlightthickness=0,
            bd=0,
        )
        card_box = (55, 50, self.WIDTH - 55, self.HEIGHT - 50)
        bg_image = _render_glass_background(self.WIDTH, self.HEIGHT, card_box)
        self._bg_photo = ImageTk.PhotoImage(bg_image)
        self.main_canvas.create_image(0, 0, image=self._bg_photo, anchor="nw")

        cx = self.WIDTH // 2

        # Título e subtítulo dentro do cartão
        self.main_canvas.create_text(
            cx,
            108,
            text="Steam Epic Bridge",
            fill="#f8fafc",
            font=("Segoe UI", 20, "bold"),
        )
        self.subtitle_item = self.main_canvas.create_text(
            cx,
            140,
            text=self._t("subtitle"),
            fill="#94a3b8",
            font=("Segoe UI", 10),
        )
        self.counts_item = self.main_canvas.create_text(
            cx,
            168,
            text="",
            fill="#cbd5e1",
            font=("Segoe UI", 9),
        )

        # Dois botões centralizados lado a lado (Esquerda: Configurações | Direita: Iniciar)
        self._draw_canvas_buttons()

        # Barra de progresso discreta desenhada no Canvas
        self.prog_bg = self.main_canvas.create_rectangle(
            120, 294, self.WIDTH - 120, 300, fill="#1e2436", outline="", state="hidden"
        )
        self.prog_fg = self.main_canvas.create_rectangle(
            120, 294, 120, 300, fill="#3b82f6", outline="", state="hidden"
        )

        # Linha de status sob os botões
        self.status_item = self.main_canvas.create_text(
            cx,
            325,
            text=self._t("ready"),
            fill="#cbd5e1",
            font=("Segoe UI", 9),
            width=480,
            justify="center",
        )

        self.root.bind("<Return>", lambda _e: self._on_start_clicked() if not self._busy else None)

    def _draw_canvas_buttons(self) -> None:
        # Botão Esquerdo: engrenagem + Configurações (cinza translúcido secundário)
        self.btn_cfg_rect = self._create_rounded_rect(
            self.main_canvas, 120, 206, 308, 262, radius=14, fill="#282e42", outline="#3e4763"
        )
        self.btn_cfg_text = self.main_canvas.create_text(
            214, 234, text=self._t("settings_btn"), fill="#e2e8f0", font=("Segoe UI", 11, "bold")
        )
        for item in (self.btn_cfg_rect, self.btn_cfg_text):
            self.main_canvas.tag_bind(item, "<Button-1>", lambda _e: not self._busy and self._show_settings_view())
            self.main_canvas.tag_bind(
                item, "<Enter>", lambda _e: self.main_canvas.itemconfigure(self.btn_cfg_rect, fill="#323952")
            )
            self.main_canvas.tag_bind(
                item, "<Leave>", lambda _e: self.main_canvas.itemconfigure(self.btn_cfg_rect, fill="#282e42")
            )

        # Botão Direito: play + Iniciar (azul sólido primário, única cor saturada)
        self.btn_start_rect = self._create_rounded_rect(
            self.main_canvas, 332, 206, 520, 262, radius=14, fill="#2563eb", outline="#3b82f6"
        )
        self.btn_start_text = self.main_canvas.create_text(
            426, 234, text=self._t("start_btn"), fill="#ffffff", font=("Segoe UI", 11, "bold")
        )
        for item in (self.btn_start_rect, self.btn_start_text):
            self.main_canvas.tag_bind(item, "<Button-1>", lambda _e: self._on_start_clicked())
            self.main_canvas.tag_bind(
                item,
                "<Enter>",
                lambda _e: not self._busy and self.main_canvas.itemconfigure(self.btn_start_rect, fill="#1d4ed8"),
            )
            self.main_canvas.tag_bind(
                item,
                "<Leave>",
                lambda _e: not self._busy and self.main_canvas.itemconfigure(self.btn_start_rect, fill="#2563eb"),
            )

    @staticmethod
    def _create_rounded_rect(
        canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int = 14, **kwargs
    ) -> int:
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _set_status(self, text: str, color: str = "#cbd5e1") -> None:
        self.main_canvas.itemconfigure(self.status_item, text=text, fill=color)

    def _set_progress(self, percent: float | None) -> None:
        if percent is None:
            self.main_canvas.itemconfigure(self.prog_bg, state="hidden")
            self.main_canvas.itemconfigure(self.prog_fg, state="hidden")
            return
        self.main_canvas.itemconfigure(self.prog_bg, state="normal")
        self.main_canvas.itemconfigure(self.prog_fg, state="normal")
        total_w = (self.WIDTH - 120) - 120
        fill_x = 120 + int(total_w * max(0.0, min(1.0, percent / 100.0)))
        self.main_canvas.coords(self.prog_fg, 120, 294, fill_x, 300)

    def _refresh_header_counts(self) -> None:
        def worker() -> None:
            self.settings = get_settings()
            try:
                shortcuts = existing_shortcuts_count(self.settings)
            except Exception:
                shortcuts = 0
            acc = get_account(self.settings) or self._t("disconnected")
            summary = f"Epic: {acc}   •   {self._t('shortcuts_lbl')}: {shortcuts}"
            self.root.after(0, lambda: self.main_canvas.itemconfigure(self.counts_item, text=summary))

        threading.Thread(target=worker, daemon=True).start()

    # ========================================================================
    # FLUXO DO BOTÃO "INICIAR" (Seção 10 do plano.md)
    # ========================================================================

    def _on_start_clicked(self) -> None:
        if self._busy:
            return
        self.settings = get_settings()

        # 1. Confere se a Steam está fechada
        if is_steam_running():
            self._set_status(self._t("steam_open"), color="#f87171")
            messagebox.showwarning("Steam Aberta", "Feche a Steam completamente antes de sincronizar.")
            return

        # 2. Muda o estado visual imediatamente para resposta instantânea
        self._busy = True
        self.main_canvas.itemconfigure(self.btn_start_rect, fill="#1e40af")
        self.main_canvas.itemconfigure(self.btn_start_text, text=self._t("running_btn"))
        self._set_progress(5)

        if not self.settings.steamgriddb_api_key:
            self._set_status(self._t("no_key_warn"), color="#fbbf24")
        else:
            self._set_status("Lendo biblioteca da Epic e criando backup...", color="#93c5fd")

        def progress_cb(title: str, current: int, total: int) -> None:
            pct = 10 + int((current / max(total, 1)) * 85)
            self.root.after(0, lambda: self._set_progress(pct))
            self.root.after(0, lambda: self._set_status(f"{title} ({current}/{total})", color="#cbd5e1"))

        def worker() -> None:
            account = get_account(self.settings)
            if not account:
                self.root.after(0, self._on_epic_missing)
                return
            try:
                result = sync_library(self.settings, progress_callback=progress_cb)
                self.root.after(0, lambda r=result: self._on_sync_done(r))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self._on_sync_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_epic_missing(self) -> None:
        self._busy = False
        self.main_canvas.itemconfigure(self.btn_start_rect, fill="#2563eb")
        self.main_canvas.itemconfigure(self.btn_start_text, text=self._t("start_btn"))
        self._set_progress(None)
        self._set_status(self._t("epic_missing"), color="#fbbf24")
        self._show_settings_view(focus_epic=True)

    def _on_sync_done(self, result: SyncResult) -> None:
        self._busy = False
        self.main_canvas.itemconfigure(self.btn_start_rect, fill="#2563eb")
        self.main_canvas.itemconfigure(self.btn_start_text, text=self._t("start_btn"))
        self._set_progress(100)
        summary = (
            f"{result.created} novos, {result.updated} corrigidos, "
            f"{result.missing_artwork} sem capa. Reabra a Steam."
        )
        self._set_status(summary, color="#4ade80")
        self._refresh_header_counts()

    def _on_sync_error(self, exc: Exception) -> None:
        self._busy = False
        self.main_canvas.itemconfigure(self.btn_start_rect, fill="#2563eb")
        self.main_canvas.itemconfigure(self.btn_start_text, text=self._t("start_btn"))
        self._set_progress(None)
        self._set_status(f"Erro: {exc}", color="#f87171")

    # ========================================================================
    # TELA DE CONFIGURAÇÕES (abre na mesma janela, com botão Voltar)
    # ========================================================================

    def _build_settings_view(self) -> None:
        self.settings_frame = ttk.Frame(self.root, padding="18 14")

        # Cabeçalho com botão Voltar e Salvar
        top_bar = ttk.Frame(self.settings_frame)
        top_bar.pack(fill=tk.X, pady=(0, 10))
        self.back_btn = ttk.Button(
            top_bar, text=self._t("back_btn"), style="Secondary.TButton", command=self._show_main_view
        )
        self.back_btn.pack(side=tk.LEFT)
        ttk.Label(top_bar, text="Configurações", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT, padx=12)
        self.save_btn = ttk.Button(
            top_bar, text=self._t("save_btn"), style="Primary.TButton", command=self._save_settings
        )
        self.save_btn.pack(side=tk.RIGHT)

        # 1. Steam
        ttk.Label(self.settings_frame, text="Steam", style="Section.TLabel").pack(anchor=tk.W, pady=(4, 2))
        steam_row = ttk.Frame(self.settings_frame)
        steam_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(steam_row, text="Pasta:").pack(side=tk.LEFT)
        self.steam_root_var = tk.StringVar(value=str(self.settings.steam_root))
        ttk.Entry(steam_row, textvariable=self.steam_root_var, width=29).pack(side=tk.LEFT, padx=(6, 4))
        ttk.Button(
            steam_row, text=self._t("browse_btn"), style="Secondary.TButton", command=self._browse_steam_root
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(steam_row, text="User ID:").pack(side=tk.LEFT)
        self.steam_uid_var = tk.StringVar(value=self.settings.steam_user_id or "")
        ttk.Entry(steam_row, textvariable=self.steam_uid_var, width=12).pack(side=tk.LEFT, padx=(6, 0))

        # 2. Epic Games
        ttk.Label(self.settings_frame, text="Conta Epic Games", style="Section.TLabel").pack(anchor=tk.W, pady=(4, 2))
        epic_row = ttk.Frame(self.settings_frame)
        epic_row.pack(fill=tk.X, pady=(0, 6))
        self.epic_status_var = tk.StringVar(value=self._t("checking"))
        ttk.Label(epic_row, textvariable=self.epic_status_var).pack(side=tk.LEFT)
        ttk.Button(
            epic_row, text="Sair", style="Secondary.TButton", command=self._do_epic_logout
        ).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(
            epic_row, text="Entrar via Navegador", style="Secondary.TButton", command=self._open_epic_code_modal
        ).pack(side=tk.RIGHT, padx=(4, 0))
        self.import_egl_btn = ttk.Button(
            epic_row, text="Importar do Epic Launcher", style="Primary.TButton", command=self._do_epic_import
        )
        self.import_egl_btn.pack(side=tk.RIGHT)

        # 3. Capas (SteamGridDB)
        ttk.Label(self.settings_frame, text="Capas (SteamGridDB)", style="Section.TLabel").pack(anchor=tk.W, pady=(4, 2))
        art_row = ttk.Frame(self.settings_frame)
        art_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(art_row, text="Chave API:").pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value=self.settings.steamgriddb_api_key or "")
        ttk.Entry(art_row, textvariable=self.api_key_var, show="*", width=26).pack(side=tk.LEFT, padx=(6, 8))
        ttk.Button(
            art_row,
            text="Pegar Chave Grátis",
            style="Secondary.TButton",
            command=lambda: webbrowser.open("https://www.steamgriddb.com/profile/preferences/api"),
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(art_row, text="Estilo:").pack(side=tk.LEFT)
        self.style_var = tk.StringVar(value=self.settings.artwork_style)
        ttk.Combobox(
            art_row,
            textvariable=self.style_var,
            values=["any", "alternate", "blurred", "white_logo", "material", "no_logo", "minimal"],
            width=10,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(4, 0))

        # 4. Como jogar & Geral
        ttk.Label(self.settings_frame, text="Como Jogar & Geral", style="Section.TLabel").pack(anchor=tk.W, pady=(4, 2))
        play_row = ttk.Frame(self.settings_frame)
        play_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(play_row, text="Backend:").pack(side=tk.LEFT)
        self.backend_var = tk.StringVar(value=self.settings.launch_backend)
        ttk.Combobox(
            play_row,
            textvariable=self.backend_var,
            values=["legendary", "epic_launcher"],
            width=14,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(6, 14))
        self.animated_var = tk.BooleanVar(value=self.settings.prefer_animated)
        ttk.Checkbutton(play_row, text="Capas animadas", variable=self.animated_var).pack(side=tk.LEFT, padx=(0, 14))
        ttk.Label(play_row, text="Idioma:").pack(side=tk.LEFT)
        self.lang_var = tk.StringVar(value=self.settings.language)
        ttk.Combobox(
            play_row, textvariable=self.lang_var, values=["pt-BR", "en"], width=7, state="readonly"
        ).pack(side=tk.LEFT, padx=(4, 0))

        # 5. Manutenção (dry-run, restaurar backup, remover atalhos)
        ttk.Label(self.settings_frame, text="Manutenção", style="Section.TLabel").pack(anchor=tk.W, pady=(6, 2))
        maint_row = ttk.Frame(self.settings_frame)
        maint_row.pack(fill=tk.X, pady=(2, 0))
        ttk.Button(
            maint_row, text="Pré-visualizar (Dry-Run)", style="Secondary.TButton", command=self._run_dry_run
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(
            maint_row, text="Restaurar Backup", style="Secondary.TButton", command=self._run_restore
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(
            maint_row, text="Remover Atalhos da Epic", style="Secondary.TButton", command=self._run_clean
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _browse_steam_root(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.steam_root_var.get() or None, title="Selecione a pasta da Steam")
        if chosen:
            self.steam_root_var.set(chosen)

    def _show_main_view(self) -> None:
        self.settings_frame.pack_forget()
        self.main_canvas.pack(fill=tk.BOTH, expand=True)
        self._refresh_header_counts()

    def _show_settings_view(self, focus_epic: bool = False) -> None:
        self.main_canvas.pack_forget()
        self.settings = get_settings()
        self.steam_root_var.set(str(self.settings.steam_root))
        self.steam_uid_var.set(self.settings.steam_user_id or "")
        self.api_key_var.set(self.settings.steamgriddb_api_key or "")
        self.style_var.set(self.settings.artwork_style)
        self.backend_var.set(self.settings.launch_backend)
        self.animated_var.set(self.settings.prefer_animated)
        self.lang_var.set(self.settings.language)
        self.settings_frame.pack(fill=tk.BOTH, expand=True)
        self._refresh_epic_account_label()
        if focus_epic:
            self.import_egl_btn.focus_set()

    def _refresh_epic_account_label(self) -> None:
        self.epic_status_var.set(self._t("checking"))

        def worker() -> None:
            acc = get_account(self.settings)
            label = f"{self._t('connected_as')}: {acc}" if acc else self._t("not_connected")
            self.root.after(0, lambda: self.epic_status_var.set(label))

        threading.Thread(target=worker, daemon=True).start()

    def _save_settings(self) -> None:
        cfg = load_config_file()
        cfg["steam_root"] = self.steam_root_var.get().strip()
        cfg["steam_user_id"] = self.steam_uid_var.get().strip()
        cfg["steamgriddb_api_key"] = self.api_key_var.get().strip()
        cfg["artwork_style"] = self.style_var.get()
        cfg["launch_backend"] = self.backend_var.get()
        cfg["prefer_animated"] = bool(self.animated_var.get())
        cfg["language"] = self.lang_var.get()
        save_config_file(cfg)
        self.settings = get_settings()
        self.main_canvas.itemconfigure(self.subtitle_item, text=self._t("subtitle"))
        self.main_canvas.itemconfigure(self.btn_cfg_text, text=self._t("settings_btn"))
        self.main_canvas.itemconfigure(self.btn_start_text, text=self._t("start_btn"))
        self.back_btn.configure(text=self._t("back_btn"))
        self.save_btn.configure(text=self._t("save_btn"))
        self._set_status(self._t("saved_msg"), color="#4ade80")
        self._show_main_view()

    def _do_epic_import(self) -> None:
        self.epic_status_var.set("Importando...")

        def worker() -> None:
            try:
                acc = login(self.settings, import_egl=True)
                self.root.after(0, self._refresh_epic_account_label)
                self.root.after(
                    0, lambda: messagebox.showinfo("Conta Conectada", f"Conta Epic '{acc}' importada com sucesso!")
                )
            except Exception as exc:
                self.root.after(0, self._refresh_epic_account_label)
                self.root.after(
                    0,
                    lambda e=exc: messagebox.showwarning(
                        "Importação",
                        f"Não foi possível importar automaticamente ({e}).\nUse 'Entrar via Navegador'.",
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _open_epic_code_modal(self) -> None:
        webbrowser.open(EPIC_AUTH_REDIRECT_URL)
        dialog = tk.Toplevel(self.root)
        dialog.title("Conectar Conta Epic")
        dialog.geometry("440x210")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(background="#141826")

        frame = ttk.Frame(dialog, padding="16")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text=(
                "1. Faça login na página da Epic que abriu no navegador.\n"
                "2. Copie o texto exibido (authorizationCode) e cole abaixo:"
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 10))
        code_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=code_var)
        entry.pack(fill=tk.X, pady=(0, 14))
        entry.focus_set()

        def submit() -> None:
            raw = code_var.get().strip()
            if not raw:
                return
            try:
                acc = login(self.settings, code=raw)
                dialog.destroy()
                self._refresh_epic_account_label()
                messagebox.showinfo("Sucesso", f"Conectado como {acc}!")
            except Exception as exc:
                messagebox.showerror("Erro no Login", str(exc))

        entry.bind("<Return>", lambda _e: submit())
        ttk.Button(frame, text="Confirmar e Conectar", style="Primary.TButton", command=submit).pack(fill=tk.X)

    def _do_epic_logout(self) -> None:
        def worker() -> None:
            logout(self.settings)
            self.root.after(0, self._refresh_epic_account_label)

        threading.Thread(target=worker, daemon=True).start()

    def _run_dry_run(self) -> None:
        def worker() -> None:
            try:
                res = sync_library(self.settings, dry_run=True)
                self.root.after(
                    0,
                    lambda r=res: messagebox.showinfo(
                        "Pré-visualização (Dry-Run)",
                        f"Novos atalhos que seriam criados: {r.planned}\nAtalhos já existentes: {r.skipped}",
                    ),
                )
            except Exception as exc:
                self.root.after(0, lambda e=exc: messagebox.showerror("Dry-Run", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _run_restore(self) -> None:
        if is_steam_running():
            messagebox.showwarning("Steam Aberta", "Feche a Steam antes de restaurar o backup.")
            return
        try:
            res = restore(self.settings)
            messagebox.showinfo("Backup Restaurado", f"Restaurado de:\n{res.backup_path}")
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))

    def _run_clean(self) -> None:
        if is_steam_running():
            messagebox.showwarning("Steam Aberta", "Feche a Steam antes de remover os atalhos.")
            return
        if not messagebox.askyesno("Confirmar", "Remover todos os atalhos e capas da Epic da Steam?"):
            return
        try:
            res = clean(self.settings)
            messagebox.showinfo("Concluído", f"{res.removed} atalhos da Epic removidos.")
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))


def run_gui() -> None:
    import sys

    root = tk.Tk()
    app = BridgeGUI(root)
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = max(0, (sw - app.WIDTH) // 2)
    y = max(0, (sh - app.HEIGHT) // 2)
    root.geometry(f"{app.WIDTH}x{app.HEIGHT}+{x}+{y}")
    root.deiconify()
    root.update_idletasks()

    if sys.platform == "win32":
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    root.lift()
    root.attributes("-topmost", True)
    root.after(500, lambda: root.attributes("-topmost", False))
    root.focus_force()
    root.mainloop()
