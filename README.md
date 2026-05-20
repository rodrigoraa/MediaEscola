# Analisador de Boletins Escolares

Sistema web em Python com Flask e SQLite para importar boletins escolares em PDF, conferir os dados extraídos, salvar no banco e gerar análises em HTML e Excel.

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
services/leitor_pdf.py
services/calculos.py
services/relatorios.py
templates/
static/
uploads/
exports/
database.sqlite3
```

## Fluxo de uso

1. Envie o PDF do boletim pela tela inicial.
2. Confira os dados extraídos antes de salvar.
3. Edite nomes, disciplinas, bimestres, notas, médias finais ou situação, se necessário.
4. Salve no SQLite.
5. Abra a tela de análises para ver médias e rankings.
6. Gere relatório HTML ou exporte para Excel.

## Login inicial

O primeiro administrador é criado automaticamente usando `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD` do arquivo `.env`.

Após entrar, altere a senha em **Senha**.

## Rotas principais

```text
/login
/logout
/dashboard
/
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

Acesse **Gerador de Médias** no menu. Use os filtros de PDF, turma, aluno, disciplina, bimestre, ano letivo, situação, tipo de cálculo e relatório. Depois clique em **Calcular**.

Exportações disponíveis:

```text
PDF
Excel
CSV
```

A média mínima padrão começa em `6.0` e pode ser alterada em **Configurações**.
