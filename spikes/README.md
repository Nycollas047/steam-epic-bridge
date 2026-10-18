# Spikes

Scripts de investigação ligados às perguntas da seção 6 de [`docs/PLANO.md`](../docs/PLANO.md).

## Leia isto antes de confiar nos resultados

Estes scripts **não validam o comportamento real** da Steam, da Epic nem do SteamGridDB. O que eles fazem de fato:

| Script | O que o código realmente exercita | O que o texto "Resposta" afirma, mas **não foi testado** |
|---|---|---|
| `spike_1_appid_estavel.py` | Grava e relê um `shortcuts.vdf` com a lib `vdf` e confere que o `appid` não muda | Que a **Steam** respeita o `appid` gravado e não o recalcula |
| `spike_2_icon_png.py` | Converte imagens para `.ico` com o Pillow | Que a **Steam** aceita `.png` no campo `icon` (e o código do app continua gerando `.ico`) |
| `spike_3_epic_login.py` | Chama `legendary auth --help` se existir um `legendary.exe` local | Qual fluxo de login é o mais estável |
| `spike_4_seb_launch_and_linux.py` | Monta strings de comando e lê um `installed.json` de teste | Que o launcher oficial da Epic registra `com.epicgames.launcher://` no Linux, formato de pacote e caminhos; que a Steam Flatpak executa `flatpak-spawn --host` |
| `spike_5_steamgriddb_api.py` | Monta um dicionário de parâmetros | Nomes e valores dos parâmetros e limites da API do SteamGridDB (conferir na documentação oficial) |

**Estado real:** as 5 perguntas continuam em aberto até alguém testar manualmente em uma máquina com a Steam (Windows 11, Linux nativo e Flatpak/Steam Deck) e com a conta Epic. Quem testar pode registrar o resultado na issue correspondente.

Os scripts são úteis como ponto de partida; os textos de "resposta" devem ser tratados como hipóteses.
