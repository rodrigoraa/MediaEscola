import csv
import statistics
from datetime import datetime
from pathlib import Path

import pandas as pd


MEDIA_MINIMA_PADRAO = 6.0
LIMITE_RECUPERACAO_PADRAO = 4.0
AREAS_CONHECIMENTO = {
    "Arte": "Linguagens",
    "Educação Física": "Linguagens",
    "Lingua Inglesa": "Linguagens",
    "Língua Portuguesa": "Linguagens",
    "Leitura e Produção Textual": "Linguagens",
    "Matemática": "Matemática",
    "Ciências": "Ciências da Natureza",
    "Geografia": "Ciências Humanas",
    "História": "Ciências Humanas",
    "Terra-Vida-Trabalho": "Ciências Humanas",
}


def preparar_dataframe(notas):
    df = pd.DataFrame(notas)
    if df.empty:
        return df

    for coluna in ["turma", "ano_letivo", "nome_aluno", "disciplina", "bimestre", "situacao", "nota", "media_final"]:
        if coluna not in df.columns:
            df[coluna] = ""

    df["nota_num"] = df["nota"].apply(normalizar_nota)
    df["media_final_num"] = df["media_final"].apply(normalizar_nota)
    df["peso"] = 1.0
    df["area_conhecimento"] = df["disciplina"].map(AREAS_CONHECIMENTO).fillna("Não classificada")
    return df


def aplicar_filtros(df, filtros):
    if df.empty:
        return df

    resultado = df.copy()
    for campo, coluna in [
        ("turma", "turma"),
        ("aluno", "nome_aluno"),
        ("disciplina", "disciplina"),
        ("bimestre", "bimestre"),
        ("ano_letivo", "ano_letivo"),
    ]:
        valor = filtros.get(campo)
        if valor:
            resultado = resultado[resultado[coluna] == valor]

    situacao = filtros.get("situacao")
    if situacao and situacao != "todos":
        resultado = resultado[resultado["situacao"].str.lower() == situacao.lower()]

    return resultado


def opcoes_filtros(df):
    if df.empty:
        return {"turmas": [], "alunos": [], "disciplinas": [], "bimestres": [], "anos": []}

    return {
        "turmas": _opcoes(df, "turma"),
        "alunos": _opcoes(df, "nome_aluno"),
        "disciplinas": _opcoes(df, "disciplina"),
        "bimestres": _opcoes(df, "bimestre"),
        "anos": _opcoes(df, "ano_letivo"),
    }


def calcular_gerador_medias(notas, filtros):
    media_minima = _float_config(filtros.get("media_minima"), MEDIA_MINIMA_PADRAO)
    limite_recuperacao = _float_config(filtros.get("limite_recuperacao"), LIMITE_RECUPERACAO_PADRAO)
    tipo_calculo = filtros.get("tipo_calculo") or "media_simples"
    relatorio = filtros.get("relatorio") or "geral_turma"

    df_base = preparar_dataframe(notas)
    opcoes = opcoes_filtros(df_base)
    df_filtrado = aplicar_filtros(df_base, filtros)
    df_valido = _df_valido_para_calculo(df_filtrado, tipo_calculo)

    resultados = _selecionar_relatorio(df_valido, relatorio, tipo_calculo)
    resultados = _classificar_resultados(resultados, media_minima, limite_recuperacao)
    if relatorio == "alunos_risco":
        resultados = [row for row in resultados if row.get("situacao") in {"Recuperação", "Reprovado"}]
    resultados = _aplicar_filtros_de_desempenho(resultados, filtros, media_minima)
    resultados = gerarRanking(resultados)
    estatisticas = _estatisticas(df_valido, resultados, media_minima)
    graficos = _graficos(df_valido, resultados)

    return {
        "opcoes": opcoes,
        "resultados": resultados,
        "estatisticas": estatisticas,
        "graficos": graficos,
        "media_minima": media_minima,
        "limite_recuperacao": limite_recuperacao,
        "tipo_calculo": tipo_calculo,
        "relatorio": relatorio,
        "total_registros": int(len(df_filtrado)),
    }


def calcularMediaGeralTurma(df, tipo_calculo="media_simples"):
    media = _calcular_serie(df, tipo_calculo)
    return [_linha_resultado("Turma", "", "", "", media, len(df))]


def calcularMediaTurmaPorBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["bimestre"], tipo_calculo, ["bimestre"])


def calcularMediaTurmaPorDisciplina(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["disciplina"], tipo_calculo, ["disciplina"])


def calcularMediaAluno(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["nome_aluno"], tipo_calculo, ["aluno"])


def calcularMediaAlunoPorBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["nome_aluno", "bimestre"], tipo_calculo, ["aluno", "bimestre"])


def calcularMediaAlunoPorDisciplina(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["nome_aluno", "disciplina"], tipo_calculo, ["aluno", "disciplina"])


def calcularMediaAlunoPorDisciplinaBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["nome_aluno", "disciplina", "bimestre"], tipo_calculo, ["aluno", "disciplina", "bimestre"])


def calcularMediaDisciplina(df, tipo_calculo="media_simples"):
    return calcularMediaTurmaPorDisciplina(df, tipo_calculo)


def calcularMediaDisciplinaPorBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["disciplina", "bimestre"], tipo_calculo, ["disciplina", "bimestre"])


def calcularMediaBimestre(df, tipo_calculo="media_simples"):
    return calcularMediaTurmaPorBimestre(df, tipo_calculo)


def calcularMediaAreaConhecimento(df, tipo_calculo="media_simples"):
    return _agrupar(df, ["area_conhecimento"], tipo_calculo, ["area"])


def calcularMediaAcumulada(df, tipo_calculo="media_simples"):
    bimestre_limite = _bimestre_numero(df["bimestre"].dropna().max()) if not df.empty else None
    if bimestre_limite:
        df = df[df["bimestre"].apply(_bimestre_numero) <= bimestre_limite]
    return calcularMediaAluno(df, tipo_calculo)


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
    try:
        return round(statistics.mode(valores), 2)
    except statistics.StatisticsError:
        return None


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
    campos = ["ranking", "aluno", "turma", "disciplina", "bimestre", "media_calculada", "situacao", "observacao"]
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
        f"Média geral: {estatisticas.get('media_geral')}",
        f"Alunos abaixo da média: {estatisticas.get('qtd_abaixo_media')}",
        f"Percentual de aprovação: {estatisticas.get('percentual_aprovacao')}%",
        "",
    ]
    for row in resultados[:45]:
        linhas.append(
            f"{row.get('ranking')}. {row.get('aluno') or 'Turma'} | {row.get('disciplina')} | "
            f"{row.get('bimestre')} | {row.get('media_calculada')} | {row.get('situacao')}"
        )
    caminho.write_bytes(_pdf_simples("\n".join(linhas)))
    return caminho


def _selecionar_relatorio(df, relatorio, tipo_calculo):
    mapa = {
        "geral_turma": calcularMediaGeralTurma,
        "turma_bimestre": calcularMediaTurmaPorBimestre,
        "turma_anual": calcularMediaGeralTurma,
        "turma_disciplina": calcularMediaTurmaPorDisciplina,
        "turma_disciplina_bimestre": calcularMediaDisciplinaPorBimestre,
        "turma_area": calcularMediaAreaConhecimento,
        "aluno_geral": calcularMediaAluno,
        "aluno_bimestre": calcularMediaAlunoPorBimestre,
        "aluno_anual": calcularMediaAluno,
        "aluno_disciplina": calcularMediaAlunoPorDisciplina,
        "aluno_disciplina_bimestre": calcularMediaAlunoPorDisciplinaBimestre,
        "aluno_acumulada": calcularMediaAcumulada,
        "disciplina_geral": calcularMediaDisciplina,
        "disciplina_bimestre": calcularMediaDisciplinaPorBimestre,
        "disciplina_aluno": calcularMediaAlunoPorDisciplina,
        "ranking_disciplina": calcularMediaAlunoPorDisciplina,
        "bimestre_geral": calcularMediaBimestre,
        "bimestre_disciplina": calcularMediaDisciplinaPorBimestre,
        "bimestre_aluno": calcularMediaAlunoPorBimestre,
        "ranking_geral": calcularMediaAluno,
        "ranking_bimestre": calcularMediaAlunoPorBimestre,
        "alunos_risco": calcularMediaAluno,
        "evolucao_turma": calcularMediaTurmaPorBimestre,
        "evolucao_aluno": calcularMediaAlunoPorBimestre,
    }
    return mapa.get(relatorio, calcularMediaGeralTurma)(df, tipo_calculo)


def _df_valido_para_calculo(df, tipo_calculo):
    if df.empty:
        return df

    base = df.copy()
    base["valor_calculo"] = base["media_final_num"].combine_first(base["nota_num"])
    if tipo_calculo in {"media_acumulada", "descartar_menor"}:
        base["valor_calculo"] = base["nota_num"]
    return base.dropna(subset=["valor_calculo"])


def _agrupar(df, colunas, tipo_calculo, nomes_saida):
    if df.empty:
        return []

    resultados = []
    for chave, grupo in df.groupby(colunas, dropna=False):
        if not isinstance(chave, tuple):
            chave = (chave,)
        media = _calcular_serie(grupo, tipo_calculo)
        linha = _linha_resultado("", "", "", "", media, len(grupo))
        for nome, valor in zip(nomes_saida, chave):
            linha[nome] = valor
        resultados.append(linha)
    return resultados


def _calcular_serie(df, tipo_calculo):
    valores = list(df["valor_calculo"].dropna())
    if not valores:
        return None
    if tipo_calculo == "media_ponderada":
        return calcularMediaPonderada(valores, list(df.loc[df["valor_calculo"].notna(), "peso"]))
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
        media = row.get("media_calculada")
        row["situacao"] = classificarSituacaoAluno(media, media_minima, limite_recuperacao)
        row["observacao"] = _observacao(row, media_minima)
    return resultados


def _aplicar_filtros_de_desempenho(resultados, filtros, media_minima):
    somente = filtros.get("desempenho")
    if somente == "abaixo_media":
        resultados = [row for row in resultados if (row.get("media_calculada") or 0) < media_minima]
    elif somente == "acima_media":
        resultados = [row for row in resultados if (row.get("media_calculada") or 0) >= media_minima]

    ordenacao = filtros.get("ordenacao")
    if ordenacao == "maior_media":
        resultados = sorted(resultados, key=lambda row: row.get("media_calculada") or -1, reverse=True)
    elif ordenacao == "menor_media":
        resultados = sorted(resultados, key=lambda row: row.get("media_calculada") if row.get("media_calculada") is not None else 99)
    return resultados


def _estatisticas(df, resultados, media_minima):
    valores = list(df["valor_calculo"].dropna()) if not df.empty else []
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
    }


def _graficos(df, resultados):
    if df.empty:
        return {"bimestres": [], "disciplinas": []}
    bimestres = calcularMediaTurmaPorBimestre(df, "media_simples")
    disciplinas = sorted(calcularMediaTurmaPorDisciplina(df, "media_simples"), key=lambda row: row["media_calculada"] or 0)[:10]
    return {"bimestres": bimestres, "disciplinas": disciplinas}


def _observacao(row, media_minima):
    media = row.get("media_calculada")
    if media is None:
        return "Sem nota válida para cálculo"
    if media < media_minima:
        if row.get("disciplina"):
            return "Disciplina com rendimento abaixo da média"
        return "Aluno abaixo da média"
    if row.get("ranking") == 1:
        return "Maior média do grupo"
    return "Desempenho dentro do esperado"


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


def _opcoes(df, coluna):
    return sorted([valor for valor in df[coluna].dropna().unique().tolist() if str(valor).strip()])


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
    return 0


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
