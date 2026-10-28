# Análise e plano de correção — 28/10/2026

## Diagnóstico antes da implementação

O portal Flask concentra em `app.py` upload, conferência, persistência SQLite,
análise, gerador e exportações. `services/auth_service.py` controla permissões.
O outro módulo, `sistemas/horarios`, usa Streamlit, solver e exportadores próprios;
compartilha o caminho SQLite, mas não consome notas nem serviços de médias.
Templates, estilos, autenticação e geração de horários não precisam de redesenho.
Não havia testes automatizados no checkout inicial (unittest: 0 testes).

Pontos afetados e causas:

- `leitor_pdf.py`: já prioriza tabelas, mas executa também extração textual sem
  necessidade. O parser textual perde vazios, estima a quantidade de bimestres e
  usa o último número como final. Ainda substitui final vazia por Média Anual.
  Contexto de um aluno por página pode atribuir notas ao aluno errado em páginas
  com mais de um boletim. Nomes quebrados devem permanecer na mesma célula.
- `app.py`: upload e POST de conferência aceitam transferidos, sem defesa antes
  de criar boletim/notas. Conferências pendentes também precisam ser filtradas.
- `media_service.py`: calcula relatórios anuais sobre todas as notas bimestrais;
  não cria `media_final_num`. Filtros listam disciplinas sem valores válidos.
  Classificação usa aprovação/reprovação sem resultado escolar final.
- `calculos.py`: implementa outra normalização e outra agregação anual. Embora
  priorize finais, aceita valores fora do intervalo e faz fallback mesmo com
  final preenchida inválida. Arredonda antes das agregações seguintes e usa 6
  fixo, divergindo da configuração do gerador.
- Os dois normalizadores aceitam negativos, >10 e infinitos. Rankings,
  estatísticas, gráficos, HTML e exportações herdam essas divergências.
- SQLite não tem rotina de limpeza seletiva por situação. Apagar o boletim
  inteiro removeria alunos ativos junto com os transferidos.

## Decisões e sequência

1. Escrever regressões e observar as falhas antes de implementar.
2. Centralizar normalização, bases anual/bimestral, médias, classificação,
   ranking e estatísticas em `media_service.py`. `calculos.py` será adaptador de
   formato para os templates legados, chamando o mesmo serviço.
3. Uma final numérica válida prevalece sobre todas as notas do par aluno e
   disciplina. Somente final realmente vazia permite média simples dos
   bimestres válidos; SN/texto inválido preenchido não autoriza fallback anual.
   Separar importação, turma e ano para não misturar homônimos entre boletins.
   Arredondar somente ao apresentar agregações.
4. Preservar cálculo ponderado e descarte, aplicados aos valores do período;
   nunca usá-los para recalcular uma final fornecida.
5. Preservar células vazias e cabeçalhos reconhecidos nas tabelas. Fallback
   textual só aceita colunas delimitadas explicitamente; texto linear ambíguo
   produz erro orientando conferência do PDF, sem adivinhar valores.
6. Aplicar a mesma identificação tolerante a espaços e caixa de transferidos
   após extrair e antes de gravar. Não criar boletim vazio.
7. Criar CLI de backup e limpeza com simulação padrão, aplicação explícita,
   backup obrigatório, transação, preservação de PDFs e remoção só de órfãos.
8. Executar testes de serviços, importação/gravação, limpeza, rotas,
   exportações e PDFs reais de 6º–9º EF e 1º–3º EM quando disponíveis.

## Validação e limites

PDFs reais: pasta externa configurável por `BOLETINS_PDF_DIR`; não versionar
documentos com dados pessoais. Os testes comparam cada célula estrutural dos
PDFs com a saída, incluindo situação, final, vazios e nomes multilinha.
Usar apenas SQLite temporário nos testes. Não executar limpeza em banco real.
Comandos e resultados finais estão em `MEDIAS.md` e no relatório de execução.

## Ajustes da revisão independente

- Rejeitar finais válidas conflitantes na conferência, preservando as edições
  na tela. Para conflitos legados, exibir avisos nas análises/relatório e bloquear
  exportações parciais do gerador. A mesma detecção atende gravação e leitura.
- Normalizar ausência de turma/ano (NULL e vazio) na base em memória para não
  criar contribuições anuais diferentes somente por ausência de metadados.
- Remover o rótulo fixo de limite 6,0 dos templates; o limite mostrado acompanha
  a configuração compartilhada entre as rotas.
- Fechar conexões após transações: o context manager padrão do sqlite3 apenas
  confirma/desfaz transação e deixava arquivos bloqueados no Windows. Há uma
  regressão específica para o encerramento e os testes usam bancos temporários.
