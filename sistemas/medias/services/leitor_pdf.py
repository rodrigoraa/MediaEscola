import re
from pathlib import Path

import pdfplumber


BIMESTRES = ["1º Bimestre", "2º Bimestre", "3º Bimestre", "4º Bimestre"]
COLUNAS_DISCIPLINA = ("Componente Curricular", "Disciplina")
COLUNAS_FINAIS = {"média anual", "media anual", "exame", "média final", "media final"}
MARCADORES_PARADA = (
    "Número de Faltas",
    "Total de Faltas",
    "Observa",
    "Máximo de Faltas",
    "Frequência",
    "Legenda",
    "Situação Atual",
)


def extrair_boletim_pdf(caminho_pdf):
    """Lê o PDF com pdfplumber e devolve linhas prontas para conferência."""
    caminho_pdf = Path(caminho_pdf)
    linhas_extraidas = []

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text(x_tolerance=1, y_tolerance=3) or ""
            contexto = _extrair_contexto(texto)
            linhas_tabelas = _extrair_por_tabelas(pagina, contexto)
            linhas_texto = _extrair_por_texto(texto)

            linhas_extraidas.extend(linhas_tabelas or linhas_texto)

    return _remover_duplicados(linhas_extraidas)


def _extrair_por_tabelas(pagina, contexto=None):
    linhas = []
    contexto = contexto or {}
    aluno = contexto.get("aluno", "")
    turma = contexto.get("turma", "")
    ano_letivo = contexto.get("ano_letivo", "")
    situacao = contexto.get("situacao", "")

    for tabela in pagina.extract_tables() or []:
        if not tabela:
            continue

        cabecalho_idx = None

        for idx, row in enumerate(tabela):
            texto_row = " ".join(_limpar(celula) for celula in row if celula)
            if "Nome do Aluno" in texto_row:
                aluno = _valor_depois_de_rotulo(texto_row, "Nome do Aluno")
            if "Turma" in texto_row:
                turma = _valor_depois_de_rotulo(texto_row, "Turma")
            if "Ano Letivo" in texto_row:
                ano_letivo = _valor_depois_de_rotulo(texto_row, "Ano Letivo")
            if "Situação Atual do Aluno" in texto_row:
                situacao = _valor_depois_de_rotulo(texto_row, "Situação Atual do Aluno")
            if _linha_tem_coluna_disciplina(row):
                cabecalho_idx = idx
                break

        if cabecalho_idx is None:
            continue

        cabecalho = [_limpar(celula) for celula in tabela[cabecalho_idx]]
        coluna_disciplina = _nome_coluna_disciplina(cabecalho)

        for row in tabela[cabecalho_idx + 1 :]:
            registro = dict(zip(cabecalho, [_limpar(celula) for celula in row]))
            disciplina = registro.get(coluna_disciplina, "").strip()

            if not disciplina or _eh_marcador_parada(disciplina):
                continue

            linhas.extend(_montar_linhas_disciplina(aluno, disciplina, registro, situacao, turma, ano_letivo))

    return linhas


def _extrair_contexto(texto):
    linhas_texto = [_limpar(linha) for linha in texto.splitlines() if _limpar(linha)]
    return {
        "aluno": _buscar_valor_linha(linhas_texto, "Nome do Aluno"),
        "turma": _buscar_rotulo_no_bloco(texto, "Turma", ["Componente Curricular", "Disciplina", "Turno"]),
        "ano_letivo": _buscar_rotulo_no_bloco(texto, "Ano Letivo", ["Ensino Fundamental", "Ensino Médio", "Ano/Fase", "Turno", "Turma"]),
        "situacao": _buscar_valor_linha(linhas_texto, "Situação Atual do Aluno"),
    }


def _extrair_por_texto(texto):
    linhas = []
    blocos = re.split(r"(?=Nome do Aluno:)", texto)

    for bloco in blocos:
        if "Nome do Aluno" not in bloco or not _tem_cabecalho_disciplina(bloco):
            continue

        linhas_texto = [_limpar(linha) for linha in bloco.splitlines() if _limpar(linha)]
        aluno = _buscar_valor_linha(linhas_texto, "Nome do Aluno")
        turma = _buscar_rotulo_no_bloco(bloco, "Turma", ["Componente Curricular", "Disciplina", "Turno"])
        ano_letivo = _buscar_rotulo_no_bloco(bloco, "Ano Letivo", ["Ensino Fundamental", "Ensino Médio", "Ano/Fase", "Turno", "Turma"])
        situacao = _buscar_valor_linha(linhas_texto, "Situação Atual do Aluno")

        inicio = _indice_cabecalho_disciplina(linhas_texto)
        if inicio is None:
            continue

        conteudo = []
        for linha in linhas_texto[inicio + 1 :]:
            if _eh_marcador_parada(linha):
                break
            if _eh_cabecalho_tabela(linha):
                continue
            conteudo.append(linha)

        linhas.extend(_parsear_linhas_sequenciais(aluno, conteudo, situacao, turma, ano_letivo))

    return linhas


def _parsear_linhas_sequenciais(aluno, linhas, situacao, turma="", ano_letivo=""):
    registros = []
    disciplina_atual = None
    valores = []

    def fechar_disciplina():
        if disciplina_atual and valores:
            registros.extend(_montar_linhas_por_valores(aluno, disciplina_atual, valores, situacao, turma, ano_letivo))

    for linha in linhas:
        if _eh_valor_nota(linha):
            valores.append(linha)
            continue

        disciplina, valores_linha = _separar_disciplina_valores(linha)
        if disciplina and valores_linha:
            fechar_disciplina()
            disciplina_atual = disciplina
            valores = valores_linha
            continue

        if disciplina_atual and valores and not _eh_marcador_parada(linha):
            disciplina_atual = f"{disciplina_atual} {linha}"
            continue

        fechar_disciplina()
        disciplina_atual = linha
        valores = []

    fechar_disciplina()
    return registros


def _montar_linhas_disciplina(aluno, disciplina, registro, situacao, turma="", ano_letivo=""):
    linhas = []
    media_final = _primeiro_valor(registro, ["Média Final", "Media Final", "Média Anual", "Media Anual"])

    for bimestre in BIMESTRES:
        nota = registro.get(bimestre, "")
        if nota:
            linhas.append(_linha(aluno, disciplina, bimestre, nota, media_final, situacao, turma, ano_letivo))

    if not linhas and media_final:
        linhas.append(_linha(aluno, disciplina, "", "", media_final, situacao, turma, ano_letivo))

    return linhas


def _montar_linhas_por_valores(aluno, disciplina, valores, situacao, turma="", ano_letivo=""):
    # No texto linear do boletim, notas finais costumam aparecer depois dos bimestres.
    media_final = valores[-1] if len(valores) >= 2 else ""
    qtd_bimestres = min(len(valores), 4)

    if len(valores) >= 3:
        qtd_bimestres = min(len(valores) - 2, 4) or 1

    return [
        _linha(aluno, disciplina, BIMESTRES[idx], valores[idx], media_final, situacao, turma, ano_letivo)
        for idx in range(qtd_bimestres)
    ]


def _linha(aluno, disciplina, bimestre, nota, media_final, situacao, turma="", ano_letivo=""):
    return {
        "nome_aluno": aluno,
        "disciplina": disciplina,
        "bimestre": bimestre,
        "nota": nota,
        "media_final": media_final,
        "situacao": situacao,
        "turma": turma,
        "ano_letivo": ano_letivo,
    }


def _remover_duplicados(linhas):
    vistos = set()
    unicas = []

    for linha in linhas:
        chave = tuple(linha.get(campo, "") for campo in ("nome_aluno", "disciplina", "bimestre", "nota", "media_final"))
        if chave in vistos:
            continue
        vistos.add(chave)
        unicas.append(linha)

    return unicas


def _limpar(valor):
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def _valor_depois_de_rotulo(texto, rotulo):
    texto = texto.replace(":", ": ")
    match = re.search(rf"{re.escape(rotulo)}\s*:?\s*(.*)", texto, re.IGNORECASE)
    return _limpar(match.group(1)) if match else ""


def _buscar_valor_linha(linhas, rotulo):
    for idx, linha in enumerate(linhas):
        if rotulo in linha:
            valor = _valor_depois_de_rotulo(linha, rotulo)
            if valor:
                return valor
            if idx + 1 < len(linhas):
                return linhas[idx + 1]
    return ""


def _buscar_rotulo_no_bloco(texto, rotulo, proximos_rotulos):
    padrao_parada = "|".join(re.escape(item) for item in proximos_rotulos)
    match = re.search(rf"{re.escape(rotulo)}:\s*(.*?)(?:\s+(?:{padrao_parada})(?::|\b)|$)", texto, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return _limpar(match.group(1))


def _indice_linha(linhas, termo):
    for idx, linha in enumerate(linhas):
        if termo in linha:
            return idx
    return None


def _indice_cabecalho_disciplina(linhas):
    for termo in COLUNAS_DISCIPLINA:
        idx = _indice_linha(linhas, termo)
        if idx is not None:
            return idx
    return None


def _tem_cabecalho_disciplina(texto):
    return any(coluna in texto for coluna in COLUNAS_DISCIPLINA)


def _linha_tem_coluna_disciplina(row):
    return any(_limpar(celula) in COLUNAS_DISCIPLINA for celula in row if celula)


def _nome_coluna_disciplina(cabecalho):
    for coluna in COLUNAS_DISCIPLINA:
        if coluna in cabecalho:
            return coluna
    return COLUNAS_DISCIPLINA[0]


def _eh_valor_nota(linha):
    return bool(re.fullmatch(r"(SN|[0-9]{1,2}(?:[,.][0-9]{1,2})?)", linha.strip(), flags=re.IGNORECASE))


def _separar_disciplina_valores(linha):
    partes = linha.split()
    valores = []

    while partes and _eh_valor_nota(partes[-1]):
        valores.insert(0, partes.pop())

    return " ".join(partes).strip(), valores


def _eh_cabecalho_tabela(linha):
    texto = linha.lower()
    return linha in BIMESTRES or linha in COLUNAS_DISCIPLINA or texto in COLUNAS_FINAIS


def _eh_marcador_parada(linha):
    return any(linha.startswith(marcador) for marcador in MARCADORES_PARADA)


def _primeiro_valor(registro, chaves):
    for chave in chaves:
        valor = registro.get(chave, "")
        if valor:
            return valor
    return ""
