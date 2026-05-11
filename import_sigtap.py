import os
import requests
import zipfile
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# 1. Configurações de Conexão
db_url = os.getenv('SUPABASE_DB_URL')
if not db_url:
    raise ValueError("A variável SUPABASE_DB_URL não foi configurada nos Secrets!")

engine = create_engine(db_url)

# 2. Definição dos Layouts (As 8 tabelas do seu esquema)
LAYOUTS = {
    'tb_procedimento.txt': {
        'table': 'tb_procedimento',
        'comp_col': 'dt_competencia',
        'fields': [('co_procedimento', 0, 10), ('no_procedimento', 10, 260), ('tp_complexidade', 260, 261), 
                   ('tp_sexo', 261, 262), ('nu_vlr_sh', 262, 272), ('nu_vlr_sa', 272, 282), ('nu_vlr_sp', 282, 292), 
                   ('co_financiamento', 292, 294), ('co_rubrica', 294, 300), ('nu_tempo_permanencia', 300, 304), ('dt_competencia', 304, 310)]
    },
    'tb_cid.txt': {
        'table': 'tb_cid',
        'comp_col': None,
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
    url = f"http://sia.datasus.gov.br/dissemin/publicos/SIGTAP/{comp}/TabelaUnificada_{comp}.zip"
    print(f"Buscando SIGTAP competência {comp}...")
    
    try:
        res = requests.get(url, timeout=60)
        if res.status_code != 200:
            print(f"Arquivo de {comp} ainda não disponível no DATASUS.")
            return None
        
        with open("sigtap.zip", "wb") as f:
            f.write(res.content)
        
        with zipfile.ZipFile("sigtap.zip", 'r') as z:
            z.extractall("extraido")
        return comp
    except Exception as e:
        print(f"Erro ao baixar arquivo: {e}")
        return None

def process_files(comp_atual):
    agora = datetime.now()
    for arq, info in LAYOUTS.items():
        caminho = os.path.join("extraido", arq)
        if os.path.exists(caminho):
            print(f"--- Lendo {arq} ---")
            cols = [f[0] for f in info['fields']]
            positions = [(f[1], f[2]) for f in info['fields']]
            
            # Carrega o arquivo de largura fixa
            df = pd.read_fwf(caminho, colspecs=positions, names=cols, encoding='latin1', dtype=str)
            
            # Adiciona o carimbo de tempo da importação
            df['importado_em'] = agora
            
            # Lógica de Histórico Inteligente
            if info['comp_col']:
                # Se a tabela tem competência, removemos apenas o mês atual para evitar duplicidade
                print(f"Limpando registros existentes de {comp_atual} em {info['table']}...")
                with engine.connect() as conn:
                    conn.execute(text(f"DELETE FROM {info['table']} WHERE {info['comp_col']} = '{comp_atual}'"))
                    conn.commit()
            
            # Insere os dados (Modo Append para acumular meses diferentes)
            print(f"Inserindo dados em {info['table']}...")
            df.to_sql(info['table'], engine, if_exists='append', index=False)
            print(f"Sucesso! {len(df)} linhas processadas.")
        else:
            print(f"Aviso: Arquivo {arq} não encontrado no pacote ZIP.")

if __name__ == "__main__":
    competencia = download_sigtap()
    if competencia:
        process_files(competencia)
        print("\n=== PROCESSO FINALIZADO COM SUCESSO ===")
    else:
        print("Execução abortada: Arquivo não disponível.")
