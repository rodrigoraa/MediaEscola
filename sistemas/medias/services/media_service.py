import csv
import logging
import math
import statistics
from datetime import datetime
from pathlib import Path

import pandas as pd

from .situacao import excluir_transferidos


logger = logging.getLogger("media_service")

MEDIA_MINIMA_PADRAO = 6.0
LIMITE_RECUPERACAO_PADRAO = 4.0

RELATORIOS = {
    "media_geral_turma": {
        "grupo": "Médias da Turma",
        "titulo": "Média Geral da Turma",
        "descricao": "Média dos valores anuais válidos, um por aluno e disciplina. Prioriza a Média Final do boletim.",
        "formula": "soma dos valores anuais válidos ÷ quantidade de pares aluno e disciplina válidos",
        "exemplo": "(8 + 7 + 6 + 9) ÷ 4 = 7,50",
        "filtros": [],
    },
    "media_turma_bimestre": {
        "grupo": "Médias da Turma",
        "titulo": "Média da Turma por Bimestre",
        "descricao": "Média de todas as notas da turma considerando apenas o bimestre selecionado.",
        "formula": "soma das notas do bimestre ÷ quantidade de notas do bimestre",
        "exemplo": "2º bimestre: soma das notas do 2º bimestre ÷ total de notas do 2º bimestre",
        "filtros": ["bimestre"],
    },
    "media_turma_disciplina": {
        "grupo": "Médias da Turma",
        "titulo": "Média da Turma por Disciplina",
        "descricao": "Média dos valores anuais dos alunos na disciplina. Prioriza a Média Final do boletim.",
        "formula": "soma dos valores anuais da disciplina ÷ quantidade de alunos com valor anual válido",
        "exemplo": "Matemática: finais 5 e 8 resultam em 6,50",
        "filtros": ["disciplina"],
    },
    "media_turma_disciplina_bimestre": {
        "grupo": "Médias da Turma",
        "titulo": "Média da Turma por Disciplina e Bimestre",
        "descricao": "Média da turma em determinada disciplina dentro de um bimestre específico.",
        "formula": "soma das notas da disciplina no bimestre ÷ quantidade dessas notas",
        "exemplo": "Matemática no 2º bimestre: notas de Matemática do 2º bimestre ÷ quantidade",
        "filtros": ["disciplina", "bimestre"],
    },
    "media_geral_aluno": {
        "grupo": "Médias do Aluno",
        "titulo": "Média Geral do Aluno",
        "descricao": "Média dos valores anuais válidos das disciplinas do aluno.",
        "formula": "soma dos valores anuais do aluno ÷ quantidade de disciplinas com valor anual válido",
        "exemplo": "Ana: finais 5 e 9 resultam em 7,00",
        "filtros": ["aluno"],
    },
    "media_aluno_bimestre": {
        "grupo": "Médias do Aluno",
        "titulo": "Média do Aluno por Bimestre",
        "descricao": "Média do aluno considerando todas as disciplinas apenas no bimestre selecionado.",
        "formula": "soma das notas do aluno no bimestre ÷ quantidade dessas notas",
        "exemplo": "Ana no 2º bimestre: notas da Ana no 2º bimestre ÷ quantidade",
        "filtros": ["aluno", "bimestre"],
    },
    "media_aluno_disciplina": {
        "grupo": "Médias do Aluno",
        "titulo": "Média do Aluno por Disciplina",
        "descricao": "Valor anual do aluno na disciplina: Média Final válida ou, somente se vazia, média dos bimestres válidos.",
        "formula": "Média Final; quando vazia, soma das notas bimestrais válidas ÷ quantidade dessas notas",
        "exemplo": "1º bimestre 10 e Média Final 5: resultado anual 5,00",
        "filtros": ["aluno", "disciplina"],
    },
    "media_aluno_disciplina_bimestre": {
        "grupo": "Médias do Aluno",
        "titulo": "Média do Aluno por Disciplina e Bimestre",
        "descricao": "Nota ou média do aluno em uma disciplina dentro de um bimestre específico.",
        "formula": "soma das notas do aluno na disciplina e bimestre ÷ quantidade dessas notas",
        "exemplo": "Ana em Matemática no 2º bimestre: notas encontradas ÷ quantidade",
        "filtros": ["aluno", "disciplina", "bimestre"],
    },
    "estatisticas": {
        "grupo": "Estatísticas",
        "titulo": "Estatísticas Gerais",
        "descricao": "Resumo dos valores anuais; com bimestre selecionado, utiliza apenas as notas daquele bimestre.",
        "formula": "maior nota, menor nota, mediana, moda, desvio padrão e percentuais de situação",
        "exemplo": "Use para diagnosticar distribuição e risco da turma.",
        "filtros": ["aluno", "disciplina", "bimestre"],
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
    df = pd.DataFrame(excluir_transferidos(notas))

    for coluna in ["boletim_id", "turma", "ano_letivo", "nome_aluno", "disciplina", "bimestre", "situacao", "nota", "media_final", "peso"]:
        if coluna not in df.columns:
            df[coluna] = ""

    for coluna in ["boletim_id", "turma", "ano_letivo"]:
        df[coluna] = df[coluna].fillna("")

    df["nota_num"] = df["nota"].apply(normalizar_nota)
    df["media_final_num"] = df["media_final"].apply(normalizar_nota)
    df["peso_num"] = df["peso"].apply(normalizar_peso)
    return df


def dados_bimestrais(df):
    """Somente notas válidas em bimestres identificados; não usa média final."""
    return df[df["nota_num"].notna() & df["bimestre"].fillna("").ne("")].copy()


def dados_anuais(df):
    """Uma contribuição anual por aluno/disciplina dentro da importação/turma/ano.

    `nota_num` nesta base contém o valor anual, compartilhando as agregações.
    O campo `media_final` original permanece intacto.
    """
    if "valor_anual" in df.columns:
        return df
    chaves = ["boletim_id", "turma", "ano_letivo", "nome_aluno", "disciplina"]
    linhas = []
    avisos = []
    for _, grupo in df.groupby(chaves, dropna=False, sort=True):
        finais = grupo["media_final_num"].dropna().unique()
        if len(finais) > 1:
            avisos.append(
                f"Médias Finais conflitantes para {grupo.iloc[0]['nome_aluno']} / "
                f"{grupo.iloc[0]['disciplina']}. Confira o boletim e corrija todas as ocorrências da Média Final."
            )
            continue
        if len(finais):
            valor = float(finais[0])
        elif grupo["media_final"].apply(_valor_vazio).all():
            notas = dados_bimestrais(grupo)["nota_num"]
            if notas.empty:
                continue
            valor = float(notas.mean())
        else:
            continue
        linha = grupo.iloc[0].to_dict()
        linha.update(nota_num=valor, valor_anual=valor, bimestre="")
        linhas.append(linha)
    resultado = pd.DataFrame(linhas, columns=[*df.columns, "valor_anual"])
    resultado.attrs["avisos"] = avisos
    return resultado


def validar_medias_finais(notas):
    """Diagnóstico compartilhado com importação e relatórios, sem escolher final."""
    return dados_anuais(preparar_dataframe(notas)).attrs.get("avisos", [])


def _valor_vazio(valor):
    return pd.isna(valor) or not str(valor).strip()


def resumir_disciplinas(notas, media_minima=MEDIA_MINIMA_PADRAO):
    df = dados_anuais(preparar_dataframe(notas))
    if df.empty:
        return []
    resumo = df.groupby("disciplina").agg(
        media=("nota_num", "mean"), menor_media=("nota_num", "min"),
        maior_media=("nota_num", "max"), alunos=("nota_num", "count"),
        abaixo_media=("nota_num", lambda v: int((v < media_minima).sum())),
    ).reset_index()
    return resumo.round(2).sort_values("media").to_dict(orient="records")


def opcoes_filtros(df):
    if df.empty:
        return {"alunos": [], "disciplinas": [], "bimestres": []}

    validos = df[df["nota_num"].notna() | df["media_final_num"].notna()]
    return {
        "alunos": _opcoes(validos, "nome_aluno"),
        "disciplinas": _opcoes(validos, "disciplina"),
        "bimestres": _ordenar_bimestres(_opcoes(dados_bimestrais(df), "bimestre")),
    }


def calcular_gerador_medias(notas, filtros):
    relatorio = normalizar_relatorio(filtros.get("relatorio") or "media_geral_turma")
    tipo_calculo = filtros.get("tipo_calculo") or "media_simples"
    media_minima = _float_config(filtros.get("media_minima"), MEDIA_MINIMA_PADRAO)
    limite_recuperacao = _float_config(filtros.get("limite_recuperacao"), LIMITE_RECUPERACAO_PADRAO)

    df_base = preparar_dataframe(notas)
    opcoes = opcoes_filtros(df_base)
    df_filtrado = aplicar_filtros(df_base, filtros, RELATORIOS[relatorio]["filtros"])
    bimestral = "bimestre" in RELATORIOS[relatorio]["filtros"]
    if relatorio == "estatisticas":
        bimestral = bool(filtros.get("bimestre"))
    filtros_anuais = [f for f in RELATORIOS[relatorio]["filtros"] if f != "bimestre"]
    df_anual = dados_anuais(aplicar_filtros(df_base, filtros, filtros_anuais))
    df_valido = dados_bimestrais(df_filtrado) if bimestral else df_anual

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
    if filtros.get("ordenacao") == "menor_media":
        resultados = list(reversed(resultados))
    estatisticas = _estatisticas(df_valido, resultados, media_minima)

    return {
        "opcoes": opcoes,
        "resultados": resultados,
        "estatisticas": estatisticas,
        "graficos": _graficos(df_filtrado, df_anual),
        "avisos": df_anual.attrs.get("avisos", []),
        "periodo": "bimestral" if bimestral else "anual",
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

    filtros_relevantes = set(filtros_relevantes if filtros_relevantes is not None else ["aluno", "disciplina", "bimestre"])
    resultado = df.copy()
    mapa = {
        "aluno": "nome_aluno",
        "disciplina": "disciplina",
        "bimestre": "bimestre",
    }

    for campo, coluna in mapa.items():
        valor = filtros.get(campo)
        if valor and campo in filtros_relevantes:
            resultado = resultado[resultado[coluna] == valor]

    return resultado


# Fórmula anual: um valor válido por aluno/disciplina.
def calcularMediaGeralTurma(df, tipo_calculo="media_simples"):
    df = dados_anuais(df)
    if df.empty:
        return []
    return [_linha_resultado("Turma", "", "", "", _calcular_media(df, tipo_calculo), len(df))]


# Fórmula: soma das notas do bimestre / quantidade de notas do bimestre.
def calcularMediaTurmaPorBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(dados_bimestrais(df), ["bimestre"], tipo_calculo, ["bimestre"])


# Fórmula anual: média dos valores anuais da disciplina.
def calcularMediaTurmaPorDisciplina(df, tipo_calculo="media_simples"):
    return _agrupar(dados_anuais(df), ["disciplina"], tipo_calculo, ["disciplina"])


# Fórmula: soma das notas da disciplina no bimestre / quantidade dessas notas.
def calcularMediaTurmaPorDisciplinaEBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(dados_bimestrais(df), ["disciplina", "bimestre"], tipo_calculo, ["disciplina", "bimestre"])


# Fórmula anual: média dos valores anuais das disciplinas do aluno.
def calcularMediaAluno(df, tipo_calculo="media_simples"):
    return _agrupar(dados_anuais(df), ["nome_aluno"], tipo_calculo, ["aluno"])


# Fórmula: soma das notas do aluno no bimestre / quantidade dessas notas.
def calcularMediaAlunoPorBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(dados_bimestrais(df), ["nome_aluno", "bimestre"], tipo_calculo, ["aluno", "bimestre"])


# Fórmula anual: valor anual único do aluno na disciplina.
def calcularMediaAlunoPorDisciplina(df, tipo_calculo="media_simples"):
    return _agrupar(dados_anuais(df), ["nome_aluno", "disciplina"], tipo_calculo, ["aluno", "disciplina"])


# Fórmula: soma das notas do aluno na disciplina e bimestre / quantidade dessas notas.
def calcularMediaAlunoPorDisciplinaEBimestre(df, tipo_calculo="media_simples"):
    return _agrupar(dados_bimestrais(df), ["nome_aluno", "disciplina", "bimestre"], tipo_calculo, ["aluno", "disciplina", "bimestre"])


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
    resultados = [r for r in resultados if r.get("media_calculada") is not None]
    ordenados = sorted(resultados, key=lambda row: (row["media_calculada"] is None, -(row["media_calculada"] or 0)))
    for posicao, row in enumerate(ordenados, start=1):
        row["ranking"] = posicao
    return ordenados


def classificarSituacaoAluno(media, media_minima=MEDIA_MINIMA_PADRAO, limite_recuperacao=LIMITE_RECUPERACAO_PADRAO):
    if media is None:
        return "Sem nota"
    if media >= media_minima:
        return "Acima da média"
    if media >= limite_recuperacao:
        return "Em atenção"
    return "Abaixo da média"


def exportar_resultados_csv(pasta_exportacao, resultados):
    caminho = Path(pasta_exportacao) / f"gerador_medias_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    campos = ["ranking", "aluno", "disciplina", "bimestre", "media_calculada", "situacao", "observacao", "formula"]
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


def exportar_resultados_pdf(pasta_exportacao, resultados, estatisticas, turma=""):
    sufixo_turma = f"_{_nome_arquivo_seguro(turma)}" if turma else ""
    caminho = Path(pasta_exportacao) / f"gerador_medias{sufixo_turma}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(_pdf_relatorio_medias(resultados, estatisticas, turma))
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
    if relatorio == "estatisticas":
        if df.empty:
            return []
        return [_linha_resultado("Turma", "", "", "", _calcular_media(df, tipo_calculo), len(df))]
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
    aprovados = len([r for r in resultados if r.get("situacao") == "Acima da média"])
    recuperacao = len([r for r in resultados if r.get("situacao") == "Em atenção"])
    reprovados = len([r for r in resultados if r.get("situacao") == "Abaixo da média"])
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
        "percentual_acima_media": _percentual(aprovados, total),
        "percentual_em_atencao": _percentual(recuperacao, total),
        "percentual_abaixo_media": _percentual(reprovados, total),
        "total_resultados": total,
        "notas_validas": len(valores),
    }


def _graficos(df, df_anual=None):
    if df.empty:
        return {"bimestres": [], "disciplinas": []}
    return {
        "bimestres": calcularMediaTurmaPorBimestre(df, "media_simples"),
        "disciplinas": sorted(
            calcularMediaTurmaPorDisciplina(df_anual if df_anual is not None else df, "media_simples"),
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
        numero = float(texto)
        return numero if math.isfinite(numero) and 0 <= numero <= 10 else None
    except (TypeError, ValueError):
        return None


def normalizar_peso(valor):
    try:
        peso = float(str(valor).strip().replace(",", "."))
        return peso if math.isfinite(peso) and peso > 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


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


def _pdf_relatorio_medias(resultados, estatisticas, turma=""):
    largura, altura = 842, 595
    margem = 36
    colunas = [
        ("Rank", 36, lambda row: row.get("ranking", "")),
        ("Aluno", 170, lambda row: row.get("aluno") or "Turma"),
        ("Disciplina", 168, lambda row: row.get("disciplina", "")),
        ("Bimestre", 86, lambda row: row.get("bimestre", "")),
        ("Média", 58, lambda row: _fmt(row.get("media_calculada"))),
        ("Situação", 88, lambda row: row.get("situacao", "")),
        ("Observação", 164, lambda row: row.get("observacao", "")),
    ]
    largura_tabela = sum(coluna[1] for coluna in colunas)
    paginas_resultados = _paginar_resultados_pdf(resultados, colunas, altura)
    total_paginas = len(paginas_resultados)
    streams = []

    for pagina_idx, linhas in enumerate(paginas_resultados, start=1):
        comandos = []
        _cabecalho_pdf(comandos, largura, altura, margem, pagina_idx, total_paginas, turma)

        if pagina_idx == 1:
            _resumo_pdf(comandos, estatisticas, margem, altura - 116)
            y = altura - 216
        else:
            y = altura - 116

        _retangulo(comandos, margem, y - 24, largura_tabela, 24, fill=(0.92, 0.96, 0.95), stroke=(0.78, 0.84, 0.82))
        x = margem
        for titulo, largura_coluna, _getter in colunas:
            _texto(comandos, titulo, x + 6, y - 15, 8.5, fonte="F2", cor=(0.10, 0.18, 0.25))
            x += largura_coluna

        y -= 24
        for idx, row in enumerate(linhas):
            altura_linha = _altura_linha(row, colunas)
            fill = (1, 1, 1) if idx % 2 == 0 else (0.97, 0.98, 0.99)
            _retangulo(comandos, margem, y - altura_linha, largura_tabela, altura_linha, fill=fill, stroke=(0.86, 0.89, 0.92))
            x = margem
            for _titulo, largura_coluna, getter in colunas:
                texto = str(getter(row) or "")
                for linha_idx, linha in enumerate(_quebrar_texto(texto, largura_coluna, 7.8)[:3]):
                    _texto(comandos, linha, x + 6, y - 13 - (linha_idx * 10), 7.8, cor=(0.16, 0.22, 0.30))
                x += largura_coluna
            y -= altura_linha

        _rodape_pdf(comandos, largura, margem, pagina_idx, total_paginas)
        streams.append("\n".join(comandos).encode("cp1252", errors="replace"))

    objetos = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        f"2 0 obj << /Type /Pages /Kids [{' '.join(f'{3 + i * 2} 0 R' for i in range(len(streams)))}] /Count {len(streams)} >> endobj\n".encode(),
    ]

    for idx, stream in enumerate(streams):
        page_obj = 3 + idx * 2
        content_obj = page_obj + 1
        objetos.append(
            f"{page_obj} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 {largura} {altura}] "
            f"/Resources << /Font << /F1 {3 + len(streams) * 2} 0 R /F2 {4 + len(streams) * 2} 0 R >> >> "
            f"/Contents {content_obj} 0 R >> endobj\n".encode()
        )
        objetos.append(
            f"{content_obj} 0 obj << /Length {len(stream)} >> stream\n".encode()
            + stream
            + b"\nendstream endobj\n"
        )

    objetos.extend(
        [
            f"{3 + len(streams) * 2} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> endobj\n".encode(),
            f"{4 + len(streams) * 2} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >> endobj\n".encode(),
        ]
    )

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


def _cabecalho_pdf(comandos, largura, altura, margem, pagina, total_paginas, turma=""):
    _retangulo(comandos, 0, altura - 78, largura, 78, fill=(0.12, 0.20, 0.29))
    _texto(comandos, "Média Escolar", margem, altura - 32, 15, fonte="F2", cor=(1, 1, 1))
    subtitulo = "Relatório do Gerador de Médias"
    if turma:
        subtitulo = f"{subtitulo} - Turma: {turma}"
    _texto(comandos, subtitulo, margem, altura - 54, 10, cor=(0.86, 0.91, 0.96))
    _texto(
        comandos,
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Página {pagina}/{total_paginas}",
        largura - 260,
        altura - 42,
        8.5,
        cor=(0.86, 0.91, 0.96),
    )


def _resumo_pdf(comandos, estatisticas, margem, y):
    cards = [
        ("Notas válidas", estatisticas.get("notas_validas")),
        ("Média geral", _fmt(estatisticas.get("media_geral"))),
        ("Maior nota", _fmt(estatisticas.get("maior_nota"))),
        ("Menor nota", _fmt(estatisticas.get("menor_nota"))),
        ("Abaixo da média", estatisticas.get("qtd_abaixo_media")),
        ("Acima da média", f"{str(estatisticas.get('percentual_acima_media', 0)).replace('.', ',')}%"),
    ]
    largura_card = 118
    for idx, (titulo, valor) in enumerate(cards):
        x = margem + idx * (largura_card + 12)
        _retangulo(comandos, x, y - 54, largura_card, 54, fill=(0.98, 0.99, 1), stroke=(0.82, 0.87, 0.92))
        _texto(comandos, titulo, x + 10, y - 18, 7.8, fonte="F2", cor=(0.37, 0.45, 0.55))
        _texto(comandos, str(valor if valor is not None else "-"), x + 10, y - 40, 15, fonte="F2", cor=(0.08, 0.32, 0.28))


def _rodape_pdf(comandos, largura, margem, pagina, total_paginas):
    _linha(comandos, margem, 34, largura - margem, 34, cor=(0.82, 0.87, 0.92))
    _texto(comandos, "Resultados calculados conforme os filtros selecionados no sistema.", margem, 20, 7.5, cor=(0.42, 0.48, 0.56))
    _texto(comandos, f"{pagina}/{total_paginas}", largura - margem - 26, 20, 7.5, cor=(0.42, 0.48, 0.56))


def _nome_arquivo_seguro(valor):
    texto = "".join(char if char.isalnum() else "_" for char in str(valor).strip())
    return "_".join(parte for parte in texto.split("_") if parte)[:80]


def _paginar_resultados_pdf(resultados, colunas, altura):
    if not resultados:
        return [[]]

    paginas = []
    pagina = []
    y = altura - 216
    limite_inferior = 72

    for row in resultados:
        altura_linha = _altura_linha(row, colunas)
        if pagina and y - altura_linha < limite_inferior:
            paginas.append(pagina)
            pagina = []
            y = altura - 116
        pagina.append(row)
        y -= altura_linha

    if pagina:
        paginas.append(pagina)
    return paginas


def _altura_linha(row, colunas):
    maior = 1
    for _titulo, largura, getter in colunas:
        maior = max(maior, len(_quebrar_texto(str(getter(row) or ""), largura, 7.8)))
    return max(26, min(maior, 3) * 10 + 12)


def _quebrar_texto(texto, largura, tamanho):
    limite = max(8, int(largura / (tamanho * 0.50)))
    palavras = str(texto or "-").split()
    linhas = []
    atual = ""
    for palavra in palavras:
        if len(palavra) > limite:
            if atual:
                linhas.append(atual)
                atual = ""
            linhas.extend(palavra[i : i + limite] for i in range(0, len(palavra), limite))
            continue
        tentativa = f"{atual} {palavra}".strip()
        if len(tentativa) <= limite:
            atual = tentativa
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas or ["-"]


def _retangulo(comandos, x, y, largura, altura, fill=None, stroke=None):
    if fill:
        comandos.append(f"{fill[0]} {fill[1]} {fill[2]} rg")
    if stroke:
        comandos.append(f"{stroke[0]} {stroke[1]} {stroke[2]} RG")
    operador = "B" if fill and stroke else "f" if fill else "S"
    comandos.append(f"{x:.2f} {y:.2f} {largura:.2f} {altura:.2f} re {operador}")


def _linha(comandos, x1, y1, x2, y2, cor=(0, 0, 0)):
    comandos.append(f"{cor[0]} {cor[1]} {cor[2]} RG")
    comandos.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")


def _texto(comandos, texto, x, y, tamanho, fonte="F1", cor=(0, 0, 0)):
    comandos.append(f"{cor[0]} {cor[1]} {cor[2]} rg")
    comandos.append(f"BT /{fonte} {tamanho} Tf {x:.2f} {y:.2f} Td ({_escape_pdf(str(texto)[:180])}) Tj ET")


def _fmt(valor):
    if valor is None or valor == "":
        return "-"
    try:
        return f"{float(valor):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(valor)


def _escape_pdf(texto):
    return (
        texto.encode("cp1252", errors="replace")
        .decode("cp1252")
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )
