# Gerador de Médias

## Dados e normalização

`nota_num` e `media_final_num` são campos calculados em memória a partir de
`nota` e `media_final`; os campos originais permanecem no SQLite. Ambos aceitam
vírgula/ponto e números finitos entre 0 e 10, inclusive zero. Vazio, SN, texto
inválido e números fora do intervalo não são notas válidas.

A situação original fica em `notas.situacao`. “Em curso” não significa resultado
final. A classificação calculada indica **Acima da média** (>= média mínima),
**Em atenção** (>= limite de atenção e < média mínima), **Abaixo da média**
(< limite de atenção). Valores padrão: 6 e 4, configuráveis. Os nomes das
variáveis/rotas antigas são preservados para compatibilidade.

## Bases de cálculo e relatórios

| Relatório | Base |
| --- | --- |
| Média Geral da Turma | Anual |
| Média da Turma por Disciplina | Anual |
| Média Geral do Aluno | Anual |
| Média do Aluno por Disciplina | Anual |
| Ranking anual / análises anuais por disciplina | Anual |
| Média da Turma por Bimestre | Bimestral |
| Média da Turma por Disciplina e Bimestre | Bimestral |
| Média do Aluno por Bimestre | Bimestral |
| Média do Aluno por Disciplina e Bimestre | Bimestral |
| Estatísticas sem bimestre selecionado | Anual |
| Estatísticas com bimestre selecionado | Bimestral |

**Bimestral:** usa apenas `nota_num` válida de registros com bimestre identificado.

**Anual:** uma contribuição por aluno e disciplina dentro de cada importação,
turma e ano letivo. Se houver `media_final_num` válida, ela prevalece. Só quando
TODAS as ocorrências de `media_final` estiverem realmente vazias é usada a média
simples dos bimestres válidos. Uma final preenchida com SN/texto inválido não
autoriza fallback anual. Finais válidas conflitantes para o mesmo par são
omitidas com aviso visível em /analise, /medias e relatório HTML, sem escolher
uma arbitrariamente. A conferência recusa gravar esses conflitos. O Excel
legado inclui uma aba de avisos; exportações do gerador são bloqueadas até
a correção para não entregar resultados parciais sem aviso. Importações distintas não são colapsadas em um único par.

As médias de grupos dividem a soma dos valores válidos pela sua quantidade.
A média anual da turma dá a cada par aluno/disciplina o mesmo peso no modo
simples; não dá peso adicional a disciplinas com mais bimestres lançados.
O fallback anual não arredonda antes da agregação; a apresentação usa 2 casas.

Exemplo obrigatório: nota do 1º bimestre = 10; demais vazios; final = 5.
Resultado bimestral = **10**; resultado anual = **5**, com uma contribuição.

Média ponderada e descarte da menor permanecem disponíveis nas agregações do
período. A final da disciplina nunca é recalculada por esses modos; o fallback
anual é sempre a média simples dos bimestres válidos. Peso anual usa o peso do
primeiro registro do par (as importações atuais gravam peso 1).

SN e disciplinas sem nota não contribuem para médias, denominadores,
estatísticas ou rankings. Só aparecem nos filtros disciplinas com alguma
nota ou final válida. Bimestres sem notas válidas não aparecem nos filtros.

`media_service.py` concentra as bases, agregações, normalização, classificação,
ranking, gráficos e estatísticas. `calculos.py` adapta o formato para a tela
legada. `/analise`, `/relatorio`, Excel legado e `/medias` compartilham regras e
configuração. A comparação entre páginas deve usar o mesmo arquivo e métrica;
`/analise` permite todos os arquivos e `/medias` seleciona um arquivo por padrão.

## Leitura de PDF e importação

A leitura usa `pdfplumber.extract_tables()` e mapeia cada célula por cabeçalho:
Disciplina/Componente Curricular, quatro bimestres, Média Anual, Exame, Média
Final. Preserva vazios, inclusive o 4º bimestre, e nomes multilinha. Média Anual
não substitui nem se desloca para Média Final. Os quatro bimestres, inclusive
vazios e SN, ficam disponíveis na conferência, preservando os valores de origem.

Fallback textual exige as oito colunas explicitamente separadas por `|`.
Texto linear, tabela truncada/cabeçalho incompleto, aluno não identificado ou
mais de um aluno na mesma página provocam erro de leitura com orientação de
conferência. Nenhum último número é presumido como final. O upload é interrompido
inteiramente se uma página ativa não puder ser lida com segurança.

Transferido/Transferida são comparados com trim e casefold: excluídos na
extração, antes da conferência e novamente antes da transação de gravação.
Conferências antigas também são filtradas. A situação de cada registro decide
a exclusão; nunca excluir por nome, pois pode haver nome igual em páginas
ativas e transferidas. Não é criado boletim se só houver transferidos.

## Backup ANTES de modificar dados existentes

Execute na raiz do projeto com o Python do ambiente da aplicação. Informe o
caminho REAL de `DATABASE_PATH` configurado no servidor (o script não carrega
`.env` nem cria banco ausente). Os exemplos usam o padrão `database.sqlite3`.
Mantenha aplicação/importações paradas durante a manutenção para facilitar a
conferência operacional e preservar a consistência do conjunto em uso.

Primeiro, backup consistente com a API SQLite, incluindo WAL:

```bash
python scripts/manutencao_medias.py backup --db database.sqlite3 --destino backup-antes-limpeza.sqlite3
```

Confira o impacto sem modificar dados (comportamento padrão):

```bash
python scripts/manutencao_medias.py limpar --db database.sqlite3
```

Aplique somente após conferir as contagens. Este comando faz OUTRO backup
obrigatório imediatamente antes dos DELETEs, dentro do bloqueio de escrita:

```bash
python scripts/manutencao_medias.py limpar --db database.sqlite3 --aplicar --backup backup-aplicacao-limpeza.sqlite3
```

Destinos devem ser novos; o script recusa sobrescrita e backup sobre a origem.
Se diretórios tiverem espaços, coloque os caminhos entre aspas. Em execuções
posteriores use nomes novos (por exemplo incluindo data/hora). Confira o JSON
retornado: `notas_transferidas`, `boletins_orfaos`, modo e backup.

A limpeza remove SOMENTE linhas cuja situação seja Transferido/Transferida.
Preserva notas ativas do mesmo boletim, IDs remanescentes, arquivos PDF,
usuários, configurações e horários. Remove boletins apenas quando não existir
mais nenhuma nota vinculada, incluindo órfãos anteriores. Falhas de backup,
SQL ou integridade abortam; DELETEs são atômicos e fazem rollback em caso de erro.
É idempotente. Não corrige por adivinhação notas históricas já deslocadas pelo
parser antigo; nesses casos confira o PDF original e reimporte após revisão.
A rotina não é executada automaticamente ao iniciar o portal.

## Testes

Sem PDFs externos, os testes de PDF real são marcados como ausentes; não
confundir esse resultado com validação das turmas reais.

PowerShell, usando a pasta local indicada nesta correção:

```powershell
$env:BOLETINS_PDF_DIR = 'C:\Users\Cliente\Pictures\Boletins'
python -m unittest discover -s tests -v
python -m compileall -q app.py services sistemas tests scripts
git diff --check
```

Linux:

```bash
BOLETINS_PDF_DIR=/caminho/boletins python -m unittest discover -s tests -v
python -m compileall -q app.py services sistemas tests scripts
git diff --check
```

Não versionar PDFs reais nem dados pessoais de estudantes. Os testes comparam
as células estruturais de todas as páginas dos sete arquivos (6º–9º EF,
1º–3º EM), usam SQLite temporário e verificam serviços, rotas autenticadas,
exportações, backup, WAL, limpeza seletiva e rollback. O módulo de horários não
recebeu alteração de regra e não houve execução do solver ou publicação.
