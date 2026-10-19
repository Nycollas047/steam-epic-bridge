# Steam Epic Bridge

**Organizador da biblioteca Epic Games na Steam.** Lê os jogos da sua conta Epic e cria atalhos na biblioteca da Steam, com capa, banner, logo e ícone (via SteamGridDB), para você jogar tudo a partir de um só lugar.

*English: syncs your Epic Games Store library into Steam as non-Steam shortcuts, with artwork from SteamGridDB. Windows and Linux (Linux is experimental).*

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Windows | Linux](https://img.shields.io/badge/Plataformas-Windows%20%7C%20Linux-0078D6?style=flat-square)
![Testes](https://github.com/Nycollas047/steam-epic-bridge/actions/workflows/ci.yml/badge.svg)

> **Status: versão 0.2, em desenvolvimento.** Testada em Linux apenas por testes automatizados; ainda falta validar na Steam real (Windows 11, Linux, Steam Deck). Veja o que está pendente em [`docs/PLANO.md`](docs/PLANO.md).
> Não é afiliado à Epic Games nem à Valve. "Epic Games" e "Steam" são marcas dos respectivos donos.

## O que faz

- **Dois botões.** `⚙ Configurações` reúne todo o setup (conta Epic, chave de capas, opções). `▶ Iniciar` cria os atalhos novos e corrige os existentes em uma única operação, que pode ser repetida com segurança.
- **Biblioteca inteira,** com jogos instalados e não instalados.
- **Capas automáticas** (poster vertical, banner, logo e ícone) pelo SteamGridDB.
- **Atalho estável.** O identificador de cada atalho depende só do jogo (`epic-<app_name>`), então mover o programa ou renomear o jogo não perde as capas.
- **Backup** do `shortcuts.vdf` antes de cada alteração, com comando para restaurar.
- **Linha de comando** (`seb`) com o mesmo motor da janela.

## Como funciona

```
Configurações ─► config.json ─┐
                              ├─► motor único (cli.py)
Iniciar ───────► sync ────────┘        │
                                       ├─ epic.py      lê a biblioteca (via Legendary)
                                       ├─ artwork.py   baixa capas (SteamGridDB)
                                       └─ steam.py     grava shortcuts.vdf e a pasta grid

Na Steam, clicar em Jogar ─► seb launch <jogo>   (launcher.py)
     instalado     ─► inicia o jogo
     não instalado ─► abre a instalação no launcher da Epic
```

O atalho único `seb launch` é usado pelo executável empacotado. Rodando pelo código-fonte, o atalho chama o Legendary (ou o launcher da Epic) diretamente.

A Steam precisa estar **fechada** durante o sync.

## Instalação rápida

Requer Python 3.10 ou superior.

| Sistema | Passo |
|---|---|
| Windows 11 | Dê dois cliques em `iniciar.bat` |
| Linux / Steam Deck (experimental) | `chmod +x iniciar.sh && ./iniciar.sh` |

`iniciar.sh` cria um ambiente virtual `.venv`; `iniciar.bat` instala no Python do sistema. Ambos instalam as dependências (incluindo o `legendary-gl`) e abrem a janela. Guia completo: [`docs/COMO_USAR.md`](docs/COMO_USAR.md).

Pela linha de comando (depois de `pip install -e .`, o comando é `seb`):

```bash
python SteamEpicBridge.py sync --dry-run   # mostra o que seria criado, sem alterar nada
python SteamEpicBridge.py sync             # cria e corrige os atalhos (feche a Steam antes)
python SteamEpicBridge.py status           # resumo da conta e dos atalhos
python SteamEpicBridge.py doctor           # diagnóstico do ambiente
python SteamEpicBridge.py restore          # volta o último backup do shortcuts.vdf
python SteamEpicBridge.py clean            # remove os atalhos criados pelo app
```

## Chave do SteamGridDB (para as capas)

1. Crie uma conta gratuita em [steamgriddb.com](https://www.steamgriddb.com).
2. Em **Preferences > API**, gere uma chave.
3. Cole a chave em `⚙ Configurações` (ou rode `python SteamEpicBridge.py setup`).

## Para quem quer opinar

Toda ajuda começa por uma conversa, não por código:

| Quero... | Vá para |
|---|---|
| Sugerir uma ideia ou melhoria | [Nova sugestão](https://github.com/Nycollas047/steam-epic-bridge/issues/new?template=sugestao.yml) |
| Reportar um erro | [Novo relato de erro](https://github.com/Nycollas047/steam-epic-bridge/issues/new?template=erro.yml) |
| Testar na sua máquina e contar o resultado | Veja as perguntas em aberto em [`spikes/README.md`](spikes/README.md) |
| Comentar o plano e as decisões em aberto | Comente nas issues ou em [`docs/PLANO.md`](docs/PLANO.md) |
| Enviar código | Leia [`CONTRIBUTING.md`](CONTRIBUTING.md) antes |

## Desenvolvimento

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest tests -v
```

Estrutura:

```
steam_epic_bridge/   código (CLI, janela, Epic, Steam, capas, launcher)
tests/               testes automatizados
spikes/              investigações técnicas (leia o README de lá)
docs/                guia de uso e plano
build_tools/         empacotamento (PyInstaller)
.github/             modelos de issue/PR e CI
```

## Licença

Todos os direitos reservados. Veja [`LICENSE`](LICENSE). O código é público para leitura e discussão; uso, cópia e redistribuição dependem de autorização do autor.
