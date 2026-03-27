# 🤖 Telegram Auto-Buy Bot

Bot que monitora um canal/grupo do Telegram em tempo real, detecta links de produtos, faz scraping de preço/disponibilidade e executa auto-buy quando as regras configuradas são atendidas.

---

## 📁 Estrutura do Projeto

```
telegram_autobuy/
├── main.py               # Ponto de entrada — inicializa e inicia o bot
├── telegram_listener.py  # Recebe mensagens, orquestra o pipeline
├── parser.py             # Extrai e normaliza URLs das mensagens
├── scraper.py            # Playwright: abre produto, extrai nome/preço/disponibilidade
├── decision.py           # Aplica regras de compra configuráveis
├── buyer.py              # Playwright: simula adicionar ao carrinho + checkout
├── config.py             # Todas as configurações do projeto
├── requirements.txt      # Dependências Python
├── session.json          # Gerado automaticamente (cookies persistentes)
└── screenshots/          # Gerado automaticamente (auditoria de compras)
```

---

## ⚙️ Instalação (Linux)

### 1. Pré-requisitos

```bash
# Python 3.11+ necessário
python3 --version

# Instalar pip e venv se necessário
sudo apt update && sudo apt install -y python3-pip python3-venv
```

### 2. Criar ambiente virtual

```bash
cd telegram_autobuy
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências Python

```bash
pip install -r requirements.txt
```

### 4. Instalar navegador do Playwright

```bash
# Instala o Chromium + dependências do sistema
playwright install chromium
playwright install-deps chromium
```

---

## 🔧 Configuração

### 1. Token do Bot

Crie um bot no [@BotFather](https://t.me/BotFather) e copie o token.

**Opção A — Variável de ambiente (recomendado):**
```bash
export BOT_TOKEN="1234567890:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**Opção B — Editar config.py diretamente:**
```python
BOT_TOKEN: str = "1234567890:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### 2. ID do Canal a Monitorar

Para obter o ID numérico do canal/grupo:
1. Encaminhe qualquer mensagem do canal para [@userinfobot](https://t.me/userinfobot)
2. Ele retornará o `Chat ID` (será negativo para grupos/canais, ex: `-1234567890000`)

```python
# config.py
SOURCE_CHAT_ID: int = -1234567890000  # substitua pelo ID real
```

### 3. ID para Receber Notificações (seu chat pessoal)

1. Envie qualquer mensagem para [@userinfobot](https://t.me/userinfobot)
2. Copie seu `User ID` (número positivo)

```python
NOTIFY_CHAT_ID: int = 12345678  # seu ID pessoal
```

### 4. Adicionar o Bot ao Canal

O bot precisa ser **membro** do canal/grupo com permissão de leitura:
- Vá nas configurações do canal → Administradores → Adicionar administrador
- Busque pelo username do seu bot
- Permissão necessária: **Leitura de mensagens** (padrão para admins)

### 5. Configurar Regras de Compra

Edite a lista `BUY_RULES` em `config.py`:

```python
BUY_RULES = [
    BuyRule(
        name="Minha Regra",
        keywords=["ssd", "nvme"],   # compra se QUALQUER keyword estiver no nome
        max_price=350.00,            # só compra se preço <= R$ 350
        min_discount_pct=20.0,       # desconto mínimo (informativo)
    ),
]
```

---

## ▶️ Execução

```bash
# Ativar ambiente virtual (se não estiver ativo)
source .venv/bin/activate

# Rodar o bot
python main.py
```

### Saída esperada no terminal:
```
2024-01-15 10:30:00 [INFO] __main__: 🚀 Iniciando bot de auto-buy...
2024-01-15 10:30:00 [INFO] __main__: 📡 Monitorando chat ID: -1001234567890
2024-01-15 10:30:00 [INFO] __main__: 📋 Regras ativas: 3
2024-01-15 10:30:00 [INFO] __main__:    • SSD Barato | keywords: ['ssd', 'nvme', 'm.2'] | max: R$ 350.00
2024-01-15 10:30:01 [INFO] __main__: ✅ Bot iniciado. Aguardando mensagens...
```

---

## 🔄 Executar em Segundo Plano (Linux)

### Com systemd:

```bash
# Criar arquivo de serviço
sudo nano /etc/systemd/system/autobuy.service
```

```ini
[Unit]
Description=Telegram Auto-Buy Bot
After=network.target

[Service]
Type=simple
User=SEU_USUARIO
WorkingDirectory=/caminho/para/telegram_autobuy
Environment=BOT_TOKEN=seu_token_aqui
Environment=SOURCE_CHAT_ID=-1001234567890
Environment=NOTIFY_CHAT_ID=987654321
ExecStart=/caminho/para/telegram_autobuy/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable autobuy
sudo systemctl start autobuy
sudo systemctl status autobuy

# Ver logs em tempo real:
journalctl -u autobuy -f
```

### Com nohup (mais simples):
```bash
nohup python main.py > bot.log 2>&1 &
tail -f bot.log
```

---

## 🔍 Como o Bot Funciona

```
Canal Telegram
      │
      │  mensagem com link
      ▼
telegram_listener.py
      │
      ├─ parser.py         → extrai URL da mensagem
      │
      ├─ Cache             → verifica duplicatas
      │
      ├─ scraper.py        → abre URL com Playwright
      │    └─ extrai nome, preço, disponibilidade
      │
      ├─ decision.py       → verifica regras de compra
      │    └─ keyword match + preço ≤ máximo
      │
      ├─ buyer.py          → auto-buy simulado
      │    ├─ clica "Adicionar ao carrinho"
      │    ├─ navega para checkout
      │    └─ PARA (não confirma pagamento)
      │
      └─ Notificação       → envia resultado + screenshot ao admin
```

---

## ⚠️ Avisos Importantes

1. **Pagamento não é confirmado** — o bot para no checkout por segurança.
2. **Sessão persistente** — `session.json` guarda cookies; delete-o para resetar login.
3. **Screenshots** — salvos em `screenshots/` para auditoria de cada compra.
4. **Sites protegidos** — sites com CAPTCHA ou anti-bot podem bloquear o scraper.
5. **Termos de uso** — verifique os ToS dos sites antes de usar automação.

---

## 🐛 Resolução de Problemas

| Problema | Solução |
|----------|---------|
| Bot não recebe mensagens | Confirme que o bot é admin do canal |
| Timeout no scraper | Aumente `SCRAPER_TIMEOUT_MS` em config.py |
| Playwright não instalado | Execute `playwright install chromium` |
| "Token inválido" | Verifique BOT_TOKEN com @BotFather |
| Preço não detectado | Adicione seletores do site em `scraper.py/_SITE_SELECTORS` |
