# Portal Escolar

Sistema web em Python com Flask e SQLite que funciona como portal para dois módulos: Gerador de Médias e Gerador de Horários.

## Instalação em servidor Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
```

## Execução

```bash
source .venv/bin/activate
python app.py
```

Acesse:

```text
http://IP_DO_SERVIDOR:5000
```

Em produção, configure o arquivo `.env` no servidor e execute atrás de um proxy reverso, como Nginx. Não envie o `.env` real para o git.

## Variáveis de ambiente

Crie o arquivo `.env` a partir do `.env.example`:

```text
SECRET_KEY=troque-por-uma-chave-grande-e-aleatoria
DATABASE_PATH=database.sqlite3
EXPORT_DIR=exports
PENDING_DIR=tmp/conferencias
APP_HOST=0.0.0.0
APP_PORT=5000
FLASK_DEBUG=0
SESSION_HOURS=8
HORARIOS_HOST=127.0.0.1
HORARIOS_PORT=8501
HORARIOS_BASE_PATH=horarios-app
# HORARIOS_URL=https://coordenacao.eesjv.com.br/horarios-app

BOOTSTRAP_ADMIN_ENABLED=1
BOOTSTRAP_ADMIN_NAME=Administrador
BOOTSTRAP_ADMIN_EMAIL=admin@seudominio.com
BOOTSTRAP_ADMIN_PASSWORD=troque-esta-senha
```

Para gerar uma chave segura no Linux:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Estrutura

```text
app.py
sistemas/
  medias/
    services/
    templates/
    docs/
  horarios/
services/auth_service.py
templates/
static/
uploads/
exports/
database.sqlite3
```

## Fluxo de uso

1. Entre no portal.
2. Escolha **Gerador de Médias** ou **Gerador de Horários**.
3. No Gerador de Médias, envie o PDF do boletim pela tela de importação.
4. Confira os dados extraídos antes de salvar.
5. Edite nomes, disciplinas, bimestres, notas, médias finais ou situação, se necessário.
6. Salve no SQLite.
7. Abra a tela de análises para ver médias e rankings.
8. Gere relatório HTML ou exporte para Excel.

## Login inicial

O primeiro administrador é criado automaticamente usando `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD` do arquivo `.env`.

Após entrar, altere a senha em **Senha**.

## Rotas principais

```text
/login
/logout
/dashboard
/
/horarios
/medias/importar
/conferencia
/analise
/medias
/medias/exportar/pdf
/medias/exportar/excel
/medias/exportar/csv
/usuarios
/configuracoes
```

## Gerador de Médias

Acesse **Gerador de Médias** no menu. Escolha o PDF analisado e use os filtros de aluno, disciplina, bimestre, tipo de cálculo e relatório. Depois clique em **Calcular**.

Exportações disponíveis:

```text
PDF
Excel
CSV
```

A média mínima padrão começa em `6.0` e pode ser alterada em **Configurações**.

## Gerador de Horários

O módulo de horários fica em `sistemas/horarios/` e é executado em Streamlit. Ao abrir **Gerador de Horários** pelo portal, o Flask tenta iniciar automaticamente o Streamlit em `HORARIOS_HOST:HORARIOS_PORT`.

Em produção, você pode manter o Streamlit atrás de um proxy reverso próprio e definir `HORARIOS_URL` no `.env` para o endereço público configurado. Para usar tudo no mesmo domínio, configure `HORARIOS_BASE_PATH=horarios-app` e `HORARIOS_URL=https://coordenacao.eesjv.com.br/horarios-app`.
