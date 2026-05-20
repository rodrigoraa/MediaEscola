import csv
import logging
import statistics
from datetime import datetime
from pathlib import Path

import pandas as pd


logger = logging.getLogger("media_service")

MEDIA_MINIMA_PADRAO = 6.0
LIMITE_RECUPERACAO_PADRAO = 4.0

RELATORIOS = {
    "media_geral_turma": {
        "grupo": "Médias da Turma",
        "titulo": "Média Geral da Turma",
        "descricao": "Média de todas as notas válidas de todos os alunos, disciplinas e bimestres.",
        "formula": "soma de todas as notas válidas ÷ quantidade total de notas válidas",
        "exemplo": "(8 + 7 + 6 + 9) ÷ 4 = 7,50",
        "filtros": ["turma", "ano_letivo"],
    },
    "media_turma_bimestre": {
        "grupo": "Médias da Turma",
        "titulo": "Média da Turma por Bimestre",
        "descricao": "Média de todas as notas da turma considerando apenas o bimestre selecionado.",
        "formula": "soma das notas do bimestre ÷ quantidade de notas do bimestre",
        "exemplo": "2º bimestre: soma das notas do 2º bimestre ÷ total de notas do 2º bimestre",
        "filtros": ["turma", "ano_letivo", "bimestre"],
    },
    "media_turma_disciplina": {
        "grupo": "Médias da Turma",
        "titulo": "Média da Turma por Disciplina",
        "descricao": "Média de todos os alunos em uma disciplina, considerando todos os bimestres.",
        "formula": "soma das notas da disciplina ÷ quantidade de notas da disciplina",
        "exemplo": "Matemática: todas as notas de Matemática ÷ total de notas de Matemática",
        "filtros": ["turma", "ano_letivo", "disciplina"],
    },
    "media_turma_disciplina_bimestre": {
        "grupo": "Médias da Turma",
        "titulo": "Média da Turma por Disciplina e Bimestre",
        "descricao": "Média da turma em determinada disciplina dentro de um bimestre específico.",
        "formula": "soma das notas da disciplina no bimestre ÷ quantidade dessas notas",
        "exemplo": "Matemática no 2º bimestre: notas de Matemática do 2º bimestre ÷ quantidade",
        "filtros": ["turma", "ano_letivo", "disciplina", "bimestre"],
    },
    "media_geral_aluno": {
        "grupo": "Médias do Aluno",
        "titulo": "Média Geral do Aluno",
        "descricao": "Média de todas as notas do aluno, em todas as disciplinas e bimestres.",
        "formula": "soma das notas do aluno ÷ quantidade de notas do aluno",
        "exemplo": "Aluno Ana: todas as notas da Ana ÷ quantidade de notas da Ana",
        "filtros": ["aluno", "turma", "ano_letivo"],
    },
    "media_aluno_bimestre": {
        "grupo": "Médias do Aluno",
        "titulo": "Média do Aluno por Bimestre",
        "descricao": "Média do aluno considerando todas as disciplinas apenas no bimestre selecionado.",
        "formula": "soma das notas do aluno no bimestre ÷ quantidade dessas notas",
        "exemplo": "Ana no 2º bimestre: notas da Ana no 2º bimestre ÷ quantidade",
        "filtros": ["aluno", "bimestre", "turma", "ano_letivo"],
    },
    "media_aluno_disciplina": {
        "grupo": "Médias do Aluno",
        "titulo": "Média do Aluno por Disciplina",
        "descricao": "Média do aluno em uma disciplina específica, considerando todos os bimestres.",
        "formula": "soma das notas do aluno na disciplina ÷ quantidade dessas notas",
        "exemplo": "Ana em Matemática: notas da Ana em Matemática ÷ quantidade",
        "filtros": ["aluno", "disciplina", "turma", "ano_letivo"],
    },
    "media_aluno_disciplina_bimestre": {
        "grupo": "Médias do Aluno",
        "titulo": "Média do Aluno por Disciplina e Bimestre",
        "descricao": "Nota ou média do aluno em uma disciplina dentro de um bimestre específico.",
        "formula": "soma das notas do aluno na disciplina e bimestre ÷ quantidade dessas notas",
        "exemplo": "Ana em Matemática no 2º bimestre: notas encontradas ÷ quantidade",
        "filtros": ["aluno", "disciplina", "bimestre", "turma", "ano_letivo"],
    },
    "estatisticas": {
        "grupo": "Estatísticas",
        "titulo": "Estatísticas Gerais",
        "descricao": "Resumo estatístico das notas válidas conforme os filtros selecionados.",
        "formula": "maior nota, menor nota, mediana, moda, desvio padrão e percentuais de situação",
        "exemplo": "Use para diagnosticar distribuição e risco da turma.",
        "filtros": ["turma", "aluno", "disciplina", "bimestre", "ano_letivo"],
    },
}

RELATORIOS_REMOVIDOS = {
    "turma_anual": "Duplicava Média Geral da Turma.",
    "disciplina_geral": "Duplicava Média da Turma por Disciplina.",
    "bimestre_geral": "Duplicava Média da Turma por Bimestre.",
    "bimestre_disciplina": "Renomeado para Média da Turma por Disciplina e Bimestre.",
    "bimestre_aluno": "Renomeado para Média do Aluno por Bimestre.",
    "ranking_geral": "Ranking agora aparece sobre os resultados de qualquer cálculo.",
    "ranking_bimestre": "Ranking agora aparece sobre Média do Aluno por Bimestre.",
    "ranking_disciplina": "Ranking agora aparece sobre Média do Aluno por Disciplina.",
    "aluno_anual": "Renomeado para Média Geral do Aluno.",
    "aluno_acumulada": "Removido por não estar no conjunto padronizado atual.",
    "turma_area": "Removido até haver cadastro formal de área do conhecimento.",
}


def preparar_dataframe(notas):
    df = pd.DataFrame(notas)
    if df.empty:
        return df

    for coluna in ["turma", "ano_letivo", "nome_aluno", "disciplina", "bimestre", "situacao", "nota", "peso"]:
        if coluna not in df.columns:
            df[coluna] = ""

    df["nota_num"] = df["nota"].apply(normalizar_nota)
    df["peso_num"] = df["peso"].apply(normalizar_peso)
    return df


def opcoes_filtros(df):
    if df.empty:
        return {"turmas": [], "alunos": [], "disciplinas": [], "bimestres": [], "anos": []}

    return {
        "turmas": _opcoes(df, "turma"),
        "alunos": _opcoes(df, "nome_aluno"),
        "disciplinas": _opcoes(df, "disciplina"),
        "bimestres": _ordenar_bimestres(_opcoes(df, "bimestre")),
        "anos": _opcoes(df, "ano_letivo"),
    }


def calcular_gerador_medias(notas, filtros):
    relatorio = normalizar_relatorio(filtros.get("relatorio") or "media_geral_turma")
    tipo_calculo = filtros.get("tipo_calculo") or "media_simples"
    media_minima = _float_config(filtros.get("media_minima"), MEDIA_MINIMA_PADRAO)
    limite_recuperacao = _float_config(filtros.get("limite_recuperacao"), LIMITE_RECUPERACAO_PADRAO)

    df_base = preparar_dataframe(notas)
    opcoes = opcoes_filtros(df_base)
    df_filtrado = aplicar_filtros(df_base, filtros, RELATORIOS[relatorio]["filtros"])
    df_valido = df_filtrado.dropna(subset=["nota_num"]).copy() if not df_filtrado.empty else df_filtrado

    logger.info(
        "calculo_medias relatorio=%s tipo=%s registros_filtrados=%s notas_validas=%s filtros=%s",
        relatorio,
        tipo_calculo,
        len(df_filtrado),
        len(df_valido),
        {k: v for k, v in filtros.items() if v},
    )

    resultados = _selecionar_relatorio(df_valido, relatorio, tipo_calculo)
    resultados = _classificar_resultados(resultados, media_minima, limite_recuperacao)
    resultados = _aplicar_filtros_de_desempenho(resultados, filtros, media_minima)
    resultados = gerarRanking(resultados)
    estatisticas = _estatisticas(df_valido, resultados, media_minima)

    return {
        "opcoes": opcoes,
        "resultados": resultados,
        "estatisticas": estatisticas,
        "graficos": _graficos(df_valido),
        "media_minima": media_minima,
        "limite_recuperacao": limite_recuperacao,
        "tipo_calculo": tipo_calculo,
        "relatorio": relatorio,
        "metadata": RELATORIOS[relatorio],
        "relatorios": RELATORIOS,
        "relatorios_removidos": RELATORIOS_REMOVIDOS,
        "total_registros": int(len(df_filtrado)),
        "total_notas_validas": int(len(df_valido)),
    }


def aplicar_filtros(df, filtros, filtros_relevantes=None):
    if df.empty:
        return df

    filtros_relevantes = set(filtros_relevantes or [])
    resultado = df.copy()
    mapa = {
        "turma": "turma",
        "aluno": "nome_aluno",
        "disciplina": "disciplina",
        "bimestre": "bimestre",
        "ano_letivo": "ano_letivo",
    }

    for campo, coluna in mapa.items():
        valor = filtros.get(campo)
        if valor and (not filtros_relevantes or campo in filtros_relevantes):
            resultado = resultado[resultado[coluna] == valor]

    return resultado


# Fórmula: soma de todas as notas válidas / quantidade total de notas válidas.
def calcularMediaGeralTurma(df, tipo_calculo="media_simples"):
    return [_linha_resultado("Turma", "", "", "", _calcular_media(df, tipo_calculo), len(df))]


# Fórmula: soma das notas do bimestre / quantidade de notas do bimestre.
def calcularMediaTurmaPorBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["bimestre"], tipo_calculo, ["bimestre"])


# Fórmula: soma das notas da disciplina / quantidade de notas da disciplina.
def calcularMediaTurmaPorDisciplina(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["disciplina"], tipo_calculo, ["disciplina"])


# Fórmula: soma das notas da disciplina no bimestre / quantidade dessas notas.
def calcularMediaTurmaPorDisciplinaEBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["disciplina", "bimestre"], tipo_calculo, ["disciplina", "bimestre"])


# Fórmula: soma das notas do aluno / quantidade de notas do aluno.
def calcularMediaAluno(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["nome_aluno"], tipo_calculo, ["aluno"])


# Fórmula: soma das notas do aluno no bimestre / quantidade dessas notas.
def calcularMediaAlunoPorBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["nome_aluno", "bimestre"], tipo_calculo, ["aluno", "bimestre"])


# Fórmula: soma das notas do aluno na disciplina / quantidade dessas notas.
def calcularMediaAlunoPorDisciplina(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["nome_aluno", "disciplina"], tipo_calculo, ["aluno", "disciplina"])


# Fórmula: soma das notas do aluno na disciplina e bimestre / quantidade dessas notas.
def calcularMediaAlunoPorDisciplinaEBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["nome_aluno", "disciplina", "bimestre"], tipo_calculo, ["aluno", "disciplina", "bimestre"])


def calcularMediaTurmaPorDisciplinaBimestre(df, tipo_calculo="media_simples"):
    return calcularMediaTurmaPorDisciplinaEBimestre(df, tipo_calculo)


def calcularMediaAlunoPorDisciplinaBimestre(df, tipo_calculo="media_simples"):
    return calcularMediaAlunoPorDisciplinaEBimestre(df, tipo_calculo)


def calcularMediaPonderada(valores, pesos=None):
    valores = [v for v in valores if pd.notna(v)]
    if not valores:
        return None
    pesos = pesos or [1 for _ in valores]
    total_pesos = sum(pesos)
    return round(sum(v * p for v, p in zip(valores, pesos)) / total_pesos, 2) if total_pesos else None


def calcularMediana(valores):
    valores = [v for v in valores if pd.notna(v)]
    return round(statistics.median(valores), 2) if valores else None


def calcularModa(valores):
    valores = [v for v in valores if pd.notna(v)]
    if not valores:
        return None
    modas = statistics.multimode(valores)
    return round(modas[0], 2) if modas else None


def calcularDesvioPadrao(valores):
    valores = [v for v in valores if pd.notna(v)]
    return round(statistics.pstdev(valores), 2) if len(valores) > 1 else 0


def gerarRanking(resultados):
    ordenados = sorted(resultados, key=lambda row: (row["media_calculada"] is None, -(row["media_calculada"] or 0)))
    for posicao, row in enumerate(ordenados, start=1):
        row["ranking"] = posicao
    return ordenados


def classificarSituacaoAluno(media, media_minima=MEDIA_MINIMA_PADRAO, limite_recuperacao=LIMITE_RECUPERACAO_PADRAO):
    if media is None:
        return "Sem nota"
    if media >= media_minima:
        return "Aprovado"
    if media >= limite_recuperacao:
        return "Recuperação"
    return "Reprovado"


def exportar_resultados_csv(pasta_exportacao, resultados):
    caminho = Path(pasta_exportacao) / f"gerador_medias_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    campos = ["ranking", "aluno", "turma", "disciplina", "bimestre", "media_calculada", "situacao", "observacao", "formula"]
    with caminho.open("w", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore", delimiter=";")
        writer.writeheader()
        writer.writerows(resultados)
    return caminho


def exportar_resultados_excel(pasta_exportacao, resultados, estatisticas):
    caminho = Path(pasta_exportacao) / f"gerador_medias_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        pd.DataFrame(resultados).to_excel(writer, sheet_name="Resultados", index=False)
        pd.DataFrame([estatisticas]).to_excel(writer, sheet_name="Resumo", index=False)
    return caminho


def exportar_resultados_pdf(pasta_exportacao, resultados, estatisticas):
    caminho = Path(pasta_exportacao) / f"gerador_medias_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linhas = [
        "Gerador de Médias",
        f"Média geral das notas filtradas: {estatisticas.get('media_geral')}",
        f"Notas válidas: {estatisticas.get('notas_validas')}",
        f"Alunos abaixo da média: {estatisticas.get('qtd_abaixo_media')}",
        "",
    ]
    for row in resultados[:45]:
        linhas.append(
            f"{row.get('ranking')}. {row.get('aluno') or row.get('turma') or 'Turma'} | "
            f"{row.get('disciplina')} | {row.get('bimestre')} | {row.get('media_calculada')}"
        )
    caminho.write_bytes(_pdf_simples("\n".join(linhas)))
    return caminho


def normalizar_relatorio(relatorio):
    return {
        "geral_turma": "media_geral_turma",
        "turma_bimestre": "media_turma_bimestre",
        "turma_disciplina": "media_turma_disciplina",
        "turma_disciplina_bimestre": "media_turma_disciplina_bimestre",
        "bimestre_disciplina": "media_turma_disciplina_bimestre",
        "aluno_geral": "media_geral_aluno",
        "aluno_anual": "media_geral_aluno",
        "aluno_bimestre": "media_aluno_bimestre",
        "aluno_disciplina": "media_aluno_disciplina",
        "aluno_disciplina_bimestre": "media_aluno_disciplina_bimestre",
        "disciplina_geral": "media_turma_disciplina",
        "disciplina_bimestre": "media_turma_disciplina_bimestre",
        "disciplina_aluno": "media_aluno_disciplina",
        "bimestre_geral": "media_turma_bimestre",
        "bimestre_aluno": "media_aluno_bimestre",
        "ranking_geral": "media_geral_aluno",
        "ranking_bimestre": "media_aluno_bimestre",
        "ranking_disciplina": "media_aluno_disciplina",
    }.get(relatorio, relatorio if relatorio in RELATORIOS else "media_geral_turma")


def _selecionar_relatorio(df, relatorio, tipo_calculo):
    mapa = {
        "media_geral_turma": calcularMediaGeralTurma,
        "media_turma_bimestre": calcularMediaTurmaPorBimestre,
        "media_turma_disciplina": calcularMediaTurmaPorDisciplina,
        "media_turma_disciplina_bimestre": calcularMediaTurmaPorDisciplinaEBimestre,
        "media_geral_aluno": calcularMediaAluno,
        "media_aluno_bimestre": calcularMediaAlunoPorBimestre,
        "media_aluno_disciplina": calcularMediaAlunoPorDisciplina,
        "media_aluno_disciplina_bimestre": calcularMediaAlunoPorDisciplinaEBimestre,
        "estatisticas": calcularMediaGeralTurma,
    }
    return mapa[relatorio](df, tipo_calculo)


def _agrupar(df, colunas, tipo_calculo, nomes_saida):
    if df.empty:
        return []

    resultados = []
    for chave, grupo in df.groupby(colunas, dropna=False):
        if not isinstance(chave, tuple):
            chave = (chave,)
        linha = _linha_resultado("", "", "", "", _calcular_media(grupo, tipo_calculo), len(grupo))
        for nome, valor in zip(nomes_saida, chave):
            linha[nome] = valor
        resultados.append(linha)
    return resultados


def _calcular_media(df, tipo_calculo):
    valores = list(df["nota_num"].dropna())
    if not valores:
        return None
    if tipo_calculo == "media_ponderada":
        return calcularMediaPonderada(valores, list(df.loc[df["nota_num"].notna(), "peso_num"]))
    if tipo_calculo == "descartar_menor" and len(valores) > 1:
        valores = sorted(valores)[1:]
    return round(sum(valores) / len(valores), 2)


def _linha_resultado(aluno, turma, disciplina, bimestre, media, quantidade):
    return {
        "aluno": aluno,
        "turma": turma,
        "disciplina": disciplina,
        "bimestre": bimestre,
        "media_calculada": media,
        "situacao": "",
        "ranking": "",
        "observacao": "",
        "quantidade": quantidade,
    }


def _classificar_resultados(resultados, media_minima, limite_recuperacao):
    for row in resultados:
        row["situacao"] = classificarSituacaoAluno(row.get("media_calculada"), media_minima, limite_recuperacao)
        row["observacao"] = _observacao(row, media_minima)
    return resultados


def _aplicar_filtros_de_desempenho(resultados, filtros, media_minima):
    desempenho = filtros.get("desempenho")
    if desempenho == "abaixo_media":
        resultados = [row for row in resultados if (row.get("media_calculada") or 0) < media_minima]
    elif desempenho == "acima_media":
        resultados = [row for row in resultados if (row.get("media_calculada") or 0) >= media_minima]

    ordenacao = filtros.get("ordenacao")
    if ordenacao == "maior_media":
        return sorted(resultados, key=lambda row: row.get("media_calculada") or -1, reverse=True)
    if ordenacao == "menor_media":
        return sorted(resultados, key=lambda row: row.get("media_calculada") if row.get("media_calculada") is not None else 99)
    return resultados


def _estatisticas(df, resultados, media_minima):
    valores = list(df["nota_num"].dropna()) if not df.empty else []
    total = len(resultados)
    aprovados = len([r for r in resultados if r.get("situacao") == "Aprovado"])
    recuperacao = len([r for r in resultados if r.get("situacao") == "Recuperação"])
    reprovados = len([r for r in resultados if r.get("situacao") == "Reprovado"])
    abaixo = len([r for r in resultados if (r.get("media_calculada") or 0) < media_minima])
    acima = len([r for r in resultados if (r.get("media_calculada") or 0) >= media_minima])

    return {
        "maior_nota": round(max(valores), 2) if valores else None,
        "menor_nota": round(min(valores), 2) if valores else None,
        "media_geral": round(sum(valores) / len(valores), 2) if valores else None,
        "mediana": calcularMediana(valores),
        "moda": calcularModa(valores),
        "desvio_padrao": calcularDesvioPadrao(valores),
        "qtd_abaixo_media": abaixo,
        "qtd_acima_media": acima,
        "percentual_aprovacao": _percentual(aprovados, total),
        "percentual_recuperacao": _percentual(recuperacao, total),
        "percentual_reprovacao": _percentual(reprovados, total),
        "total_resultados": total,
        "notas_validas": len(valores),
    }


def _graficos(df):
    if df.empty:
        return {"bimestres": [], "disciplinas": []}
    return {
        "bimestres": calcularMediaTurmaPorBimestre(df, "media_simples"),
        "disciplinas": sorted(
            calcularMediaTurmaPorDisciplina(df, "media_simples"),
            key=lambda row: row["media_calculada"] if row["media_calculada"] is not None else 99,
        )[:10],
    }


def _observacao(row, media_minima):
    media = row.get("media_calculada")
    if media is None:
        return "Sem nota válida para cálculo"
    if media < media_minima:
        return "Resultado abaixo da média configurada"
    return "Resultado dentro ou acima da média configurada"


def normalizar_nota(valor):
    if valor is None:
        return None
    texto = str(valor).strip().replace(",", ".")
    if not texto or texto.upper() == "SN":
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def normalizar_peso(valor):
    peso = normalizar_nota(valor)
    return peso if peso and peso > 0 else 1.0


def _opcoes(df, coluna):
    return sorted([valor for valor in df[coluna].dropna().unique().tolist() if str(valor).strip()])


def _ordenar_bimestres(valores):
    return sorted(valores, key=_bimestre_numero)


def _float_config(valor, padrao):
    try:
        return float(str(valor).replace(",", ".")) if valor not in (None, "") else padrao
    except ValueError:
        return padrao


def _percentual(parte, total):
    return round((parte / total) * 100, 1) if total else 0


def _bimestre_numero(valor):
    texto = str(valor or "")
    for numero in range(1, 5):
        if str(numero) in texto:
            return numero
    return 99


def _pdf_simples(texto):
    linhas = texto.splitlines()
    comandos = ["BT", "/F1 10 Tf", "50 790 Td"]
    for idx, linha in enumerate(linhas[:55]):
        if idx:
            comandos.append("0 -14 Td")
        comandos.append(f"({_escape_pdf(linha[:100])}) Tj")
    comandos.append("ET")
    stream = "\n".join(comandos).encode("latin-1", errors="replace")
    objetos = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objetos:
        offsets.append(len(pdf))
        pdf += obj
    xref = len(pdf)
    pdf += f"xref\n0 {len(objetos)+1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += f"trailer << /Root 1 0 R /Size {len(objetos)+1} >>\nstartxref\n{xref}\n%%EOF".encode()
    return pdf


def _escape_pdf(texto):
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
