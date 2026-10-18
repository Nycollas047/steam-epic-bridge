# Segurança

## Como relatar uma vulnerabilidade

**Não abra uma issue pública.** Use o relato privado do GitHub: aba **Security** do repositório > **Report a vulnerability**. Se a opção não estiver visível, entre em contato pelo perfil [@Nycollas047](https://github.com/Nycollas047).

Inclua: o que acontece, como reproduzir, e o impacto que você imagina.

## O que o app mexe (para você avaliar o risco)

- Lê e grava o `shortcuts.vdf` e a pasta `grid` da Steam (com backup antes de gravar).
- Guarda a chave do SteamGridDB em `config.json` na pasta de configuração do usuário.
- Chama o Legendary, que guarda a sessão da Epic no próprio diretório de configuração dele.

## Cuidados ao reportar

Nunca cole em issues públicas: chave do SteamGridDB, códigos de login (SID) da Epic, nem o conteúdo da pasta de configuração do Legendary.
