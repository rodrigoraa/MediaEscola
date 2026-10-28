"""Situação administrativa original do boletim (não é desempenho calculado)."""


def eh_transferido(situacao):
    return str(situacao or "").strip().casefold() in {"transferido", "transferida"}


def excluir_transferidos(linhas):
    return [linha for linha in linhas if not eh_transferido(linha.get("situacao"))]
