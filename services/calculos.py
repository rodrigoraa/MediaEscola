import pandas as pd


def gerar_analises(notas):
    """Calcula os indicadores principais a partir das linhas salvas."""
    df = pd.DataFrame(notas)

    if df.empty:
        return _analise_vazia()

    df["nota_num"] = df["nota"].apply(_to_float)
    df["media_final_num"] = df["media_final"].apply(_to_float)
    df_bimestres = df.dropna(subset=["nota_num"]).copy()
    df_anuais = _medias_anuais_por_disciplina(df)

    if df_anuais.empty and df_bimestres.empty:
        return _analise_vazia()

    media_por_aluno = _media(df_anuais, "nome_aluno", "aluno")
    media_por_disciplina = _media(df_anuais, "disciplina", "disciplina")
    media_por_bimestre = _media_bimestre(df_bimestres)
    media_aluno_por_bimestre = _media_aluno_bimestre(df_bimestres)
    media_aluno_por_disciplina = _media_aluno_disciplina(df_anuais)
    media_disciplina_por_bimestre = _media_disciplina_bimestre(df_bimestres)
    resumo_geral_por_disciplina = _resumo_geral_disciplina(df_anuais)

    media_geral = round(float(df_anuais["media"].mean()), 2) if not df_anuais.empty else None

    abaixo_media = (
        media_por_aluno[media_por_aluno["media"] < 6]
        .sort_values("media")
        .to_dict(orient="records")
    )
    melhores_medias = (
        media_por_aluno.sort_values("media", ascending=False)
        .head(10)
        .to_dict(orient="records")
    )
    menor_rendimento = (
        media_por_disciplina.sort_values("media")
        .head(10)
        .to_dict(orient="records")
    )

    return {
        "media_por_aluno": media_por_aluno.to_dict(orient="records"),
        "media_por_disciplina": media_por_disciplina.to_dict(orient="records"),
        "media_geral_turma": media_geral,
        "media_por_bimestre": media_por_bimestre.to_dict(orient="records"),
        "media_aluno_por_bimestre": media_aluno_por_bimestre.to_dict(orient="records"),
        "media_aluno_por_disciplina": media_aluno_por_disciplina.to_dict(orient="records"),
        "media_disciplina_por_bimestre": media_disciplina_por_bimestre.to_dict(orient="records"),
        "resumo_geral_por_disciplina": resumo_geral_por_disciplina.to_dict(orient="records"),
        "alunos_abaixo_media": abaixo_media,
        "melhores_medias": melhores_medias,
        "disciplinas_menor_rendimento": menor_rendimento,
    }


def _medias_anuais_por_disciplina(df):
    linhas = []

    for (aluno, disciplina), grupo in df.groupby(["nome_aluno", "disciplina"], dropna=False):
        media_final = grupo["media_final_num"].dropna()
        notas = grupo["nota_num"].dropna()

        if not media_final.empty:
            media = media_final.iloc[0]
        elif not notas.empty:
            media = notas.mean()
        else:
            continue

        linhas.append(
            {
                "nome_aluno": aluno,
                "disciplina": disciplina,
                "media": round(float(media), 2),
            }
        )

    return pd.DataFrame(linhas)


def _media(df, coluna, nome_coluna):
    if df.empty:
        return pd.DataFrame(columns=[nome_coluna, "media", "quantidade"])

    return (
        df.groupby(coluna, dropna=False)
        .agg(media=("media", "mean"), quantidade=("media", "count"))
        .reset_index()
        .rename(columns={coluna: nome_coluna})
        .assign(media=lambda dados: dados["media"].round(2))
        .sort_values("media", ascending=False)
    )


def _media_bimestre(df):
    if df.empty:
        return pd.DataFrame(columns=["bimestre", "media", "quantidade"])

    return (
        df.groupby("bimestre", dropna=False)
        .agg(media=("nota_num", "mean"), quantidade=("nota_num", "count"))
        .reset_index()
        .assign(media=lambda dados: dados["media"].round(2))
        .sort_values("bimestre")
    )


def _media_aluno_bimestre(df):
    if df.empty:
        return pd.DataFrame(columns=["aluno", "bimestre", "media", "quantidade"])

    return (
        df.groupby(["nome_aluno", "bimestre"], dropna=False)
        .agg(media=("nota_num", "mean"), quantidade=("nota_num", "count"))
        .reset_index()
        .rename(columns={"nome_aluno": "aluno"})
        .assign(media=lambda dados: dados["media"].round(2))
        .sort_values(["aluno", "bimestre"])
    )


def _media_aluno_disciplina(df):
    if df.empty:
        return pd.DataFrame(columns=["aluno", "disciplina", "media", "quantidade"])

    return (
        df.groupby(["nome_aluno", "disciplina"], dropna=False)
        .agg(media=("media", "mean"), quantidade=("media", "count"))
        .reset_index()
        .rename(columns={"nome_aluno": "aluno"})
        .assign(media=lambda dados: dados["media"].round(2))
        .sort_values(["disciplina", "media"], ascending=[True, False])
    )


def _media_disciplina_bimestre(df):
    if df.empty:
        return pd.DataFrame(columns=["disciplina", "bimestre", "media", "quantidade"])

    return (
        df.groupby(["disciplina", "bimestre"], dropna=False)
        .agg(media=("nota_num", "mean"), quantidade=("nota_num", "count"))
        .reset_index()
        .assign(media=lambda dados: dados["media"].round(2))
        .sort_values(["disciplina", "bimestre"])
    )


def _resumo_geral_disciplina(df):
    if df.empty:
        return pd.DataFrame(
            columns=["disciplina", "media", "menor_media", "maior_media", "alunos", "abaixo_media"]
        )

    resumo = (
        df.groupby("disciplina", dropna=False)
        .agg(
            media=("media", "mean"),
            menor_media=("media", "min"),
            maior_media=("media", "max"),
            alunos=("nome_aluno", "nunique"),
            abaixo_media=("media", lambda valores: int((valores < 6).sum())),
        )
        .reset_index()
    )

    for coluna in ["media", "menor_media", "maior_media"]:
        resumo[coluna] = resumo[coluna].round(2)

    return resumo.sort_values("media")


def _to_float(valor):
    if valor is None:
        return None

    texto = str(valor).strip().replace(",", ".")
    if not texto or texto.upper() == "SN":
        return None

    try:
        return float(texto)
    except ValueError:
        return None


def _analise_vazia():
    return {
        "media_por_aluno": [],
        "media_por_disciplina": [],
        "media_geral_turma": None,
        "media_por_bimestre": [],
        "media_aluno_por_bimestre": [],
        "media_aluno_por_disciplina": [],
        "media_disciplina_por_bimestre": [],
        "resumo_geral_por_disciplina": [],
        "alunos_abaixo_media": [],
        "melhores_medias": [],
        "disciplinas_menor_rendimento": [],
    }
