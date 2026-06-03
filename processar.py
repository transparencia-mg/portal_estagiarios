import os
import re
import subprocess
from datetime import datetime

import pandas as pd

# =====================================================
# CONFIGURAÇÃO
# =====================================================

PASTA_BASE = r"C:\Users\kbomf\Google Drive\CGE\bi_atualizacao\portal_estagiarios"
PASTA_UPLOAD = os.path.join(PASTA_BASE, "upload")

ARQUIVO_DEPARA = os.path.join(
    PASTA_BASE,
    "de_para_orgao.xlsx"
)

# =====================================================
# LOG
# =====================================================

def log(msg):
    print(
        f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {msg}"
    )

# =====================================================
# LOCALIZAR ARQUIVO NOVO
# =====================================================

def localizar_arquivo_estagiarios():

    arquivos = [
        arq
        for arq in os.listdir(PASTA_UPLOAD)
        if re.match(
            r"^Estagi[aá]rios_\d{6}\.xlsx$",
            arq,
            re.IGNORECASE
        )
    ]

    if not arquivos:
        return None

    arquivos.sort(reverse=True)

    return os.path.join(
        PASTA_UPLOAD,
        arquivos[0]
    )

# =====================================================
# ANO
# =====================================================

def obter_ano(nome):

    match = re.search(
        r"(\d{4})(\d{2})",
        nome
    )

    if not match:
        raise Exception(
            "Não foi possível identificar AAAAMM."
        )

    return match.group(1)

# =====================================================
# DE PARA
# =====================================================

def atualizar_de_para(df):

    log("Lendo de_para_orgao.xlsx")

    depara = pd.read_excel(
        ARQUIVO_DEPARA,
        dtype=str
    ).fillna("")

    depara.columns = depara.columns.str.strip()

    depara["sigla"] = (
        depara["sigla"]
        .astype(str)
        .str.strip()
    )

    depara["orgao"] = (
        depara["orgao"]
        .astype(str)
        .str.strip()
    )

    mapa = dict(
        zip(
            depara["sigla"],
            depara["orgao"]
        )
    )

    siglas_arquivo = (
        df["Sigla"]
        .astype(str)
        .str.strip()
        .unique()
    )

    siglas_novas = sorted(
        set(siglas_arquivo)
        - set(mapa.keys())
        - {""}
    )

    if siglas_novas:

        print("\n")
        print("=" * 60)
        print("ERRO: SIGLAS NÃO CADASTRADAS")
        print("=" * 60)

        for sigla in siglas_novas:
            print(sigla)

        print("\nAtualize o de_para_orgao.xlsx e execute novamente.")

        raise Exception(
            "Existem siglas não cadastradas."
        )

    df["orgao"] = (
        df["Sigla"]
        .astype(str)
        .str.strip()
        .map(mapa)
        .fillna("")
    )

    return df

# =====================================================
# PADRONIZAÇÃO
# =====================================================

def formatar_valor_remuneracao(serie):
    return (
        serie
        .astype(str)
        .str.strip()
        # Remove separador de milhar: ponto seguido de exatamente 3 dígitos e depois vírgula ou fim
        .str.replace(r"\.(\d{3})(?=[,\.]|$)", r"\1", regex=True)
        # Troca vírgula decimal por ponto para pd.to_numeric entender
        .str.replace(",", ".", regex=False)
        .pipe(lambda s: pd.to_numeric(s, errors="coerce"))
        .map(
            lambda x: f"{x:.2f}".replace(".", ",")
            if pd.notna(x)
            else ""
        )
    )

def padronizar_layout(df):

    df = df.rename(columns={

        "Ano/Mês Referência": "ano_mesreferencia",
        "Nome Servidor": "nome_estagiario",
        "Masp/Admissão": "masp",
        "Cod Sit Funcional": "codigo_situacao_funcional",
        "Situação Funcional": "situacao_funcional",
        "Data Início": "data_inicio",
        "Data Fim": "data_fim",
        "Cod Orçamento Dotação": "codigo_orgao",
        "Sigla": "sigla_orgao",
        "Valor Remuneração": "valor_remuneracao"

    })

    # AAAAMM -> AAAA/MM
    df["ano_mesreferencia"] = (
        df["ano_mesreferencia"]
        .astype(str)
        .str.replace("/", "", regex=False)
        .str.strip()
    )

    df["ano_mesreferencia"] = (
        df["ano_mesreferencia"].str[:4]
        + "/"
        + df["ano_mesreferencia"].str[4:6]
    )

    # Remuneração padronizada (vírgula decimal)
    df["valor_remuneracao"] = formatar_valor_remuneracao(
        df["valor_remuneracao"]
    )

    # Remover horário das datas — FIX: usar .str.replace em vez de .replace
    for coluna in ["data_inicio", "data_fim"]:

        df[coluna] = (
            df[coluna]
            .astype(str)
            .str.replace(" 00:00:00", "", regex=False)
            .str.replace("nan", "", regex=False)  # FIX: era .replace("nan","")
        )

    colunas_finais = [
        "ano_mesreferencia",
        "nome_estagiario",
        "masp",
        "codigo_situacao_funcional",
        "situacao_funcional",
        "data_inicio",
        "data_fim",
        "codigo_orgao",
        "orgao",
        "sigla_orgao",
        "valor_remuneracao"
    ]

    return df[colunas_finais]


# =====================================================
# HISTÓRICO
# =====================================================

def atualizar_historico(df_novo, ano):

    arquivo_historico = os.path.join(
        PASTA_UPLOAD,
        f"estagiarios_{ano}.xlsx"
    )

    if os.path.exists(arquivo_historico):

        log(
            f"Lendo histórico: estagiarios_{ano}.xlsx"
        )

        df_hist = pd.read_excel(
            arquivo_historico,
            dtype=str
        ).fillna("")

        # FIX: normalizar valor_remuneracao do histórico com a mesma
        # função usada nos dados novos — garante "1388,64" em todos os casos
        if "valor_remuneracao" in df_hist.columns:
            df_hist["valor_remuneracao"] = formatar_valor_remuneracao(
                df_hist["valor_remuneracao"]
            )

    else:

        log(
            f"Criando histórico: estagiarios_{ano}.xlsx"
        )

        df_hist = pd.DataFrame()

    # FIX: todo este bloco estava fora da função no código original
    df_final = pd.concat(
        [df_hist, df_novo],
        ignore_index=True
    )

    df_final = df_final.drop_duplicates(
        subset=[
            "ano_mesreferencia",
            "masp"
        ],
        keep="last"
    )

    df_final.to_excel(
        arquivo_historico,
        index=False
    )

    log(
        f"Arquivo atualizado: estagiarios_{ano}.xlsx"
    )

# =====================================================
# GITHUB
# =====================================================

def atualizar_github():

    log("Atualizando GitHub...")

    try:

        subprocess.run(
            ["git", "add", "."],
            cwd=PASTA_BASE,
            check=True
        )

        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                f"Atualização automática estagiários {datetime.now():%Y-%m-%d %H:%M}"
            ],
            cwd=PASTA_BASE,
            check=False
        )

        subprocess.run(
            ["git", "push"],
            cwd=PASTA_BASE,
            check=True
        )

        log(
            "GitHub atualizado com sucesso."
        )

    except Exception as e:

        log(
            f"Erro ao atualizar GitHub: {e}"
        )

# =====================================================
# MAIN
# =====================================================

def main():

    arquivo = localizar_arquivo_estagiarios()

    if not arquivo:
        log(
            "Nenhum arquivo Estagiarios_AAAAMM.xlsx encontrado."
        )
        return

    nome = os.path.basename(arquivo)

    log(f"Processando {nome}")

    ano = obter_ano(nome)

    df = pd.read_excel(
        arquivo,
        dtype=str
    ).fillna("")

    df.columns = df.columns.str.strip()

    df = atualizar_de_para(df)

    df = padronizar_layout(df)

    atualizar_historico(
        df,
        ano
    )

    os.remove(arquivo)

    log(
        f"{nome} removido da pasta upload."
    )

    atualizar_github()

    log("Processamento concluído.")

if __name__ == "__main__":
    main()
