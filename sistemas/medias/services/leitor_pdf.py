"""Leitura estrutural; nunca inferir colunas a partir de uma lista de números."""
import re
import unicodedata
from pathlib import Path

import pdfplumber

from .situacao import eh_transferido, excluir_transferidos

BIMESTRES = ["1º Bimestre", "2º Bimestre", "3º Bimestre", "4º Bimestre"]
COLUNAS_DISCIPLINA = ("Componente Curricular", "Disciplina")
COLUNAS = ["disciplina", *BIMESTRES, "media_anual", "exame", "media_final"]
MARCADORES_PARADA = ("Número de Faltas", "Total de Faltas", "Observa", "Máximo de Faltas",
                      "Frequência", "Legenda", "Situação Atual")
ERRO_COLUNAS = "Não foi possível reconhecer as colunas com segurança. Confira o PDF e envie um boletim com tabela legível."


def extrair_boletim_pdf(caminho_pdf):
    linhas = []
    with pdfplumber.open(Path(caminho_pdf)) as pdf:
        for numero, pagina in enumerate(pdf.pages, 1):
            texto = pagina.extract_text(x_tolerance=1, y_tolerance=3) or ""
            if len(re.findall(r"Nome do Aluno\s*:", texto, re.I)) > 1:
                raise ValueError(f"Página {numero}: mais de um aluno; separe os boletins por página para conferência.")
            contexto = _extrair_contexto(texto)
            if eh_transferido(contexto["situacao"]):
                continue
            try:
                registros = _extrair_por_tabelas(pagina, contexto)
                if not registros:
                    registros = _extrair_por_texto(texto)
                if not registros:
                    raise ValueError(ERRO_COLUNAS)
            except ValueError as exc:
                raise ValueError(f"Página {numero}: {exc}") from exc
            linhas.extend(registros)
    return _remover_duplicados(excluir_transferidos(linhas))


def _coluna(valor):
    texto = unicodedata.normalize("NFKD", _limpar(valor).casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    if texto in {"disciplina", "componente curricular", "disciplina ou componente curricular"}:
        return "disciplina"
    for i, bimestre in enumerate(BIMESTRES, 1):
        if re.fullmatch(rf"{i}[^\w]*[oa]?\s*bimestre", texto):
            return bimestre
    return {"media anual": "media_anual", "exame": "exame", "media final": "media_final"}.get(texto)


def _validar_cabecalho(row):
    colunas = [_coluna(c) for c in row]
    if len(colunas) != len(COLUNAS) or set(colunas) != set(COLUNAS):
        raise ValueError(ERRO_COLUNAS)
    return colunas


def _extrair_por_tabelas(pagina, contexto=None):
    contexto = contexto or {}
    linhas = []
    for tabela in pagina.extract_tables() or []:
        cabecalho = None
        for row in tabela:
            if any(_coluna(c) == "disciplina" for c in row):
                cabecalho = _validar_cabecalho(row)
                continue
            if cabecalho is None:
                continue
            if len(row) != len(cabecalho):
                raise ValueError(ERRO_COLUNAS)
            registro = dict(zip(cabecalho, [_limpar(c) for c in row]))
            disciplina = registro["disciplina"]
            if _eh_marcador_parada(disciplina):
                break
            if not disciplina:
                if any(registro.values()):
                    raise ValueError(ERRO_COLUNAS)
                continue
            linhas.extend(_montar_linhas_disciplina(contexto, disciplina, registro))
    return linhas


def _extrair_por_texto(texto):
    """Fallback conservador: apenas oito colunas explicitamente delimitadas.

    extract_text() linear descarta vazios. Mesmo sete números não provam suas
    posições; sem tabela ou delimitadores a importação deve parar para revisão.
    """
    contexto = _extrair_contexto(texto)
    if eh_transferido(contexto["situacao"]):
        return []
    cabecalho = None
    linhas = []
    for raw in texto.splitlines():
        if _eh_marcador_parada(raw.strip()) and cabecalho:
            break
        if "|" not in raw:
            if cabecalho and raw.strip():
                raise ValueError(ERRO_COLUNAS)
            continue
        row = raw.split("|")
        if any(_coluna(c) == "disciplina" for c in row):
            cabecalho = _validar_cabecalho(row)
            continue
        if cabecalho:
            if len(row) != len(cabecalho):
                raise ValueError(ERRO_COLUNAS)
            registro = dict(zip(cabecalho, [_limpar(c) for c in row]))
            if not registro["disciplina"]:
                raise ValueError(ERRO_COLUNAS)
            linhas.extend(_montar_linhas_disciplina(contexto, registro["disciplina"], registro))
    if not linhas:
        raise ValueError(ERRO_COLUNAS)
    return linhas


def _extrair_contexto(texto):
    linhas = [_limpar(linha) for linha in texto.splitlines() if _limpar(linha)]
    return {
        "aluno": _buscar_valor_linha(linhas, "Nome do Aluno"),
        "turma": _buscar_rotulo_no_bloco(texto, "Turma", ["Componente Curricular", "Disciplina", "Turno"]),
        "ano_letivo": _buscar_rotulo_no_bloco(texto, "Ano Letivo", ["Ensino Fundamental", "Ensino Médio", "Ano/Fase", "Turno", "Turma"]),
        "situacao": _buscar_valor_linha(linhas, "Situação Atual do Aluno"),
    }


def _montar_linhas_disciplina(contexto, disciplina, registro):
    if not contexto.get("aluno"):
        raise ValueError("Aluno não identificado. Confira o PDF antes de importar.")
    return [{
        "nome_aluno": contexto["aluno"], "disciplina": disciplina,
        "bimestre": bimestre, "nota": registro.get(bimestre, ""),
        "media_final": registro.get("media_final", ""),
        "situacao": contexto.get("situacao", ""), "turma": contexto.get("turma", ""),
        "ano_letivo": contexto.get("ano_letivo", ""),
    } for bimestre in BIMESTRES]


def _remover_duplicados(linhas):
    vistos = set()
    resultado = []
    for linha in linhas:
        chave = tuple(linha.items())
        if chave not in vistos:
            vistos.add(chave)
            resultado.append(linha)
    return resultado


def _eh_marcador_parada(linha):
    return any(linha.casefold().startswith(m.casefold()) for m in MARCADORES_PARADA)


def _limpar(valor):
    return re.sub(r"\s+", " ", str(valor if valor is not None else "")).strip()


def _valor_depois_de_rotulo(texto, rotulo):
    texto = texto.replace(":", ": ")
    match = re.search(rf"{re.escape(rotulo)}\s*:?\s*(.*)", texto, re.IGNORECASE)
    return _limpar(match.group(1)) if match else ""


def _buscar_valor_linha(linhas, rotulo):
    for idx, linha in enumerate(linhas):
        if rotulo.casefold() in linha.casefold():
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
