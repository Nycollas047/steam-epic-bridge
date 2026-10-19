# 🎮 Como Usar o Steam Epic Bridge

## O que é?
O **Steam Epic Bridge** sincroniza toda a sua biblioteca da **Epic Games Store** (jogos instalados e não instalados) diretamente para a biblioteca da **Steam**, baixando automaticamente capas verticais, banners (hero), logos e ícones personalizados.

---

## Primeiro Uso (Passo a Passo)

### 1. Abrir a Interface
- **No Windows**: Dê dois cliques em `iniciar.bat` (ou execute `python SteamEpicBridge.py`).
- **No Linux / Steam Deck**: Execute `./iniciar.sh` (ou `python3 SteamEpicBridge.py`).

### 2. Configurar Conta Epic e Capas (`⚙ Configurações`)
1. Na tela principal, clique em **`⚙ Configurações`**.
2. Em **Conta Epic Games**:
   - Clique em **"Importar do Epic Launcher"** para importar sua sessão automaticamente com 1 clique; **ou**
   - Clique em **"Entrar via Navegador"**, faça login na Epic Games, copie o código (`authorizationCode`) exibido e cole na janela.
3. Em **Capas (SteamGridDB)**:
   - Clique em **"Pegar Chave Grátis"** (ou acesse [SteamGridDB API](https://www.steamgriddb.com/profile/preferences/api)), copie sua chave de API e cole no campo **Chave API**.
4. Clique em **"Salvar Configurações"**.

### 3. Sincronizar (`▶ Iniciar`)
1. **Feche a Steam completamente** (`Steam` -> `Sair`).
2. Na tela inicial do **Steam Epic Bridge**, clique em **`▶ Iniciar`**.
3. Reabra a Steam — todos os seus jogos da Epic estarão na biblioteca com capas e ícones!

---

## Como Funciona ao Clicar em "Jogar" na Steam

- **Jogo já instalado**: Abre o jogo diretamente.
- **Jogo ainda não instalado**: Abre o aplicativo da **Epic Games Store** no PC do usuário para baixar e gerenciar o jogo normalmente.

---

## Comandos de Terminal (Opcional)

```bash
python SteamEpicBridge.py sync           # Sincroniza e corrige atalhos e capas
python SteamEpicBridge.py status         # Mostra o resumo da conta e atalhos
python SteamEpicBridge.py doctor         # Diagnóstico completo do ambiente
python SteamEpicBridge.py clean          # Remove todos os atalhos da Epic da Steam
python SteamEpicBridge.py restore        # Restaura o último backup do shortcuts.vdf
```
