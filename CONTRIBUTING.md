# Como contribuir

Obrigado por querer ajudar. Este projeto é público para leitura e discussão, mas **o código não tem licença de uso aberta** (veja [`LICENSE`](LICENSE)). Por isso há dois caminhos.

## 1. Comentar e sugerir (sem exigências)

Qualquer pessoa pode, a qualquer momento:

- abrir uma [sugestão](https://github.com/Nycollas047/steam-epic-bridge/issues/new?template=sugestao.yml);
- relatar um [erro](https://github.com/Nycollas047/steam-epic-bridge/issues/new?template=erro.yml);
- comentar nas issues abertas e em [`docs/PLANO.md`](docs/PLANO.md), onde estão as decisões em aberto.

Quanto mais concreto, melhor: sistema operacional, versão da Steam, passos para reproduzir, o que você esperava.

## 2. Enviar código (pull request)

Antes de investir tempo, **abra uma issue descrevendo a mudança** e espere um retorno. Assim evitamos trabalho duplicado ou fora do plano.

Ao abrir o PR, você confirma o termo abaixo (há uma caixa para marcar no modelo do PR).

> **Termo de contribuição.** Declaro que sou autor da contribuição (ou tenho direito de enviá-la) e concedo ao autor do projeto uma licença mundial, perpétua, irrevogável, gratuita e sublicenciável para usar, modificar, distribuir e comercializar a contribuição como parte do projeto, inclusive em versões comerciais e fechadas.

Sem essa concordância, o PR não será aceito. *(Este texto é um ponto de partida e deve passar por revisão jurídica antes de a comercialização começar.)*

### Como rodar localmente

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest tests -v
```

### Regras do PR

- Um assunto por PR, pequeno e fácil de revisar.
- Testes passando (o CI roda em Windows e Linux).
- Mudou comportamento? Atualize o teste e a documentação.
- Não inclua binários (`.exe`), chaves de API nem arquivos do seu `shortcuts.vdf`.

## Conduta

Leia o [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Segurança: veja [`SECURITY.md`](SECURITY.md).
