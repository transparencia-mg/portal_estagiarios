import os
import re
import subprocess
from datetime import datetime

import pandas as pd

# =====================================================
# CONFIGURAÇÃO
# =====================================================

PASTA_BASE = r"G:\Meu Drive\CGE\bi_atualizacao\portal_estagiarios"
PASTA_UPLOAD = os.path.join(PASTA_BASE, "upload")

ARQUIVO_DEPARA = os.path.join(PASTA_BASE, "de_para_orgao.xlsx")

# =====================================================
# FUNÇÕES
# =====================================================

def log(msg):
    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {msg}")


def localizar_arquivo_estagiarios():

    arquivos = [
        arq
        for arq in os.listdir(PASTA_UPLOAD)
        if re.match(r"^Estagiarios_\d{6}\.xlsx$", arq, re.IGNORECASE)
    ]

    if not arquivos:
        return None

    arquivos.sort(reverse=True)

    return os.path.join(
        PASTA_UPLOAD,
        arquivos[0]
    )


def obter_ano(nome_arquivo):
    match = re.search(r"(\d{4})(\d{2})", nome_arquivo)

    if not match:
        raise Exception("Não foi possível identificar AAAAMM do arquivo.")

    return match.group(1)


def atualizar_de_para(df, arquivo_depara):
    log("Lendo de_para_orgao.xlsx")

    depara = pd.read_excel(
        arquivo_depara,
        dtype=str
    ).fillna("")

    depara.columns = depara.columns.str.strip()

    mapa = dict(
        zip(
            depara["sigla"].str.strip(),
            depara["orgao"].str.strip()
        )
    )

    siglas_arquivo = (
        df["Sigla"]
        .fillna("")
        .astype(str)
        .str.strip()
        .unique()
    )

    novas = sorted(
        set(siglas_arquivo)
        - set(mapa.keys())
        - {""}
    )

    if novas:
        log(f"{len(novas)} siglas novas encontradas.")

        novos_registros = pd.DataFrame({
            "sigla": novas,
            "orgao": ["PREENCHER"] * len(novas)
        })

        depara = pd.concat(
            [depara, novos_registros],
            ignore_index=True
        )

        depara.to_excel(
            arquivo_depara,
            index=False
        )

        log("de_para_orgao.xlsx atualizado.")

        mapa = dict(
            zip(
                depara["sigla"].astype(str).str.strip(),
                depara["orgao"].astype(str).str.strip()
            )
        )

    df["orgao"] = (
        df["Sigla"]
        .fillna("")
        .astype(str)
        .str.strip()
        .map(mapa)
        .fillna("")
    )

    return df


def atualizar_historico(df_novo, ano):

    arquivo_historico = os.path.join(
        PASTA_UPLOAD,
        f"estagiarios_{ano}.xlsx"
    )

    if os.path.exists(arquivo_historico):

        log(f"Lendo histórico: {os.path.basename(arquivo_historico)}")

        df_hist = pd.read_excel(
            arquivo_historico,
            dtype=str
        ).fillna("")

    else:

        log(f"Criando histórico: {os.path.basename(arquivo_historico)}")

        df_hist = pd.DataFrame()

    df_final = pd.concat(
        [df_hist, df_novo],
        ignore_index=True
    )

    chaves = [
        "Ano/Mês",
        "Masp/Adm"
    ]

    if all(col in df_final.columns for col in chaves):

        antes = len(df_final)

        df_final = df_final.drop_duplicates(
            subset=chaves,
            keep="last"
        )

        depois = len(df_final)

        log(f"{antes - depois} duplicidades removidas.")

    df_final.to_excel(
        arquivo_historico,
        index=False
    )

    log(f"Arquivo atualizado: {os.path.basename(arquivo_historico)}")


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

        log("GitHub atualizado com sucesso.")

    except Exception as e:
        log(f"Erro ao atualizar GitHub: {e}")


# =====================================================
# PROCESSAMENTO
# =====================================================

def main():

    arquivo = localizar_arquivo_estagiarios()

    if not arquivo:
        log("Nenhum arquivo Estagiarios_AAAAMM.xlsx encontrado.")
        return

    nome = os.path.basename(arquivo)

    log(f"Processando {nome}")

    ano = obter_ano(nome)

    df = pd.read_excel(
        arquivo,
        dtype=str
    ).fillna("")

    df.columns = df.columns.str.strip()

    if "Sigla" not in df.columns:
        raise Exception(
            "Coluna 'Sigla' não encontrada."
        )

    df = atualizar_de_para(
        df,
        ARQUIVO_DEPARA
    )

    atualizar_historico(
        df,
        ano
    )

    os.remove(arquivo)

    log(f"{nome} removido da pasta upload.")

    atualizar_github()

    log("Processamento concluído.")


if __name__ == "__main__":
    main()