# Resultado da correção — 28/10/2026

## Verificação final

Execução na raiz do projeto, com os sete PDFs externos disponíveis:

```powershell
$env:BOLETINS_PDF_DIR = 'C:\Users\Cliente\Pictures\Boletins'
$env:LOG_LEVEL = 'WARNING'
python -m unittest discover -s tests -v
```

Saída final:

```text
Ran 49 tests in 69.655s

OK
```

49 aprovados; zero falhas, erros ou testes ignorados. `python -m compileall -q
app.py services sistemas tests scripts` e `git diff --check` também passaram.
O log completo local está em `tmp/validacao-final.log` (ignorado pelo Git).

| Grupo | Testes aprovados |
| --- | ---: |
| Normalização, bases, médias, filtros, rankings, gráficos e consistência | 19 |
| Leitor: tabela, vazios, multilinha, fallback e transferidos | 7 |
| PDFs reais: todas as páginas dos sete arquivos | 7 |
| SQLite: backup, limpeza, WAL, preservação e rollback | 7 |
| Rotas, conferência, configuração e exportações | 9 |

## PDFs reais

Comparação integral das células das tabelas com a saída do leitor, sem gravar
dados reais no banco e sem copiar os documentos para o repositório:

| Arquivo | Páginas | Páginas Em curso preservadas | Páginas Transferido excluídas |
| --- | ---: | ---: | ---: |
| 6º EF | 17 | 15 | 2 |
| 7º EF | 21 | 19 | 2 |
| 8º EF | 22 | 21 | 1 |
| 9º EF | 19 | 17 | 2 |
| 1º EM | 19 | 18 | 1 |
| 2º EM | 12 | 10 | 2 |
| 3º EM | 15 | 13 | 2 |
| Total | 125 | 113 | 12 |

No 6º EF há nome presente tanto em página ativa quanto transferida. O teste
preserva a página ativa e exclui somente a situação transferida. Nenhuma
exclusão é feita por nome.

O caso obrigatório `nota=10`, demais bimestres vazios e `media_final=5` passou:
os quatro relatórios anuais retornam **5**, com uma contribuição por disciplina;
os quatro relatórios bimestrais retornam **10** no primeiro bimestre.

## Causas e correções

| Problema | Causa no código anterior | Correção |
| --- | --- | --- |
| Transferidos importados | Nenhum filtro na extração/upload ou no POST | Identificação compartilhada por situação, tolerante a caixa/espaços, antes da conferência e novamente antes de criar boletim/notas |
| Anuais diferentes nas duas telas | Gerador agregava todas as notas bimestrais; análise tinha implementação anual própria | Serviço único; base anual com uma contribuição por aluno/disciplina e prioridade absoluta da final válida |
| Finais inválidas recalculadas | Análise fazia fallback quando a normalização da final falhava | Fallback somente se a final estiver realmente vazia; SN/texto preenchido não autoriza substituição |
| Valores inválidos e disciplinas sem nota | Normalizadores aceitavam qualquer float, incluindo fora de 0–10; opções eram extraídas do conjunto bruto | Normalização única e finita de 0–10; opções e contagens derivadas de valores válidos |
| Risco de deslocar colunas do PDF | Fallback contava tokens e escolhia o último como final; final vazia podia receber Média Anual | Mapeamento estrutural pelos oito cabeçalhos, mantendo vazios e nomes multilinha; texto ambíguo gera erro |
| Classificação parecia resultado escolar | Rótulos Aprovado/Recuperação/Reprovado usados para cálculo intermediário | Acima da média/Em atenção/Abaixo da média; situação original permanece separada |
| Limites divergentes | Análise e rótulos fixavam 6, enquanto gerador lia configuração | Ambas as telas, resumo por disciplina e rótulos usam configuração compartilhada |
| Limpeza poderia afetar ativos | Ausência de rotina seletiva por situação | CLI com simulação padrão, backup obrigatório e transação; boletim só é removido se não restar nenhuma nota |
| Final conflitante na conferência | Edição de apenas uma das linhas repetidas podia criar duas finais para o mesmo par | Recusa antes de salvar; conflitos legados ficam visíveis nas análises e bloqueiam exportações parciais do gerador |
| Gráfico anual influenciado pelo filtro bimestral | Recorte do bimestre podia reduzir as notas usadas no fallback anual | Base anual do gráfico ignora o recorte por bimestre e usa todos os bimestres válidos do par |
| SQLite mantinha arquivos abertos | Context manager padrão confirma/desfaz, mas não fecha conexão | Conexão fecha ao sair da transação, com regressão específica |

As fórmulas completas e os comandos de backup, simulação e aplicação estão em
[MEDIAS.md](MEDIAS.md). A análise anterior à implementação e a sequência de
trabalho estão em [CORRECAO_MEDIAS.md](CORRECAO_MEDIAS.md).

## Arquivos alterados ou criados

- `app.py`: defesas, configuração comum, validação de conflitos e fechamento SQLite.
- `sistemas/medias/services/media_service.py`: fonte única de regras e bases.
- `sistemas/medias/services/calculos.py`: adaptador para as análises legadas.
- `sistemas/medias/services/leitor_pdf.py`: leitura estrutural e fallback conservador.
- `sistemas/medias/services/situacao.py`: identificação de transferidos.
- `sistemas/medias/services/relatorios.py`: avisos de dados conflitantes no Excel legado.
- `sistemas/medias/templates/medias/index.html`: rótulos corretos e avisos.
- `sistemas/medias/templates/analise.html`: limite configurado e avisos.
- `sistemas/medias/templates/relatorio.html`: limite configurado e avisos.
- `sistemas/medias/templates/partials/tabela_resumo_disciplina.html`: limite configurado.
- `scripts/manutencao_medias.py`: backup e limpeza seletiva.
- `tests/__init__.py`.
- `tests/test_medias.py`.
- `tests/test_leitor_pdf.py`.
- `tests/test_routes.py`.
- `tests/test_limpeza.py`.
- `sistemas/medias/docs/MEDIAS.md`.
- `sistemas/medias/docs/CORRECAO_MEDIAS.md`.
- `sistemas/medias/docs/VALIDACAO_MEDIAS.md`.

## Escopo validado

A revisão independente encontrou o conflito de finais, corrigido e coberto
por regressões que falharam antes da correção e passaram depois. A suíte
completa foi repetida após os últimos ajustes de código.

Nenhum SQLite existente foi modificado, nenhuma limpeza real foi aplicada,
nenhum PDF de origem foi alterado e não houve publicação ou push. O checkout
não continha `database.sqlite3`; testes de gravação e limpeza usaram somente
bancos temporários. Foi inspecionada visualmente uma página do PDF real para
confirmar a posição das colunas. Não houve validação visual do portal em
navegador, impressão física, execução do solver de horários ou teste em produção.
