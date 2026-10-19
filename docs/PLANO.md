# Plano de simplificação: steam-epic-bridge

Data da análise: 17/10/2026. Base: código do `projeto steam.zip` (3.439 linhas no pacote `steam_epic_bridge`, 30 testes).

## Status em 18/10/2026

O código foi reescrito seguindo este plano. As seções 1 a 3 abaixo descrevem o **estado anterior** e ficam como histórico.

| Item do plano | Situação no código | Observação |
|---|---|---|
| Motor único (CLI e GUI) | Feito (`cli.py`) | |
| `appid` estável (`crc32("epic-<app_name>")`) | Feito (`steam.py`), com migração das capas | Falta confirmar na Steam real que o valor é respeitado |
| Atalho único `seb launch` | Feito (`launcher.py`) | Não testado em máquina real; ver riscos abaixo |
| Sem `artwork_doctor`, `repair`, `reset_all` | Feito | |
| Filtros na origem do SteamGridDB | Feito (`build_steamgriddb_params`) | Nomes de parâmetros ainda não conferidos na documentação oficial |
| GUI de dois botões | Feita (`gui.py`) | |
| Testes | 37 passando (Linux, Python 3.13) | Faltam testes no Windows e em Steam real |
| **Spikes 0 a 4** | Scripts em `spikes/`, mas **sem teste real** | Ver [`spikes/README.md`](../spikes/README.md) |

Riscos novos vistos na revisão do código (não testados):
- **Build empacotado (PyInstaller):** com o módulo `legendary` instalado, o app usa `python -m legendary.cli`, que roda `sys.executable`. Dentro do `.exe` empacotado, `sys.executable` é o próprio app, então esse comando provavelmente não funciona. Conferir antes de distribuir.
- **Licença do Legendary (GPL-3.0):** `build.py` embute o módulo `legendary` no executável (`--collect-submodules legendary`). Isso muda o que é "redistribuir" e deve ser avaliado antes de qualquer venda.
- **Windows 10/11:** os caminhos `explorer.exe` e `cmd.exe` estão fixos em `C:\Windows`.

## 1. Estado anterior (histórico)

```
Epic (legendary.exe embutido) ──► epic_library ─┐
                                                ├─► sync.py (CLI)  ─┐  lógica duplicada
SteamGridDB ──► artwork ──► artwork_doctor      │   core.py (GUI)  ─┘  em dois lugares
                                                ▼
                         steam_shortcuts.py (VDF + launch por SO + reparo de imagens)
                                                ▼
                       shortcuts.vdf + grid/ (Steam precisa estar fechada)
```

## 2. Achados

| Achado | Evidência |
|---|---|
| Dois motores paralelos (`sync.py` na CLI, `core.py` na GUI) que já divergem | 371 linhas; só um baixa capas em paralelo e roda o reparo ao final |
| O `appid` depende de `exe + título`: mudar o caminho do legendary ou o título orfana as capas | `_unsigned_appid`. Boa parte do "reparo" existe por causa disso |
| Duplicatas checadas pelo título, não pelo `app_name`, embora a tag `epic-<app_name>` já exista | `add_games` |
| A GUI é 29% do pacote | 983 de 3.439 linhas |
| Conversão de ícone falha em silêncio: com Pillow 13, `sizes=[(256,256)]` gera erro em imagens menores que 256 px | Reproduzido; causa dos 2 testes que falham (28 de 30 passam) |
| Linux: o atalho chama `legendary launch` sem Wine/Proton; jogos não instalados usam `xdg-open com.epicgames.launcher://` e não há launcher da Epic nativo no Linux | Código + docs do Legendary. Provável falha, **ainda não testada** |
| `legendary.exe` de 8 MB embutido, enquanto o Legendary voltou a ser mantido (0.21.1 em set/2026) | Versão do binário embutido não identificada |
| `iniciar.sh/.bat` não criam venv, ao contrário do que o README diz; `pip --user` tende a falhar em distros recentes | |
| Sobras do modelo antigo: restos de RAWG/IGDB, cache do pytest com testes inexistentes, `pytest` em `requirements.txt` | |
| `pc-health-checker/` (1.047 linhas, 8 relatórios commitados) é outro projeto dentro do zip; não há LICENSE, apesar de o README citar | |

## 3. O que já existe no mercado

| Ferramenta | Cobertura |
|---|---|
| BoilR | Epic via Proton no Linux, capas SteamGridDB |
| Steam ROM Manager | Parser do Legendary no Windows, Linux e Mac |
| steamsync (Python, 2026) | Escaneia jogos instalados |
| Heroic | "Add to Steam" segundo o guia do GamingOnLinux |

Todos cobrem bem jogos instalados. **O diferencial do projeto é a biblioteca inteira, incluindo jogos não instalados:** clicar em Jogar na Steam instala e abre.

## 4. Arquitetura proposta

```
Steam clica "Jogar" ──► seb launch <app_name>   (único executável em todos os atalhos)
                          ├─ instalado?  sim ─► legendary launch (Wine/Proton) e espera o jogo fechar
                          └─              não ─► legendary install ─► launch

seb sync ──► epic.py (lista) ─► artwork.py (SteamGridDB) ─► steam.py (VDF + grid + backup)
```

| Módulo | Substitui | Observação |
|---|---|---|
| `epic.py` | `epic_auth` + `epic_library` | Depende de `legendary-gl>=0.21` via pip, sem `.exe` embutido |
| `steam.py` | `discovery` (parte Steam) + `steam_shortcuts` (núcleo) | Só VDF, backup, caminhos e "Steam aberta?" |
| `artwork.py` | `artwork` + `artwork_doctor` | Filtra a consulta na origem (poster vertical, resolução), sem "doctor" |
| `launcher.py` | Ramificações por SO em `_build_exe_and_launch` | Atalho igual no Windows e no Linux |
| `cli.py` | `main` + `sync` + `core` | Um só motor |

Ganhos: `appid` estável, mesmo caminho no Windows e no Linux, duplicata checada pela tag `epic-<app_name>`. Meta de tamanho (estimativa, não medida): 1.000 a 1.400 linhas.

## 5. Roadmap

| Fase | Entrega | Pronto quando |
|---|---|---|
| 0, higiene (feita no PR de preparação) | Árvore de código real no repo, `pc-health-checker` fora, LICENSE, README corrigido, CI | Repo clonável e `pytest` roda. Falta apenas a tag `v0-legacy` |
| 1, spikes | Validar as 4 suposições de risco (seção 6) | Cada uma com resultado sim/não anotado |
| 2, núcleo | `epic`, `steam`, `artwork` e CLI (`sync`, `--dry-run`, `status`, `clean`, `restore`), testes com respostas falsas da API | `sync` idempotente nas duas plataformas |
| 3, launcher e distribuição | `seb launch`, `.exe` no Windows (build via GitHub Actions), `uv tool install`/`pipx` no Linux | Instalar e jogar sem terminal além de um comando |
| 4, interface | Janela de dois botões (seção 10) sobre o mesmo motor da CLI | `Iniciar` faz sync + correção sem ajuda; `Configurações` cobre todo o setup |
| 5, opcionais | Timer (systemd/`schtasks`), Flatpak | Só se a Fase 4 estiver estável |

## 6. Spikes da Fase 1

0. **(novo, ver seção 11)** O launcher oficial da Epic para Linux registra o protocolo `com.epicgames.launcher://` e dá para disparar um jogo por linha de comando? Convive com o Legendary e com a Steam Flatpak?
1. O `seb launch` roda legendary com Wine/Proton a partir da Steam nativa e da Steam Flatpak, mantendo o processo vivo enquanto o jogo roda?
2. A Steam atual respeita um `appid` gravado explicitamente, desacoplado do caminho do executável?
3. A Steam aceita ícone `.png`? Se sim, saem o Pillow e todo o pipeline de `.ico`.
4. Login da Epic: janela do próprio Legendary (Windows 0.20.14+) ou webview opcional (0.21), contra o fluxo atual de colar o SID. O Legendary oferece `--code`, `--token` e `--sid`.

## 7. Cortes sugeridos

- `artwork_doctor`, `repair_library` e `reset_all` (perdem a razão de existir com `appid` estável).
- `scheduler` no v1: o sync exige Steam fechada, então agendar às 4h é frágil.
- `GameMetadata` e `pytest` dos requisitos de runtime.
- GUI de 983 linhas: reescrever do zero na Fase 4 como a janela de dois botões da seção 10, sem reaproveitar o código atual.

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Mudança no login ou na API da Epic | Fixar a versão do Legendary e rodar teste-fumaça no CI |
| `.exe` não assinado no Windows 11 | O SmartScreen pode alertar; documentar no README |
| Steam Flatpak não enxergar o shim e o legendary | Resolver no spike 1 |
| Anti-cheat (ex.: Fortnite) no Linux | Documentar como limitação |
| Limites da API do SteamGridDB | A documentação não carregou na análise; conferir limites e nomes dos parâmetros de filtro antes da Fase 2 |

## 9. Decisões em aberto

- Manter o diferencial de jogos não instalados (exige o fluxo de instalação no `launch`)?
- GUI: decidido, janela de dois botões (seção 10). Falta escolher o toolkit.
- Depois do spike 0: o launcher oficial vira o backend padrão no Linux, ou o Legendary continua como padrão?
- Idioma do README: por ora, pt-BR com um resumo em inglês no topo. Vale revisar se o público for internacional.

O projeto tem 0 estrelas e 0 forks, então não há usuários para migrar: basta `clean` e `sync`.

## 10. Design do app: dois botões

Referência visual: cartão escuro semitransparente (efeito vidro) com cantos bem arredondados e borda fina, sobre fundo desfocado em gradiente roxo/azul/verde-água. Dois botões lado a lado, centralizados:

| | Esquerda | Direita |
|---|---|---|
| Texto e ícone | engrenagem + **Configurações** | play + **Iniciar** |
| Estilo | cinza translúcido (secundário) | azul sólido (primário, única cor saturada) |
| Papel | onde tudo se configura | aplica e corrige |

### Como o app se encaixa no motor

```
[ Configurações ] ──► lê/grava config.json ─┐
                                            ├─► mesmo motor da CLI (epic, steam, artwork)
[ Iniciar ]       ──► seb sync ─────────────┘
```

A janela não tem lógica própria: `Iniciar` chama o mesmo `seb sync` da CLI, e `Configurações` edita o mesmo arquivo de configuração. Assim CLI e janela nunca divergem, o problema atual de `sync.py` contra `core.py`.

### Configurações (tudo em um lugar, valores detectados automaticamente)

| Seção | Conteúdo |
|---|---|
| Steam | Pasta e usuário detectados; campo para corrigir à mão |
| Epic | Entrar / sair da conta |
| Capas | Chave do SteamGridDB, estilo preferido |
| Como jogar | Launcher oficial ou Legendary (depende do spike 0) |
| Manutenção | Pré-visualizar (dry-run), restaurar backup, remover atalhos da Epic |
| Geral | Idioma |

Abre na mesma janela, com botão de voltar. Nenhum botão extra na tela principal: desfazer e pré-visualizar ficam aqui dentro.

### Iniciar (aplica e corrige, em uma operação)

1. Confere o ambiente: Steam fechada (se não, pede para fechar), conta Epic conectada (se não, leva a Configurações > Epic), chave de capas (se faltar, segue sem capas e avisa).
2. Faz backup do `shortcuts.vdf`.
3. Lê a biblioteca da Epic.
4. Cria os atalhos novos.
5. Corrige os existentes: caminho ou comando de launch desatualizado, capas faltando.
6. Mostra o resumo no próprio cartão, por exemplo "12 novos, 3 corrigidos, 2 sem capa. Reabra a Steam."

Rodar de novo é seguro (idempotente). Isso só funciona com o `appid` estável da seção 4; sem ele, "corrigir" volta a ser um botão separado.

Estados do botão: pronto, em andamento (barra de progresso), concluído, precisa de atenção (leva à seção certa de Configurações). Uma linha de status sob os botões é adição minha, não aparece na referência; é opcional.

### Toolkit (decisão aberta)

O efeito vidro/desfoque real não é possível no Tkinter. Opções, não testadas nesta análise:

| Opção | Prós | Contras |
|---|---|---|
| Tkinter, aproximação plana (cores sólidas + fundo em gradiente estático) | Já vem com o Python; empacotamento leve | Não tem desfoque de verdade |
| Qt (PySide6) | Continua tudo em Python; visual mais próximo | Dependência maior; empacotamento mais pesado |
| Tauri/Electron | Visual mais livre | Segundo ecossistema (Rust/JS) para manter |

Antes de decidir, conferir se o desfoque funciona no Windows 11 e nos compositores do Linux (KDE, GNOME), o que não foi verificado.

## 11. Launcher oficial da Epic no Linux

Em 14/10/2026 a Epic lançou o novo launcher em Preview, com versão nativa para Linux.

| Item | Situação |
|---|---|
| Distros suportadas | Ubuntu 22.04+, Fedora 43+, Debian 12+ |
| Jogos só de Windows | Rodam por GE-Proton, gerenciado pelo launcher |
| Instalação | Pelo site da Epic; segundo um artigo, remove o launcher existente |
| Steam Deck/SteamOS | Em aberto, sem prazo |
| Fortnite | Planejado, sem data (depende do anti-cheat EAC Linux v2) |
| Estado | Preview, sem data para a versão estável |

Efeito no plano: o trabalho de rodar jogo Windows no Linux e instalar jogo não instalado pode passar ao launcher oficial. O Legendary continua útil para listar a biblioteca sem interface e para o Steam Deck.

```
Steam ► seb launch ► ?  ┬─ launcher oficial (traz Proton, instala o jogo)
                        └─ Legendary (distros fora da lista, Steam Deck)
```

Incógnitas (viram o spike 0): protocolo `com.epicgames.launcher://` no Linux, disparo por linha de comando, convivência com o launcher antigo e com o Legendary, funcionamento na Steam Flatpak.

## Fontes

- [Epic Games Launcher Preview Adds Linux, Fortnite to Follow](https://godisageek.com/2026/10/epic-games-launcher-linux/)
- [Epic Games Launcher for Linux: New Preview Brings Fortnite's Path and AI-Built Client](https://www.linuxcompatible.org/story/epic-games-launcher-for-linux-new-preview-brings-fortnites-path-and-aibuilt-client)

- [legendary-gl no PyPI (0.21.1, set/2026)](https://pypi.org/project/legendary-gl/)
- [Legendary v0.21.0 volta a ser mantido](https://www.linuxcompatible.org/story/legendary-v0210-revives-the-opensource-epic-games-launcher-replacement/)
- [Repositório do Legendary](https://github.com/legendary-gl/legendary)
- [BoilR](https://github.com/cncz42/BoilR)
- [Steam ROM Manager](https://github.com/SteamGridDB/steam-rom-manager)
- [steamsync](https://pypi.org/project/steamsync)
- [Heroic Games Launcher](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher)
- [GamingOnLinux: Epic e GOG no Linux e Steam Deck](https://gamingonlinux.com/guides/view/how-to-play-games-from-gog-and-epic-games-on-linux-steamos-and-steam-deck)
