from dotenv import load_dotenv
import copy
import os
import re

import yaml
from frictionless import describe

load_dotenv()

YAML_PATH = 'dataset/datapackage.yaml'


class IndentDumper(yaml.SafeDumper):
    # Mantém listas indentadas como o frictionless grava, para o diff ficar limpo
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def create_datapackage_yaml():
    dataset_files = os.listdir('dataset')
    if 'datapackage.yaml' not in dataset_files:
        package = describe('./data', type='package', basepath='./dataset')
        package['name'] = os.getenv("DATASET_NAME")
        package['title'] = ' '.join(os.getenv("DATASET_NAME").split('-')).capitalize()
        package['owner_org'] = os.getenv("OWNER_ORG")
        for resource in package.resources:
            resource['description'] = 'Insira a descrição/explicação detalhada deste recurso.'
            resource['title'] = 'Insira um título humanamente legível para este recurso.'
        package.to_yaml(YAML_PATH)
    else:
        add_new_resources()


def add_new_resources():
    """Inclui no datapackage.yaml os CSVs de dataset/data que ainda não estão
    listados. O recurso novo copia schema/dialeto do recurso mais parecido
    (mesmo prefixo, ex.: estagiarios_2026 -> estagiarios_2027) e troca o ano
    no título."""
    with open(YAML_PATH, encoding='utf-8') as f:
        package = yaml.safe_load(f)

    resources = package.setdefault('resources', [])
    paths = {r.get('path') for r in resources}
    csvs = sorted(f for f in os.listdir('dataset/data') if f.endswith('.csv'))
    added = []

    for csv in csvs:
        path = f'data/{csv}'
        if path in paths:
            continue
        name = csv[:-4]
        prefix = re.sub(r'\d+$', '', name)
        modelo = [r for r in resources if re.sub(r'\d+$', '', r.get('name', '')) == prefix]

        if modelo:
            novo = copy.deepcopy(modelo[-1])
            ano_antigo = re.search(r'(\d+)$', modelo[-1]['name'])
            ano_novo = re.search(r'(\d+)$', name)
            titulo = novo.get('title', name)
            if ano_antigo and ano_novo:
                titulo = titulo.replace(ano_antigo.group(1), ano_novo.group(1))
            novo.update({'name': name, 'path': path, 'title': titulo})
            novo.pop('hash', None)
            novo.pop('bytes', None)
        else:
            novo = describe(path, basepath='./dataset').to_dict()
            novo['title'] = 'Insira um título humanamente legível para este recurso.'
            novo['description'] = 'Insira a descrição/explicação detalhada deste recurso.'

        resources.append(novo)
        added.append(name)

    if added:
        with open(YAML_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(package, f, Dumper=IndentDumper, allow_unicode=True, sort_keys=False)
        print(f"Recursos incluídos no datapackage.yaml: {', '.join(added)}")
    else:
        print("datapackage.yaml já contém todos os CSVs.")


if __name__ == '__main__':
    create_datapackage_yaml()
