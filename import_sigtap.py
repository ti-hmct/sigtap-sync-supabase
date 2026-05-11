import os
import requests
import zipfile
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# Configurações do Banco via Secret do GitHub
db_url = os.getenv('SUPABASE_DB_URL')
if not db_url:
    raise ValueError("Variável SUPABASE_DB_URL não configurada!")

engine = create_engine(db_url)

# Dicionário de Layout (Posições oficiais do SIGTAP)
LAYOUTS = {
    'tb_procedimento.txt': {
        'table': 'tb_procedimento',
        'comp_col': 'dt_competencia', # Esta tabela já tem coluna de competência
        'fields': [('co_procedimento', 0, 10), ('no_procedimento', 10, 260), ('tp_complexidade', 260, 261), 
                   ('tp_sexo', 261, 262), ('nu_vlr_sh', 262, 272), ('nu_vlr_sa', 272, 282), ('nu_vlr_sp', 282, 292), 
                   ('co_financiamento', 292, 294), ('co_rubrica', 294, 300), ('nu_tempo_permanencia', 300, 304), ('dt_competencia', 304, 310)]
    },
    'tb_cid.txt': {
        'table': 'tb_cid',
        'comp_col': None, # Tabela original não tem competência (histórico aqui requer cuidado)
        'fields': [('co_cid', 0, 4), ('no_cid', 4, 104), ('st_agravo', 104, 105), ('st_sexo', 105, 106), ('st_estadio', 106, 107), ('vl_campos_irradiados', 107, 111)]
    },
    'tb_ocupacao.txt': {
        'table': 'tb_ocupacao',
        'comp_col': None,
        'fields': [('co_ocupacao', 0, 6), ('no_ocupacao', 6, 156)]
    },
    'rl_procedimento_cid.txt': {
        'table': 'rl_procedimento_cid',
        'comp_col': 'dt_competencia',
        'fields': [('co_procedimento', 0, 10), ('co_cid', 10, 14), ('st_principal', 14, 15), ('dt_competencia', 15, 21)]
    },
    'rl_procedimento_ocupacao.txt': {
        'table': 'rl_procedimento_ocupacao',
        'comp_col': 'dt_competencia',
        'fields': [('co_procedimento', 0, 10), ('co_ocupacao', 10, 16), ('dt_competencia', 16, 22)]
    },
    'tb_registro.txt': {
        'table': 'tb_registro',
        'comp_col': 'dt_competencia',
        'fields': [('co_registro', 0, 2), ('no_registro', 2, 52), ('dt_competencia', 52, 58)]
    },
    'tb_modalidade.txt': {
        'table': 'tb_modalidade',
        'comp_col': 'dt_competencia',
        'fields': [('co_modalidade', 0, 2), ('no_modalidade', 2, 102), ('dt_competencia', 102, 108)]
    },
    'tb_componente_rede.txt': {
        'table': 'tb_componente_rede',
        'comp_col': 'dt_competencia',
        'fields': [('co_componente', 0, 4), ('no_componente', 4, 104), ('dt_competencia', 104, 110)]
    }
}

def download_sigtap():
    comp = datetime.now().strftime("%Y%m")
    url_http = f"http://sia.datasus.gov.br/dissemin/publicos/SIGTAP/{comp}/TabelaUnificada_{comp}.zip"
    print(f"Buscando competência {comp}...")
    
    res = requests.get(url_http, timeout=60)
    if res.status_code != 200:
        print("Mês atual ainda não disponível no DATASUS.")
        return None
    
    with open("sigtap.zip", "wb") as f: f.write(res.content)
    with zipfile.ZipFile("sigtap.zip", 'r') as z: z.extractall("extraido")
    return comp

def process_files(comp_atual):
    for arq, info in LAYOUTS.items():
        caminho = os.path.join("extraido", arq)
        if os.path.exists(caminho):
            print(f"Processando {arq}...")
            cols = [f[0] for f in info['fields']]
            positions = [(f[1], f[2]) for f in info['fields']]
            
            df = pd.read_fwf(caminho, colspecs=positions, names=cols, encoding='latin1', dtype=str)
            
            # Se a tabela tem coluna de competência, limpamos o mês atual antes de inserir (evita duplicados)
            if info['comp_col']:
                with engine.connect() as conn:
                    conn.execute(text(f"DELETE FROM {info['table']} WHERE {info['comp_col']} = '{comp_atual}'"))
                    conn.commit()
            
            # Modo APPEND (Acumular)
            df.to_sql(info['table'], engine, if_exists='append', index=False)
            print(f"Sucesso: Dados de {comp_atual} adicionados em {info['table']}.")

if __name__ == "__main__":
    competencia = download_sigtap()
    if competencia:
        process_files(competencia)
