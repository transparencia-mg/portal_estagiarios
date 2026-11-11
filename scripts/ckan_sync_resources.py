"""
Cria no CKAN os recursos que existem no datapackage.json local mas ainda
não existem no conjunto de dados publicado (ex.: estagiarios_2027).

Por que este script existe:
  O `dpckan dataset update` só percorre os recursos listados no campo extra
  `resources_ids` do dataset no CKAN. Um recurso novo no datapackage nunca
  entra nessa lista e, portanto, nunca é criado. Este script cria o recurso
  pela API do CKAN, registra o id em `resources_ids` e atualiza o
  datapackage.json remoto. Depois disso o `dpckan dataset update` passa a
  enxergar o recurso normalmente.

Uso (variáveis CKAN_HOST e CKAN_KEY no ambiente):
  python scripts/ckan_sync_resources.py [--datapackage dataset/datapackage.json] [--no-datastore]
"""
import argparse
import ast
import json
import os
import sys

from ckanapi import RemoteCKAN
from dpckan.functions import (
    load_complete_datapackage,
    is_dataset_published,
    resource_create,
    resource_update,
    update_datapackage_json_resource,
    get_ckan_datapackage_resource_id,
)


def ler_resources_ids(pacote_ckan):
    for extra in pacote_ckan.get("extras", []):
        if extra.get("key") == "resources_ids":
            valor = extra.get("value") or "{}"
            try:
                return json.loads(valor)
            except json.JSONDecodeError:
                return ast.literal_eval(valor)
    return {}


def gravar_resources_ids(ckan, pacote_ckan, resources_ids):
    # datapackage.json sempre por último, como o dpckan faz
    ordenado = {k: v for k, v in resources_ids.items() if k != "datapackage.json"}
    if "datapackage.json" in resources_ids:
        ordenado["datapackage.json"] = resources_ids["datapackage.json"]

    # package_patch substitui a lista inteira de extras, então reenviamos todas
    extras = [
        {"key": e["key"], "value": e["value"]}
        for e in pacote_ckan.get("extras", [])
        if e.get("key") != "resources_ids"
    ]
    extras.append({"key": "resources_ids", "value": json.dumps(ordenado)})
    ckan.call_action("package_patch", {"id": pacote_ckan["id"], "extras": extras})


def recurso_existente_por_arquivo(pacote_ckan, caminho_local):
    """Evita duplicar: se uma execução anterior criou o recurso mas falhou
    antes de gravar o resources_ids, reaproveita o recurso pelo nome do arquivo."""
    arquivo = os.path.basename(caminho_local)
    for r in pacote_ckan.get("resources", []):
        if (r.get("url") or "").split("/")[-1] == arquivo:
            return r["id"]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datapackage", default="dataset/datapackage.json")
    parser.add_argument("--no-datastore", action="store_true")
    args = parser.parse_args()
    datastore = not args.no_datastore

    host = os.getenv("CKAN_HOST")
    key = os.getenv("CKAN_KEY")
    if not host or not key:
        print("CKAN_HOST e CKAN_KEY precisam estar definidos.")
        sys.exit(1)

    datapackage = load_complete_datapackage(args.datapackage)
    ckan = RemoteCKAN(host, apikey=key)

    if not is_dataset_published(ckan, datapackage.name):
        print(f"Dataset {datapackage.name} ainda não existe no CKAN; a etapa de criação cuida disso.")
        return

    pacote = ckan.action.package_show(id=datapackage.name)
    resources_ids = ler_resources_ids(pacote)

    novos = [n for n in datapackage.resource_names if n not in resources_ids]
    if not novos:
        print("Nenhum recurso novo para criar no CKAN.")
        return

    for nome in novos:
        recurso = datapackage.get_resource(nome)
        if not recurso.title:
            recurso.title = nome
        id_existente = recurso_existente_por_arquivo(pacote, recurso.path)
        if id_existente:
            print(f"Recurso {nome} já existe no CKAN ({id_existente}); atualizando e registrando.")
            resource_update(ckan, id_existente, recurso, datastore)
            resources_ids[nome] = id_existente
        else:
            print(f"Criando recurso novo no CKAN: {nome}")
            criado = resource_create(ckan, datapackage.name, recurso, datastore)
            resources_ids[nome] = criado["id"]

    if "datapackage.json" not in resources_ids:
        resources_ids["datapackage.json"] = get_ckan_datapackage_resource_id(ckan, datapackage.name)

    gravar_resources_ids(ckan, pacote, resources_ids)

    # Atualiza o datapackage.json remoto para já conter os recursos novos,
    # senão a comparação de metadados do dpckan falha ao procurar o recurso.
    update_datapackage_json_resource(ckan, datapackage, resources_ids["datapackage.json"])

    print(f"Recursos criados/registrados: {', '.join(novos)}")


if __name__ == "__main__":
    main()
