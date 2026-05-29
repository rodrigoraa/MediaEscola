# Gerador de Médias

Este módulo usa somente notas válidas do campo `nota`. Valores vazios, `SN` e textos inválidos são ignorados.

## Opções finais

### Média Geral da Turma

Média de todas as notas válidas de todos os alunos, disciplinas e bimestres.

Fórmula: `soma de todas as notas válidas / quantidade total de notas válidas`.

### Média da Turma por Bimestre

Média de todas as notas válidas da turma no bimestre selecionado.

Fórmula: `soma das notas do bimestre / quantidade de notas do bimestre`.

### Média da Turma por Disciplina

Média de todos os alunos em uma disciplina, considerando todos os bimestres.

Fórmula: `soma das notas da disciplina / quantidade de notas da disciplina`.

### Média da Turma por Disciplina e Bimestre

Média da turma em determinada disciplina dentro de um bimestre.

Fórmula: `soma das notas da disciplina no bimestre / quantidade dessas notas`.

### Média Geral do Aluno

Média de todas as notas válidas do aluno, em todas as disciplinas e bimestres.

Fórmula: `soma das notas do aluno / quantidade de notas do aluno`.

### Média do Aluno por Bimestre

Média do aluno considerando todas as disciplinas apenas no bimestre selecionado.

Fórmula: `soma das notas do aluno no bimestre / quantidade dessas notas`.

### Média do Aluno por Disciplina

Média do aluno em uma disciplina específica, considerando todos os bimestres.

Fórmula: `soma das notas do aluno na disciplina / quantidade dessas notas`.

### Média do Aluno por Disciplina e Bimestre

Nota ou média do aluno em uma disciplina dentro de um bimestre específico.

Fórmula: `soma das notas do aluno na disciplina e bimestre / quantidade dessas notas`.

## Opções removidas ou consolidadas

- `turma_anual`: duplicava Média Geral da Turma.
- `disciplina_geral`: duplicava Média da Turma por Disciplina.
- `bimestre_geral`: duplicava Média da Turma por Bimestre.
- `bimestre_disciplina`: renomeado para Média da Turma por Disciplina e Bimestre.
- `bimestre_aluno`: renomeado para Média do Aluno por Bimestre.
- `ranking_geral`, `ranking_bimestre`, `ranking_disciplina`: ranking agora aparece nos resultados de qualquer cálculo.
- `aluno_anual`: renomeado para Média Geral do Aluno.
- `aluno_acumulada`: removido do conjunto padronizado atual.
- `turma_area`: removido até existir cadastro formal de área do conhecimento.
