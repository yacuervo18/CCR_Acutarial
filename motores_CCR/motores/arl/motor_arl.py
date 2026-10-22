"""ARL engine converted from the original notebook.

Calculation cells preserve their source and order.
Execution adjustments: motor-relative working directory and config_cierre.txt.
"""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)

# %% Celda 0
from getpass import getpass
import pandas as pd
 
df = pd.read_excel('utils.xlsx', engine='openpyxl')
excel_password = df['Contraseña'].iloc[0]
 
password = os.environ.pop("MOTOR_ARL_PASSWORD", None)
if password is None:
    password = getpass("Introduce la contraseña para ejecutar el notebook: ")
if password != excel_password:
    print("Contraseña incorrecta. No se puede ejecutar el notebook.")
    raise SystemExit
 
print("Contraseña correcta. Continuando con la ejecución del notebook para el calculo de la Reserva")

# %% Celda 1
#### MOTOR MATRICIAL ####

# librerias
import pandas  as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from joblib import Parallel, delayed, cpu_count
import numpy as np
import warnings
import os
warnings.filterwarnings("ignore")

nombre_reserva = 'RM'

fecha_ejecucion = datetime.now().strftime('%Y/%m/%d %H:%m')

start = datetime.now()

params = pd.read_table('config_cierre.txt', delimiter = ';').set_index('Parametro')

bd_t_1 = eval(params.loc['bd_t_1'].Valor)
informe = eval(params.loc['Informe'].Valor)
proyecciones = False

correr_nuevas = eval(params.loc['Correr Nuevas'].Valor)

#pd.set_option('display.float_format', lambda x: '%.9f' % x)
#pd.set_option('future.no_silent_downcasting', True)

porcentaje_trabajadores = 0.8

# Permanence en None si se va a utilizar Columna POTASA_CRECIMIENTO de las BD como Inflacion
pi_ultima_conocida = float(params.loc['Inflacion'].Valor) / 100
# Permanence en None si no se va a actualizar la mesada que hay en la columna PT_MESADA1 de las BD como mesada
pi_actualizacion_mesada = None
# Inpunt Salario Mínimo Vigente
salario_minimo_vigente = eval(params.loc['SMMLV'].Valor)
# True si solo se va a calcular los riesgos de lo nuevo False para calcular impacto IFRS17 cartera Completa
riesgos_solo_nuevo = True

impacto_mortalidad = eval(params.loc['Mortalidad'].Valor)
conservar_mesada = eval(params.loc['Conservar Mesada'].Valor)

gasto_choque_solvencia = 0

ramo = 94
fecha_cierre_str = params.loc['Fecha Cierre'].Valor
fecha_cierre_string = fecha_cierre_str
indicador_fecha = fecha_cierre_str.split('/')[0] + fecha_cierre_str.split('/')[1]

fecha_mes_ant = params.loc['Fecha valoración t-1'].Valor
fecha_mes_ant_ruta = ''.join(fecha_mes_ant.split('/')[:2])

fecha_mes_act = params.loc['Fecha valoración t'].Valor
fecha_mes_act_ruta = ''.join(fecha_mes_ant.split('/')[:2])

fecha_ruta = indicador_fecha if not informe else fecha_mes_ant_ruta

ruta_mes_parametros = f'inputs/{fecha_ruta}/parametros'

ruta_nuevo = None
ruta_stock = None
ruta_nuevo_tasa_sura = None

if bd_t_1 is True:
    bd_nuevas_tasa_sura = f'{fecha_mes_act_ruta}_t_consolidada_Sura_{nombre_reserva}.csv' if ruta_nuevo is None else ruta_stock
    bd_nuevas = f'{fecha_mes_act_ruta}_t_consolidada_Nuevo_{nombre_reserva}.csv' if ruta_nuevo is None else ruta_nuevo
    bd_stock = f'{fecha_mes_act_ruta}_t_consolidada_Stock_{nombre_reserva}.csv' if ruta_nuevo is None else ruta_stock    
else:
    bd_nuevas_tasa_sura = f'{fecha_ruta}_t_consolidada_Sura_{nombre_reserva}.csv' if ruta_nuevo is None else ruta_stock
    bd_nuevas = f'{fecha_ruta}_t_consolidada_Nuevo_{nombre_reserva}.csv' if ruta_nuevo is None else ruta_nuevo
    bd_stock = f'{fecha_ruta}_t_consolidada_Stock_{nombre_reserva}.csv' if ruta_nuevo is None else ruta_stock

if correr_nuevas and informe:
    bd_nuevas = f'{fecha_mes_act_ruta}_nuevas_nuevas_{nombre_reserva}.csv'
    bd_stock = f'{fecha_ruta}_t_consolidada_Stock_{nombre_reserva}_Dummy.csv'
nombre_salida = params.loc['Salida'].Valor

numero_nucleos = int(round(cpu_count() * porcentaje_trabajadores, 0))

# %% Celda 2

if bd_t_1 is True:
    ruta_final_nuevas = f'inputs/{fecha_mes_act_ruta}/t_consolidada/{bd_nuevas}'
    ruta_final_stock = f'inputs/{fecha_mes_act_ruta}/t_consolidada/{bd_stock}'
    ruta_final_nuevas_sura = f'inputs/{fecha_mes_act_ruta}/t_consolidada/{bd_nuevas_tasa_sura}'
else:    
    ruta_final_nuevas = f'inputs/{fecha_ruta}/t_consolidada/{bd_nuevas}'
    ruta_final_stock = f'inputs/{fecha_ruta}/t_consolidada/{bd_stock}'
    ruta_final_nuevas_sura = f'inputs/{fecha_ruta}/t_consolidada/{bd_nuevas_tasa_sura}'

df_nuevas = pd.read_csv(ruta_final_nuevas, delimiter = ';', engine = 'pyarrow', encoding = 'latin-1')
df_stock  = pd.read_csv(ruta_final_stock, delimiter = ';', engine = 'pyarrow', encoding = 'latin-1')

col_pol_nuevo = df_nuevas.filter(regex = '(?=Estado P)', axis = 1).columns[0]
col_pol_stock = df_stock.filter(regex = '(?=Estado P)', axis = 1).columns[0]

df_nuevas = df_nuevas.rename(columns = {col_pol_nuevo: 'Estado Póliza'})
df_stock = df_stock.rename(columns = {col_pol_stock: 'Estado Póliza'})

# %% Celda 3
data = pd.concat([df_stock, df_nuevas], ignore_index = True)

if not os.path.exists(f'inputs/{fecha_ruta}/salida/{nombre_reserva}'):
    os.makedirs(f'inputs/{fecha_ruta}/salida/{nombre_reserva}')

if not os.path.exists(f'inputs/{fecha_ruta}/salida/{nombre_reserva}/informe'):
    os.makedirs(f'inputs/{fecha_ruta}/salida/{nombre_reserva}/informe')

if not os.path.exists(f'inputs/{fecha_ruta}/t_consolidada/{fecha_ruta}_t_consolidada_Stock_{nombre_reserva}_Dummy.csv'):
    t_stock_dummy = pd.DataFrame(columns = data.columns)
    t_stock_dummy.to_csv(f'inputs/{fecha_ruta}/t_consolidada/{fecha_ruta}_t_consolidada_Stock_{nombre_reserva}_Dummy.csv')

# %% Celda 4
data.PT_Mesada_1 = data.PT_Mesada_1 if pi_actualizacion_mesada is None else data.PT_Mesada_1 * (1 + pi_actualizacion_mesada)

data.loc[(data.NMPOLIZA == 94220005703), ['POINTERES_TECNICO', 'TASA p1']] = 3.6359

data[~data['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])].NMPOLIZA.to_csv(f'inputs/{fecha_ruta}/salida/pol_canceladas_y_finalizados_{nombre_reserva}.csv')

data = data[data['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])]

pat = r'(FENACIMIENTO_(?:A|B|C)$)|(CDPARENTESCO_(?:A|B|C)$)|(CDSEXO_(?:A|B|C)$)|(NMPOLIZA)|(Estado_(?:A|B|C)$)|(Estado_Civil_(?:A|B|C)$)|(CDPARENTESCO_(?:A|B|C)$)|(Temporalidad_(?:A|B|C))|(FE_FINVIGENCIA_1)|(Valor Asegurado_S_1)|(CRE_SLMN)|(CRE_SLMN_ACT)'

pat_edad_sexo = r'(FENACIMIENTO_(?:A|B|C)$)|(CDSEXO_(?:A|B|C)$)'

pat_edad_sexo_estado = r'(FENACIMIENTO_(?:A|B|C)$)|(CDSEXO_(?:A|B|C)$)|(Estado_(?:A|B|C)$)|(NMPOLIZA)'

pat_edad = r'(FENACIMIENTO_(?:A|B|C)$)'

pat_sexo = r'CDSEXO_(?:A|B|C)$'

pat_estado = r'(Estado_(?:A|B|C)$)'

pat_estado_civil = r'(Estado_Civil_(?:A|B|C)$)'

pat_cdparentesco = r'(CDPARENTESCO_(?:A|B|C)$)'

pat_temporalidad = r'Temporalidad_(?:A|B|C)'

pat_temporalidad_edad = r'(Temporalidad_(?:A|B|C))|(FENACIMIENTO_(?:A|B|C)$)'

pat_vigencia = 'FE_FINVIGENCIA_1'

pat_aux = r'Valor Asegurado_S_1'

fecha_cierre_str = fecha_cierre_str.split('/')
fecha_cierre     = datetime(year  = int(fecha_cierre_str[0]),
                            month = int(fecha_cierre_str[1]),
                            day   = int(fecha_cierre_str[2])
                            )

def diff_mes(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month

def edad_actuarial(fecha_nacimiento):
    if (fecha_nacimiento is None) or (type(fecha_nacimiento) == float): return

    fecha_nacimiento = fecha_nacimiento.split('/')
    fecha_nacimiento = datetime(year  = int(fecha_nacimiento[0]),
                                month = int(fecha_nacimiento[1]),
                                day   = int(fecha_nacimiento[2]))

    factor_year       = fecha_cierre.year - fecha_nacimiento.year
    factor_mes_exacta = -1 if fecha_nacimiento.month > 6 else 0

    edad_actuarial_exacta = factor_year * 12 + factor_mes_exacta * 12

    return edad_actuarial_exacta + fecha_cierre.month

def encontrar_sexo(cod_sexo: int):
    try:
        cod_sexo = int(cod_sexo)
        return 'M' if cod_sexo == 1 else 'F'
    except ValueError:
        return
    
def encontrar_estado(cod_estado: int):
    try:
        cod_estado = int(cod_estado)
        return 'Invalido' if cod_estado == 2 else 'Valido'
    except ValueError:
        return
    
def encontrar_estado_civil(cod_estado_civil: int):
    try:
        dict_codigos = {1: 'Casado',
                        2: 'Soltero',
                        3: 'Divorciado',
                        4: 'Viudo',
                        5: 'Union Libre'}

        cod_estado_civil = int(cod_estado_civil)
        return dict_codigos[cod_estado_civil]
    except ValueError:
        return

def encontrar_parentesco(cod_parentesco: int):
    try:
        dict_parentesco = {1: 'Afiliado',
                           2: 'Hijo',
                           3: 'Conyuge',
                           4: 'Companero',
                           5: 'Padre',
                           6: 'Hermano Invalido'}

        cod_parentesco = int(cod_parentesco)
        return dict_parentesco[cod_parentesco]
    except ValueError:
        return
    
def obtener_fin_vigencia(x, omega: int = 1332):
    if x == 'V':
        return omega
    elif x is None:
        return
   
    start_date = fecha_cierre
    end_date   = pd.to_datetime(x, format = '%Y/%m/%d')
    meses_rest = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    return meses_rest if meses_rest > 0 else 0
    
def obtener_fin_pago(x, omega: int = 1332):
    obtener_meses = lambda x: (x.year - fecha_cierre.year) * 12 + (x.month - fecha_cierre.month)

    for afi in ['A','B','C']:
        if x[f'Temporalidad_{afi}'] == 'V':
            fecha_nacimiento = pd.to_datetime(x[f'FENACIMIENTO_{afi}'], format = '%Y/%m/%d') + pd.offsets.MonthEnd(0)
            x[f'Temporalidad_{afi}'] = obtener_meses(fecha_nacimiento + pd.DateOffset(months = omega))
        elif x[f'Temporalidad_{afi}'] is not None:
            fin_pago = pd.to_datetime(x[f'Temporalidad_{afi}'], format = '%Y/%m/%d')
            x[f'Temporalidad_{afi}'] = obtener_meses(fin_pago)
    return x[['Temporalidad_A', 'Temporalidad_B', 'Temporalidad_C']]

def tiene_auxilio(x):
    x = x.filter(regex = pat_aux)
    return 1 if (x != 0).all() else 0

def crece_smmlv(x):
    cre_sml = x['CRE_SLMN']
    cre_sml_act = x['CRE_SLMN_ACT']
    return int(cre_sml == 'NO' and cre_sml_act == 'SI')

edades_cony = data.filter(regex = pat, axis = 1)

edades_cony.loc[:, edades_cony.filter(regex = pat_temporalidad,
                                      axis = 1).columns] = edades_cony.loc[:, edades_cony.filter(
                                                                                                  regex = pat_temporalidad_edad,
                                                                                                  axis = 1
                                                                                                ).columns].apply(obtener_fin_pago, axis = 1)

edades_cony.loc[:, edades_cony.filter(regex = pat_edad, 
                                      axis = 1).columns] = edades_cony.loc[:, edades_cony.filter(
                                                                                                  regex = pat_edad, 
                                                                                                  axis = 1
                                                                                                ).columns].map(edad_actuarial)

edades_cony.loc[:, edades_cony.filter(regex = pat_sexo,
                                      axis = 1).columns] = edades_cony.loc[:, edades_cony.filter(
                                                                                                  regex = pat_sexo,
                                                                                                  axis = 1
                                                                                                ).columns].map(encontrar_sexo)

edades_cony.loc[:, edades_cony.filter(regex = pat_estado,
                                      axis = 1).columns] = edades_cony.loc[:, edades_cony.filter(
                                                                                                  regex = pat_estado,
                                                                                                  axis = 1
                                                                                                ).columns].map(encontrar_estado)

edades_cony.loc[:, edades_cony.filter(regex = pat_estado_civil,
                                      axis = 1).columns] = edades_cony.loc[:, edades_cony.filter(
                                                                                                  regex = pat_estado_civil,
                                                                                                  axis = 1
                                                                                                ).columns].map(encontrar_estado_civil)

edades_cony.loc[:, edades_cony.filter(regex = pat_cdparentesco,
                                      axis = 1).columns] = edades_cony.loc[:, edades_cony.filter(
                                                                                                  regex = pat_cdparentesco,
                                                                                                  axis = 1
                                                                                                ).columns].map(encontrar_parentesco)

edades_cony.loc[:, edades_cony.filter(regex = pat_vigencia,
                                      axis = 1).columns] = edades_cony.loc[:, edades_cony.filter(
                                                                                                  regex = pat_vigencia,
                                                                                                  axis = 1
                                                                                                ).columns].map(obtener_fin_vigencia)

edades_cony['Tiene_Aux'] = edades_cony.apply(tiene_auxilio, axis = 1)

edades_cony['Gran_Invalido'] = edades_cony.apply(crece_smmlv, axis = 1)

edades_cony = edades_cony.drop(columns = ['Valor Asegurado_S_1'])

# %% Celda 6
#factores_mejora = pd.read_excel(f'{ruta_mes_parametros}/factores_mejora.xlsx')
# factores_mejora = factores_mejora.reset_index(names = 'Edad')
# print(factores_mejora)

# %% Celda 8
nombre_reserva_ = nombre_reserva if nombre_reserva in ['RM', 'Ley100'] else 'RM'

año_val = (fecha_cierre + timedelta(days = 1)).year

def generar_tabla_mort_edad(tabla_mort_base: pd.DataFrame, edad_afi: int) -> None:
    edad_meses  = 4 * list(range(1332))
    lista_femn  = 2 * 1332 * ['F'] 
    lista_masc  = 2 * 1332 * ['M']
    lista_val_  = 1332 * ['Valido'] + 1332 * ['Invalido']

    mtx_probs = pd.DataFrame({'Edad_Meses': edad_meses, 'Sexo': lista_femn + lista_masc, 'Estado': 2 * lista_val_})

    mtx_probs['Edad']        = mtx_probs.Edad_Meses // 12
    mtx_probs['Edad_Exacta'] = mtx_probs.Edad_Meses / 12
    mtx_probs['Frac_Edad']   = mtx_probs.Edad_Exacta - mtx_probs.Edad

    mtx_probs = mtx_probs[['Edad', 'Edad_Meses', 'Edad_Exacta', 'Frac_Edad', 'Sexo', 'Estado']]
    mtx_probs = mtx_probs.merge(tabla_mort_base, how = 'left', on = ['Edad', 'Sexo', 'Estado'])

    mtx_probs['Qx_Mensualizada_Base'] = mtx_probs[['Frac_Edad', 'Qx']].apply(lambda x: (x['Qx'] / 12) / (1 - x['Qx'] * x['Frac_Edad']), axis = 1)

    mtx_probs['Qx_Mejorada'] = (mtx_probs.Qx) * (1 - mtx_probs.rx) ** ((mtx_probs.Año_Valoracion - mtx_probs.Año) + (mtx_probs.Edad - edad_afi))

    mtx_probs['Qx_Mensualizada_Mejorada'] = mtx_probs[['Frac_Edad', 'Qx_Mejorada']].apply(lambda x: (x['Qx_Mejorada'] / 12) / (1 - x['Qx_Mejorada'] * x['Frac_Edad']), axis = 1)

    mtx_probs.to_csv(f'tablas_mort_edad/{nombre_reserva_}/{mtx_probs.Año_Valoracion[0]}/tabla_mort_{edad_afi}.csv', index = False)

if os.path.exists(f'tablas_mort_edad/{nombre_reserva_}/{año_val}/tabla_mort_0.csv'):
    pass
else:
    if not os.path.exists(f'tablas_mort_edad/{nombre_reserva_}/{año_val}'):
        if not os.path.exists(f'tablas_mort_edad/{nombre_reserva_}'):
            os.mkdir(f'tablas_mort_edad/{nombre_reserva_}')
        os.mkdir(f'tablas_mort_edad/{nombre_reserva_}/{año_val}')
    for edad in range(112):
        # Factores mejora
        factores_mejora = pd.read_excel(f'{ruta_mes_parametros}/factores_mejora.xlsx')
        factores_mejora = factores_mejora.reset_index(names = 'Edad')

        if nombre_reserva == 'Ley100':
            factores_mejora['Rx-M-ARL_Inv'] = factores_mejora['Rx-M-Válido']
            factores_mejora['Rx-F-ARL_Inv'] = factores_mejora['Rx-F-Válido']

        factores_mejora = factores_mejora.melt(value_vars = ['Rx-M-Válido', 'Rx-F-Válido', 'Rx-M-ARL_Inv', 'Rx-F-ARL_Inv'], 
                                            var_name = 'Sexo', value_name = 'rx', id_vars = 'Edad')

        factores_mejora[['N', 'Sexo', 'Estado']] = factores_mejora.Sexo.str.split('-', expand = True)
        factores_mejora['Estado'] = factores_mejora['Estado'].replace('ARL_Inv', 'Invalido').replace('Válido', 
                                                                                                     'Valido').replace('Inválido','Invalido')

        factores_mejora = factores_mejora[['Edad', 'Sexo', 'Estado', 'rx']]

        factores_mejora['rx'] = factores_mejora['rx'].round(9)

        # Tabla RV08 
        tabla_rv08 = pd.read_csv(f'{ruta_mes_parametros}/tablas_mortalidad.csv', engine = 'pyarrow', delimiter = ';')

        tabla_rv08['Qx'] = tabla_rv08['Qx'].round(9)

        tabla_rv08_val = tabla_rv08[tabla_rv08.Tabla == 'RV08']

        tabla_rv08_val = tabla_rv08_val.rename(columns = {'Periodo': 'Edad'})

        tabla_rv08_val['Estado'] = 'Valido'

        qxs_val = tabla_rv08_val[['Edad', 'Sexo', 'Estado', 'Qx']]

        qxs_val = qxs_val.merge(factores_mejora, how = 'left', on = ['Edad', 'Sexo', 'Estado'])

        # Tabla RI89 sin mejorar
        tabla_rv08_inv = tabla_rv08[tabla_rv08.Tabla == 'RI89']

        tabla_rv08_inv = tabla_rv08_inv.rename(columns = {'Periodo': 'Edad'})

        tabla_rv08_inv['Estado'] = 'Invalido'

        qxs_inv = tabla_rv08_inv[['Edad', 'Sexo', 'Estado', 'Qx']]

        qxs_inv = qxs_inv.merge(factores_mejora, how = 'left', on = ['Edad', 'Sexo', 'Estado'])

        qxs = pd.concat([qxs_inv, qxs_val], axis = 0)

        qxs['Año'] = 2008

        qxs['Año'] = qxs['Año'].where(qxs['Estado'] == 'Valido', 1990)

        qxs['Año_Valoracion'] = (fecha_cierre + timedelta(days = 1)).year

        generar_tabla_mort_edad(qxs, edad)

tablas_mort_dict = {i:pd.read_csv(f'tablas_mort_edad/{nombre_reserva_}/{año_val}/tabla_mort_{i}.csv') for i in range(112)}

# %% Celda 9
def generar_meses(row: pd.Series, min_edad: int) -> pd.DataFrame:
    min_edad_long = len(list(range(min_edad, 1333)))

    row = row.filter(regex = pat_temporalidad_edad).fillna(0)

    num_bef = 3

    afis = [list(range(int(row.iloc[2 * i]), min(1333, int(row.iloc[2 * i]) + int(row.iloc[2 * i + 1])))) if int(row.iloc[2 * i + 1]) != 0 else [] for i in range(num_bef)]
    
    return pd.DataFrame({f'FENACIMIENTO_{afi}': long_afi + (min_edad_long - len(long_afi)) * [1333] if len(long_afi) >= 1 else [1333] * min_edad_long for afi, long_afi in zip(['A','B','C'][:len(row)], afis)})

def poner_genero_y_estado(row: pd.Series, min_edad: int) -> pd.DataFrame:
    df_meses = generar_meses(row, min_edad)

    mes_pasado = df_meses.iloc[0,:] - 1
    mes_pasado = mes_pasado.to_frame().T

    df_meses = pd.concat([mes_pasado, df_meses], axis = 0).reset_index(drop = True)

    num_bef = len(df_meses.columns)

    afis = ['A','B','C'][:num_bef]

    for afi in afis:
        df_meses[f'CDSEXO_{afi}'] = row[f'CDSEXO_{afi}']
        df_meses[f'Estado_{afi}'] = row[f'Estado_{afi}']

    df_meses[[f'FENACIMIENTO_{afi}_ACTUARIAL' for afi in afis]] = df_meses.iloc[:,0:3].floordiv(12)

    df_meses[[f'FENACIMIENTO_{afi}_EXACTA' for afi in afis]] = df_meses.iloc[:,0:3]/12

    for idx, afi in zip(range(12, 12 + num_bef), ['A', 'B', 'C']):
        df_meses[f'FENACIMIENTO_{afi}_FRAC'] = df_meses.iloc[:, idx] - df_meses.iloc[:, idx - 3]
    return df_meses, num_bef

def encontrar_npx_lineal(x: pd.Series, mejorar: bool = False, auxilio_funerario: bool = False, 
                         cg: bool = False, impacto_mortalidad: bool = False) -> pd.Series:
    min_edad = 0
    qx = 'Mejorada' if mejorar else 'Base'
    df_edades_mes, num_bef = poner_genero_y_estado(x, min_edad)

    for afi in ['A','B','C'][:num_bef]:
        df_edades_mes = df_edades_mes.rename(columns = {f'CDSEXO_{afi}': 'Sexo', f'FENACIMIENTO_{afi}': 'Edad_Meses', f'Estado_{afi}': 'Estado'})
        
        tabla_mort = tablas_mort_dict[df_edades_mes[f'FENACIMIENTO_{afi}_ACTUARIAL'][1]]
        df_edades_mes = df_edades_mes.merge(tabla_mort[['Sexo', 'Edad_Meses', 'Estado', f'Qx_Mensualizada_{qx}']], how = 'left', on = ['Sexo', 'Edad_Meses', 'Estado'])
        df_edades_mes = df_edades_mes.rename(columns = {'Sexo': f'CDSEXO_{afi}', 'Edad_Meses': f'FENACIMIENTO_{afi}', 
                                                        'Estado': f'Estado_{afi}', f'Qx_Mensualizada_{qx}': f'Qx_Mensualizada_{qx}_{afi}'})

    df_edades_mes = df_edades_mes.fillna(1)

    if not impacto_mortalidad:
        df_edades_mes.iloc[0,-3:] = 0

    df_edades_mes[['npx_A', 'npx_B', 'npx_C']] = (1 - df_edades_mes.iloc[:,-num_bef:]).cumprod()

    if cg:
        return df_edades_mes[['npx_A', 'npx_B']]

    res_sum  = df_edades_mes.iloc[:,-num_bef:].sum(axis = 1)
    res_prod = df_edades_mes.iloc[:,-num_bef:].prod(axis = 1)
    
    num_cols = len(df_edades_mes.columns)
    res_ab = df_edades_mes.iloc[:, [num_cols - num_bef, num_cols - num_bef + 1]].prod(axis = 1)
    res_ac = df_edades_mes.iloc[:, [num_cols - num_bef, num_cols - num_bef + 2]].prod(axis = 1)
    res_bc = df_edades_mes.iloc[:, [num_cols - num_bef + 1, num_cols - num_bef + 2]].prod(axis = 1)
    res_prod_t = res_ab + res_ac + res_bc
    npx_conjta = res_sum + res_prod - res_prod_t

    if auxilio_funerario:
        return df_edades_mes[f'Qx_Mensualizada_{qx}_A'] * df_edades_mes['npx_A'].shift(1).fillna(1)

    return npx_conjta

def aplicar_calculo_npx_lineal(df: pd.DataFrame, mejorar: bool = False, impacto_mortalidad: bool = impacto_mortalidad) -> pd.DataFrame:
    df = df.apply(lambda x: encontrar_npx_lineal(x, mejorar = mejorar, impacto_mortalidad = impacto_mortalidad), axis = 1, result_type = 'expand')
    return df

# %% Celda 10
# Function to get the last day of the month
def get_last_day_of_month(date):
    next_month = date.replace(day=28) + relativedelta(days=4)
    return next_month - relativedelta(days=next_month.day)

# Function to generate range of last days of the month
def generate_last_days(start_date, num_years):
    start_date = datetime.strptime(start_date, "%Y/%m/%d")
    
    # Calculate the end date by adding the number of years to the start date
    end_date = start_date + relativedelta(years=num_years)
    
    # Adjust start_date to the last day of the start month if it's not already the last day
    start_date = get_last_day_of_month(start_date)
    
    dates = []
    while start_date <= end_date:
        dates.append(start_date)
        start_date += relativedelta(months=1)
        start_date = get_last_day_of_month(start_date)
        
    return dates

# Example usage
start_date = fecha_cierre_string
num_years = 2
last_days = generate_last_days(start_date, 111)[:1335]
last_days = pd.DatetimeIndex(last_days)

# %% Celda 11
chunks = np.array_split(edades_cony, numero_nucleos)

processed_chunks = Parallel(n_jobs = numero_nucleos)(delayed(aplicar_calculo_npx_lineal)(chunk,
                                                                                         mejorar = False,
                                                                                         impacto_mortalidad = impacto_mortalidad) for chunk in chunks)

mtx_npxs = pd.concat(processed_chunks).T

mtx_npxs_contable = mtx_npxs.copy()
mtx_npxs_contable.columns = edades_cony.NMPOLIZA.to_list()

# %% Celda 12
chunks = np.array_split(edades_cony, numero_nucleos)

processed_chunks = Parallel(n_jobs = numero_nucleos)(delayed(aplicar_calculo_npx_lineal)(chunk, 
                                                                                         mejorar = True, 
                                                                                         impacto_mortalidad = impacto_mortalidad) for chunk in chunks)

mtx_npxs = pd.concat(processed_chunks).T

mtx_npxs_mejorada = mtx_npxs.copy()
mtx_npxs_mejorada.columns = edades_cony.NMPOLIZA.to_list()

# %% Celda 13
def encontrar_max_vigencia(x: pd.Series, omega: int = 1333, conservar_mesada: bool = False) -> pd.DataFrame:
    incluir_flujo = 1 if conservar_mesada else 0
    return pd.Series([incluir_flujo] + min(x['FE_FINVIGENCIA_1'], omega) * [1] + (omega - x['FE_FINVIGENCIA_1']) * [0])

def aplicar_max_vigencia(df: pd.DataFrame, omega: int = 1333, conservar_mesada: bool = False) -> pd.DataFrame:
    df = df.apply(lambda x: encontrar_max_vigencia(x, omega, conservar_mesada), axis = 1, result_type = 'expand')
    return df

mtx_vigencia = aplicar_max_vigencia(edades_cony, conservar_mesada = conservar_mesada).T
mtx_vigencia.columns = edades_cony.NMPOLIZA

# %% Celda 15
mesadas     = data.PT_Mesada_1.to_numpy()
mtx_mesadas = pd.DataFrame(np.tile(mesadas, (len(mtx_npxs_mejorada), 1)))
mtx_mesadas.columns = edades_cony.NMPOLIZA

# %% Celda 16
mes = fecha_cierre.month - 2 # Número del mes menos dos.

num_pagos = data[['NMPOLIZA', 'ENERO_1', 'FEBRERO_1', 'MARZO_1', 'ABRIL_1', 'MAYO_1', 
                  'JUNIO_1', 'JULIO_1', 'AGOSTO_1', 'SEPTIEMBRE_1', 'OCTUBRE_1', 'NOVIEMBRE_1', 'DICIEMBRE_1']]

num_pagos = num_pagos.T
num_pagos.columns = num_pagos.iloc[0]

num_pagos = num_pagos.reset_index(drop = True).iloc[1:].reset_index(drop = True)
num_pagos = num_pagos.to_numpy()
num_pagos = np.tile(num_pagos, (112, 1))
num_pagos = num_pagos[mes + 1: len(mtx_npxs_mejorada) + mes + 1, :]
num_pagos = pd.DataFrame(num_pagos, columns = edades_cony.NMPOLIZA)

num_pagos

# %% Celda 17
# Vector de Inflacion

proyecciones = False

vector_inflacion = data.POTASA_CRECIMIENTO.to_numpy()[0] / 100 if pi_ultima_conocida is None else pi_ultima_conocida

if proyecciones:
    vector_inflacion = pd.read_csv(f'{ruta_mes_parametros}/vector_inflacion.csv', 
                                   delimiter=';', 
                                   engine='pyarrow')['inflacion'].to_numpy()

    tasa_inflacion_ = vector_inflacion.repeat(12)
    tasa_inflacion_ = np.tile(tasa_inflacion_, (len(edades_cony), 1))
    tasa_inflacion_ = tasa_inflacion_[:,mes + 1:] if fecha_cierre.month != 12 else tasa_inflacion_ 
    tasa_inflacion_ = 1 + pd.DataFrame(tasa_inflacion_.T).iloc[:len(mtx_npxs_mejorada),:]

    tasa_inflacion_.columns = edades_cony.NMPOLIZA

    vector_inflacion_arr = vector_inflacion

if type(vector_inflacion) == float:
    tasa_inflacion_ = vector_inflacion * np.ones((len(mtx_npxs_mejorada), len(edades_cony)))
    tasa_inflacion_ = 1 + pd.DataFrame(tasa_inflacion_)

    tasa_inflacion_.columns = edades_cony.NMPOLIZA

    vector_inflacion_arr = np.array([0] + [vector_inflacion] * 111)

inflacion_ = (1 + vector_inflacion_arr).cumprod()
inflacion_ = inflacion_.repeat(12)
inflacion_ = np.tile(inflacion_, (len(edades_cony), 1))
inflacion_ = inflacion_[:,mes + 1:] if fecha_cierre.month != 12 else inflacion_ 
inflacion_ = pd.DataFrame(inflacion_.T).iloc[:len(mtx_npxs_mejorada),:]

inflacion_.columns = edades_cony.NMPOLIZA

if fecha_cierre.month == 12:
    inflacion_ = pd.concat([pd.Series([1] * len(inflacion_.columns), index = inflacion_.columns).to_frame().T, inflacion_], axis = 0)
    inflacion_ = inflacion_.reset_index(drop = True)

mtx_incremento_mesada_inf = inflacion_
mtx_incremento_mesada_inf.head(24)

# %% Celda 18
# Vector de Tasa
data['POINTERES_TECNICO'] = pd.to_numeric(data['POINTERES_TECNICO'], errors='coerce')

vector_tasa = data.POINTERES_TECNICO.to_numpy() / 100

if proyecciones:
    vector_tasa = pd.read_csv(f'{ruta_mes_parametros}/vector_tasa.csv', 
                                   delimiter=';', 
                                   engine='pyarrow')['tasa'].to_numpy()
    
    if len(vector_tasa) < 113:
        deslizamiento_ = vector_tasa.tolist()
        deslizamiento_ = deslizamiento_ + [deslizamiento_[-1]] * (113 - len(deslizamiento_))
        deslizamiento_ = np.array(deslizamiento_)
    
    tasa_interes = vector_tasa.repeat(12)
    tasa_interes = np.tile(tasa_interes, (len(edades_cony), 1))
    tasa_interes = tasa_interes[:,mes + 1:] if fecha_cierre.month != 12 else tasa_interes
    tasa_interes = 1 + pd.DataFrame(tasa_interes.T).iloc[:len(mtx_npxs_mejorada),:]

    tasa_interes.columns = edades_cony.NMPOLIZA
    
    if fecha_cierre.month == 12:
        tasa_interes  = pd.concat([pd.series([0] * len(tasa_interes.columns), index = tasa_interes.columns).to_frame().T, tasa_interes], axis = 0)
        tasa_interes = tasa_interes.reset_index(drop = True)
    
else:
    tasa_interes = vector_tasa * np.ones((len(mtx_npxs_mejorada), 1))
    tasa_interes = 1 + pd.DataFrame(tasa_interes)

    tasa_interes.columns = edades_cony.NMPOLIZA

tasa_interes

# %% Celda 20
# deslizamiento = pd.read_csv(f'{ruta_mes_parametros}/hip_deslizamiento.csv', delimiter = ';', engine = 'pyarrow')
# deslizamiento

# %% Celda 21
# Vector de Deslizamiento

nueva_filtro = df_nuevas[df_nuevas['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])]


deslizamiento = pd.read_csv(f'{ruta_mes_parametros}/hip_deslizamiento.csv', delimiter = ';', engine = 'pyarrow')
deslizamiento_ = deslizamiento[deslizamiento.ID == 0]['Deslizamiento'].to_numpy()

if len(deslizamiento_) < 113:
    deslizamiento_ = deslizamiento_.tolist()
    deslizamiento_ = deslizamiento_ + [deslizamiento_[-1]] * (113 - len(deslizamiento_))
    deslizamiento_ = np.array(deslizamiento_)

deslizamiento = (1 + deslizamiento_).cumprod()
deslizamiento = deslizamiento.repeat(12)
deslizamiento = np.tile(deslizamiento, (len(edades_cony), 1))
deslizamiento = deslizamiento[:,mes + 1:] if fecha_cierre.month != 12 else deslizamiento
deslizamiento = pd.DataFrame(deslizamiento.T).iloc[:len(mtx_npxs_mejorada),:len(df_nuevas)]
#deslizamiento = pd.DataFrame(deslizamiento.T).iloc[:len(mtx_npxs_mejorada),:len(edades_cony)] Código para prender deslizamiento al stock


#deslizamiento.columns = edades_cony.NMPOLIZA Para aplicar deslizamiento al stock
deslizamiento.columns = df_nuevas.NMPOLIZA 

if fecha_cierre.month == 12:
    deslizamiento = pd.concat([pd.Series([1] * len(deslizamiento.columns), index= deslizamiento.columns ).to_frame().T, deslizamiento], axis = 0)
    deslizamiento = deslizamiento.reset_index(drop = True)

deslizamiento = pd.concat([pd.DataFrame(np.ones((len(mtx_npxs_mejorada), 
                                                 len(df_stock[df_stock['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])]))), 
                                                 columns = df_stock[df_stock['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])].NMPOLIZA), 
                                                 deslizamiento], axis = 1)

crec_smmlv = deslizamiento * inflacion_

crec_smmlv = pd.concat([pd.DataFrame(np.ones((len(mtx_npxs_mejorada), 
                                              len(df_stock[df_stock['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])]))), 
                                              columns = df_stock[df_stock['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])].NMPOLIZA), 
                                              crec_smmlv[nueva_filtro.NMPOLIZA]], axis = 1)


crec_smmlv

# %% Celda 22
mtx_mesadas_inf = mtx_mesadas * mtx_incremento_mesada_inf

# %% Celda 23
mtx_vp = 1 / (tasa_inflacion_ * tasa_interes) ** (1/12)
mtx_vp = mtx_vp.pow(range(len(mtx_vp)), axis = 0)

mtx_vp

# %% Celda 24
smmlv = len(mtx_npxs_mejorada) * [salario_minimo_vigente]

smmlv = pd.DataFrame(smmlv)
smmlv = pd.concat([smmlv] * len(tasa_inflacion_.columns), axis = 1)

smmlv.columns = tasa_inflacion_.columns

# %% Celda 25
mtx_smmlv_des = smmlv * crec_smmlv
mtx_smmlv_inf = smmlv * mtx_incremento_mesada_inf
mtx_mesadas_des_ = mtx_mesadas * crec_smmlv

# %% Celda 26
mtx_mesadas_des = mtx_mesadas_inf.where(mtx_smmlv_des < mtx_mesadas_inf, mtx_smmlv_des, axis = 1)
mtx_mesadas_inf = mtx_mesadas_inf

pols_gran_invalido = edades_cony[edades_cony.Gran_Invalido == 1].NMPOLIZA.to_list()
pols_gran_invalido = [pol for pol in pols_gran_invalido if pol in df_nuevas.NMPOLIZA.to_list()]

mtx_mesadas_des.loc[:, pols_gran_invalido] = mtx_mesadas_des_[pols_gran_invalido]
mtx_mesadas_des

# %% Celda 27
rva_ifrs4_contable = mtx_mesadas_inf * mtx_npxs_contable * mtx_vp * num_pagos * mtx_vigencia

rva_ifrs4_deslizamiento = mtx_mesadas_des * mtx_npxs_contable * mtx_vp * num_pagos * mtx_vigencia

rva_ifrs4_extralongevidad = mtx_mesadas_des * mtx_npxs_mejorada * mtx_vp * num_pagos * mtx_vigencia

# %% Celda 29
rxs = pd.read_csv(f'{ruta_mes_parametros}/rx_cambio_grupo.csv', engine = 'pyarrow', delimiter = ';')
rxs = rxs.rename(columns = {'Year': 'Edad'})
rxs = rxs.melt(id_vars = ['Edad', 'Estado'], value_vars = ['M', 'F'], 
               value_name = 'Rx', var_name = 'Sexo')

# %% Celda 30
edad_meses = 2 * list(range(1331))
lista_femn = 1331 * ['F'] 
lista_masc = 1331 * ['M']
lista_div  = 1331 * ['Divorciarse']

mtx_probs_div = pd.DataFrame({'Edad_Meses': edad_meses, 'Sexo': lista_femn + lista_masc, 'Estado': 2 * lista_div})

mtx_probs_div['Edad']        = mtx_probs_div.Edad_Meses // 12
mtx_probs_div['Edad_Exacta'] = mtx_probs_div.Edad_Meses / 12
mtx_probs_div['Frac_Edad']   = mtx_probs_div.Edad_Exacta - mtx_probs_div.Edad

mtx_probs_div = mtx_probs_div.merge(rxs, how = 'left', on = ['Edad', 'Sexo', 'Estado'])

mtx_probs_div['Rx_Mensualizada'] = mtx_probs_div[['Frac_Edad', 'Rx']].apply(lambda x: (x['Rx'] / 12) / (1 - x['Rx'] * x['Frac_Edad']), axis = 1)

mtx_probs_div = mtx_probs_div.rename(columns = {'Rx': 'Dx', 'Rx_Mensualizada': 'Dx_Mensualizada'})

mtx_probs_div['Dx_C'] = 1 - mtx_probs_div.Dx_Mensualizada

# %% Celda 31
edad_meses  = 8 * list(range(1331))
lista_femn  = 4 * 1331 * ['F'] 
lista_masc  = 4 * 1331 * ['M']
lista_val_  = 1331 * ['Soltero'] + 1331 * ['Casado'] + 1331 * ['Viudo'] + 1331 * ['Divorciado']

mtx_probs_cg = pd.DataFrame({'Edad_Meses': edad_meses, 'Sexo': lista_femn + lista_masc, 'Estado': 2 * lista_val_})

mtx_probs_cg['Edad']        = mtx_probs_cg.Edad_Meses // 12
mtx_probs_cg['Edad_Exacta'] = mtx_probs_cg.Edad_Meses / 12
mtx_probs_cg['Frac_Edad']   = mtx_probs_cg.Edad_Exacta - mtx_probs_cg.Edad

mtx_probs_cg = mtx_probs_cg[['Edad', 'Edad_Meses', 'Edad_Exacta', 'Frac_Edad', 'Sexo', 'Estado']]
mtx_probs_cg = mtx_probs_cg.merge(rxs, how = 'left', on = ['Edad', 'Sexo', 'Estado'])

mtx_probs_cg['Rx_Mensualizada'] = mtx_probs_cg[['Frac_Edad', 'Rx']].apply(lambda x: (x['Rx'] / 12) / (1 - x['Rx'] * x['Frac_Edad']), axis = 1)
mtx_probs_cg['Sx_Mensualizada'] = 1 - mtx_probs_cg.Rx_Mensualizada

mtx_probs_cg = pd.concat([mtx_probs_cg, mtx_probs_div])

# %% Celda 32
estado_civil    = 2 * ['Casado', 'Soltero', 'Viudo', 'Divorciado']
sexo            = 4 * ['F'] + 4 * ['M']
diferencia_edad = [5, -4, 11, 4, 15, 0, 26, 14]

tabla_diff_edad_cg = pd.DataFrame({
                                    'Estado Civil': estado_civil,
                                    'Sexo': sexo,
                                    'Diff Edad Nuevo Conyuge': diferencia_edad
                                   })

# %% Celda 33
def encontrar_nueva_cony(tabla_diff_edades: pd.DataFrame, estado_afi: int, sexo_afi: str):
    return tabla_diff_edades[(tabla_diff_edades['Estado Civil'] == estado_afi) & (tabla_diff_edades.Sexo == sexo_afi)]['Diff Edad Nuevo Conyuge']

def encontrar_p_cg(x: pd.Series, mtx_flujos: pd.DataFrame, mtx_vp: pd.DataFrame, mtx_num_mesadas: pd.DataFrame,
                   tabla_cg: pd.DataFrame, tabla_diff_edades: pd.DataFrame, fecha_cierre: datetime.date,
                   mejorar: bool = False, omega: int = 1332, min_edad_extra: int = 18, impacto_mortalidad: bool = False):
    tabla = 'Mejorada' if mejorar else 'Base'
    x_flujos = mtx_flujos[x['NMPOLIZA']]
    M0 = x_flujos[0]
    x_flujos = x_flujos / M0

    x_vp      = mtx_vp[x['NMPOLIZA']]
    num_pagos = mtx_num_mesadas[x['NMPOLIZA']]
    if 'Afiliado' not in x.values: return pd.Series(np.zeros((len(x_flujos))))

    afi = x == 'Afiliado'
    afi = x[afi].index[0][-1] if x[afi] is not None != 0 else None

    info_afi = x[1:].filter(regex = f'.*{afi}$').copy()
    info_afi.index = ['CDPARENTESCO_A', 'CDSEXO_A', 'FENACIMIENTO_A', 'Estado_A', 'Temporalidad_A', 'Estado_Civil_A']

    divorciado_ind = True if ('Casado' in info_afi.values) and (('Conyuge' not in x.values) and ('Companero' not in x.values)) else False
    divorciado_ind = True if ((('Union Libre' in info_afi.values) and (('Conyuge' not in x.values) and ('Companero' not in x.values))) or divorciado_ind) else False

    cony_actual = x.isin(['Conyuge', 'Companero'])
    cony_actual = x[cony_actual].index[0][-1] if len(x[cony_actual]) != 0 else None

    info_cony = x[1:].filter(regex = f'.*{cony_actual}$').copy() if cony_actual is not None else None
    if info_cony is not None:
        info_cony.index = ['CDPARENTESCO_B', 'CDSEXO_B', 'FENACIMIENTO_B', 'Estado_B', 'Temporalidad_B', 'Estado_Civil_B'] if cony_actual is not None else None

    info_afi['Estado_Civil_A'] = 'Divorciado' if divorciado_ind else info_afi['Estado_Civil_A']
    info_afi['Estado_Civil_A'] = 'Casado' if info_afi['Estado_Civil_A'] == 'Union Libre' else info_afi['Estado_Civil_A']

    # edad_nueva_cony = max(info_afi['FENACIMIENTO_A'] // 12 - encontrar_nueva_cony(tabla_diff_edades, info_afi[f'Estado_Civil_A'], info_afi[f'CDSEXO_A']).values[0], min_edad_extra)
    # info_afi['FENACIMIENTO_B'] = edad_actuarial(f'{int(fecha_cierre.year - edad_nueva_cony)}/{fecha_cierre.month}/{fecha_cierre.day}')
    
    # Calcular diferencia de edad según tabla
    diff_edad_tabla = encontrar_nueva_cony(tabla_diff_edades, info_afi[f'Estado_Civil_A'], info_afi[f'CDSEXO_A']).values[0]

    # Calcular edad del nuevo cónyuge en años
    edad_nueva_cony_anos = info_afi['FENACIMIENTO_A'] // 12 - diff_edad_tabla

    # Si la edad es >= 18 años, usar cálculo en meses (mantiene precisión)
    if edad_nueva_cony_anos >= min_edad_extra:
        info_afi['FENACIMIENTO_B'] = info_afi['FENACIMIENTO_A'] - (diff_edad_tabla * 12)
    # Si la edad es < 18 años, usar edad_actuarial (para aplicar restricción correctamente)
    else:
        info_afi['FENACIMIENTO_B'] = edad_actuarial(f'{int(fecha_cierre.year - min_edad_extra)}/{fecha_cierre.month}/{fecha_cierre.day}')


    info_afi['Temporalidad_B'] = 1331
    info_afi['Estado_B'] = 'Valido'
    info_afi['CDSEXO_B'] = 'F' if info_afi[f'CDSEXO_A'] == 'M' else 'M'

    info_afi['FENACIMIENTO_C'] = None
    info_afi['Temporalidad_C'] = None
    info_afi['Estado_C'] = None
    info_afi['CDSEXO_C'] = None

    npx_df_cony_nueva = encontrar_npx_lineal(info_afi.copy(), cg = True, mejorar = mejorar, impacto_mortalidad = impacto_mortalidad)
    npx_cony_nueva = npx_df_cony_nueva.iloc[:,1].copy()
    npx_afiliado   = npx_df_cony_nueva.iloc[:,0].copy()

    npx_cony_actual = None

    if ('Conyuge' in x.values) or ('Companero' in x.values):
        info_afi['FENACIMIENTO_B'] = info_cony['FENACIMIENTO_B']
        info_afi['Temporalidad_B'] = info_cony['Temporalidad_B']
        info_afi['Estado_B'] = info_cony['Estado_B']
        info_afi['CDSEXO_B'] = info_cony['CDSEXO_B']

        npx_df_cony_actual = encontrar_npx_lineal(info_afi.copy(), cg = True, mejorar = mejorar, impacto_mortalidad = impacto_mortalidad)
        npx_cony_actual = npx_df_cony_actual.iloc[:,1].copy()

    if info_afi['Estado_Civil_A'] != 'Casado':
        nSx = (1 - tabla_cg[(tabla_cg.Estado == info_afi['Estado_Civil_A']) & (tabla_cg.Edad_Meses >= info_afi['FENACIMIENTO_A']) & (tabla_cg.Sexo == info_afi['CDSEXO_A'])].Rx_Mensualizada).cumprod().shift().fillna(1).copy().reset_index(drop = True)
        rx  = tabla_cg[(tabla_cg.Estado == info_afi['Estado_Civil_A']) & (tabla_cg.Edad_Meses >= info_afi['FENACIMIENTO_A']) & (tabla_cg.Sexo == info_afi['CDSEXO_A'])].Rx_Mensualizada.copy().reset_index(drop = True)

        prob_cg = rx * nSx
        prob_cg = pd.concat([prob_cg, pd.Series((omega - len(prob_cg) + 1) * [0])]).reset_index(drop = True)

        # Aqui era la version anterior que suma los flujos desde el periodo t en adelante        # beta_afiliado = ((x_flujos * npx_afiliado * num_pagos * x_vp).iloc[::-1].cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1))).fillna(0)
        # beta_cony_nueva = ((x_flujos * npx_cony_nueva * num_pagos * x_vp).iloc[::-1].cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_cony_nueva.shift().fillna(1))).fillna(0)
        # beta_cony_nueva_afiliado = ((x_flujos * npx_afiliado * npx_cony_nueva * num_pagos * x_vp).iloc[::-1].cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1) * npx_cony_nueva.shift().fillna(1))).fillna(0)
        
        ## Nueva version que suma los flujos desde el periodo t+1 en adelante
        beta_afiliado = ((x_flujos * npx_afiliado * num_pagos * x_vp).iloc[::-1].shift().fillna(0).cumsum().iloc[::-1].fillna(0) / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1))).fillna(0)
        beta_cony_nueva = ((x_flujos * npx_cony_nueva * num_pagos * x_vp).iloc[::-1].shift().fillna(0).cumsum().iloc[::-1].fillna(0) / (x_vp.shift().fillna(1) * x_flujos * npx_cony_nueva.shift().fillna(1))).fillna(0)
        beta_cony_nueva_afiliado = ((x_flujos * npx_afiliado * npx_cony_nueva * num_pagos * x_vp).iloc[::-1].shift().fillna(0).cumsum().iloc[::-1].fillna(0) / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1) * npx_cony_nueva.shift().fillna(1))).fillna(0)
        beta_conjunto_cony_nueva = beta_afiliado + beta_cony_nueva - beta_cony_nueva_afiliado 
        
        costo_cg       = beta_conjunto_cony_nueva - beta_afiliado
        costo_cg_final = (costo_cg * prob_cg.shift()).fillna(0)
        
        return costo_cg_final * npx_afiliado

    # Divorciarse y volver a casarse
    rx_div = tabla_cg[(tabla_cg.Estado == 'Divorciado') & (tabla_cg.Edad_Meses >= info_afi['FENACIMIENTO_A'])  & (tabla_cg.Sexo == info_afi['CDSEXO_A'])].Rx_Mensualizada.copy().reset_index(drop = True)
    rx_env = tabla_cg[(tabla_cg.Estado == 'Viudo') & (tabla_cg.Edad_Meses >= info_afi['FENACIMIENTO_A']) & (tabla_cg.Sexo == info_afi['CDSEXO_A'])].Rx_Mensualizada.copy().reset_index(drop = True)

    nSx_div = (1 - tabla_cg[(tabla_cg.Estado == 'Divorciado') & (tabla_cg.Edad_Meses >= info_afi['FENACIMIENTO_A'])  & (tabla_cg.Sexo == info_afi['CDSEXO_A'])].Rx_Mensualizada).cumprod().shift().fillna(1).copy().reset_index(drop = True)
    nSx_env = (1 - tabla_cg[(tabla_cg.Estado == 'Viudo') & (tabla_cg.Edad_Meses >= info_afi['FENACIMIENTO_A'])  & (tabla_cg.Sexo == info_afi['CDSEXO_A'])].Rx_Mensualizada).cumprod().shift().fillna(1).copy().reset_index(drop = True)

    p_matrimonio_div = rx_div * nSx_div
    p_matrimonio_env = rx_env * nSx_env

    nDx = tabla_cg[(tabla_cg.Estado == 'Divorciarse') & (tabla_cg.Edad_Meses >= info_afi['FENACIMIENTO_A'])  & (tabla_cg.Sexo == info_afi['CDSEXO_A'])].Dx_Mensualizada.copy().reset_index(drop = True)

    p_divorcio = nDx * (1 - nDx).cumprod().shift().fillna(1)

    nSx_div = pd.concat([pd.Series([1]), nSx_div], axis = 0)
    nSx_env = pd.concat([pd.Series([1]), nSx_env], axis = 0)

    p_divorcio = pd.concat([p_divorcio, pd.Series((omega - len(p_divorcio) + 1) * [0])]).reset_index(drop = True)
    nSx_div    = pd.concat([nSx_div, pd.Series((omega - len(nSx_div) + 1) * [nSx_div.iloc[-1]])]).reset_index(drop = True)

    factor_divorcio = (npx_cony_actual * p_divorcio.shift().fillna(0) / nSx_div).cumsum()

    p_matrimonio_div = pd.concat([p_matrimonio_div, pd.Series((omega - len(p_matrimonio_div) + 1) * [0])]).reset_index(drop = True)

    prob_cg_div = (p_matrimonio_div * factor_divorcio).fillna(0)

    # Enviudar y volver a casarse
    tabla_mort = tablas_mort_dict[info_cony['FENACIMIENTO_B']//12].copy()

    qx_cony = tabla_mort[(tabla_mort.Estado == info_cony['Estado_B']) & (tabla_mort.Sexo == info_cony[f'CDSEXO_B']) & (tabla_mort.Edad_Meses >= info_cony[f'FENACIMIENTO_B'])][f'Qx_Mensualizada_{tabla}'].copy()
    qx_cony = pd.concat([pd.Series([0]), qx_cony, pd.Series((omega - len(qx_cony) + 1) * [1])]).reset_index(drop = True)

    qx_enviudar = qx_cony * npx_cony_actual.shift().fillna(1)
    nSx_env = pd.concat([nSx_env, pd.Series((omega - len(nSx_env) + 1) * [nSx_env.iloc[-1]])]).reset_index(drop = True)

    qx_enviudar_acum = (qx_enviudar / nSx_env).cumsum()

    p_matrimonio_env = pd.concat([p_matrimonio_env, pd.Series((omega - len(p_matrimonio_env) + 1) * [0])]).reset_index(drop = True)

    prob_cg_env = p_matrimonio_env.fillna(0) * qx_enviudar_acum

    # Flujos
    # beta_afiliado = ((x_flujos * npx_afiliado * num_pagos * x_vp).iloc[::-1].cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1))).fillna(0)
    # beta_cony_act = ((x_flujos * npx_cony_actual * num_pagos * x_vp).iloc[::-1].cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_cony_actual.shift().fillna(1))).fillna(0)
    # beta_cony_act_afiliado = ((x_flujos * npx_afiliado * npx_cony_actual * num_pagos * x_vp).iloc[::-1].cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1) * npx_cony_actual.shift().fillna(1))).fillna(0)
    # beta_conjunto_cony_act = beta_afiliado + beta_cony_act - beta_cony_act_afiliado

    beta_afiliado = ((x_flujos * npx_afiliado * num_pagos * x_vp).iloc[::-1].shift().fillna(0).cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1))).fillna(0)
    beta_cony_act = ((x_flujos * npx_cony_actual * num_pagos * x_vp).iloc[::-1].shift().fillna(0).cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_cony_actual.shift().fillna(1))).fillna(0)
    beta_cony_act_afiliado = ((x_flujos * npx_afiliado * npx_cony_actual * num_pagos * x_vp).iloc[::-1].shift().fillna(0).cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1) * npx_cony_actual.shift().fillna(1))).fillna(0)
    beta_conjunto_cony_act = beta_afiliado + beta_cony_act - beta_cony_act_afiliado

    # beta_cony_nueva = ((x_flujos * npx_cony_nueva * num_pagos * x_vp).iloc[::-1].cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_cony_nueva.shift().fillna(1))).fillna(0)
    # beta_cony_nueva_afiliado = ((x_flujos * npx_afiliado * npx_cony_nueva * num_pagos * x_vp).iloc[::-1].cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1) * npx_cony_nueva.shift().fillna(1))).fillna(0)
    # beta_conjunto_cony_nueva = beta_afiliado + beta_cony_nueva - beta_cony_nueva_afiliado

    beta_cony_nueva = ((x_flujos * npx_cony_nueva * num_pagos * x_vp).iloc[::-1].shift().fillna(0).cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_cony_nueva.shift().fillna(1))).fillna(0)
    beta_cony_nueva_afiliado = ((x_flujos * npx_afiliado * npx_cony_nueva * num_pagos * x_vp).iloc[::-1].shift().fillna(0).cumsum().iloc[::-1] / (x_vp.shift().fillna(1) * x_flujos * npx_afiliado.shift().fillna(1) * npx_cony_nueva.shift().fillna(1))).fillna(0)
    beta_conjunto_cony_nueva = beta_afiliado + beta_cony_nueva - beta_cony_nueva_afiliado
 
    costo_cg_div = beta_conjunto_cony_nueva - beta_conjunto_cony_act
    costo_cg_env = beta_conjunto_cony_nueva - beta_afiliado

    costo_final_div = prob_cg_div.shift().fillna(0) * costo_cg_div
    costo_final_env = prob_cg_env.shift().fillna(0) * costo_cg_env

    return (costo_final_div + costo_final_env).fillna(0) * npx_afiliado

def aplicar_cg(df: pd.DataFrame, mtx_flujos: pd.DataFrame, mtx_vp: pd.DataFrame, num_pagos: pd.DataFrame,
                tabla_cg: pd.DataFrame, tabla_diff_edades: pd.DataFrame, fecha_cierre: datetime.date, 
                mejorar: bool = False, impacto_mortalidad: bool = False) -> pd.DataFrame:
    df = df.apply(lambda x: encontrar_p_cg(x, mtx_flujos, mtx_vp, num_pagos, tabla_cg, tabla_diff_edades, 
                                           fecha_cierre, mejorar = mejorar, impacto_mortalidad = impacto_mortalidad), axis = 1, result_type = 'expand')
    return df

# Raro cálculo para casados. Preguntar. (Hay doble shift?)

# %% Celda 34
# edades_cony_cg = edades_cony.loc[edades_cony.NMPOLIZA.isin(df_stock.NMPOLIZA),:].copy()
edades_cony_cg = edades_cony.copy()

chunks = np.array_split(edades_cony_cg, numero_nucleos)

processed_chunks = Parallel(n_jobs = numero_nucleos)(delayed(aplicar_cg)(chunk, mtx_mesadas_des, mtx_vp, num_pagos, 
                                                                         mtx_probs_cg, tabla_diff_edad_cg, fecha_cierre, 
                                                                         mejorar = False, impacto_mortalidad = impacto_mortalidad) for chunk in chunks)

mtx_cg_no_mejora = pd.concat(processed_chunks).T

mtx_cg_no_mejora.columns = edades_cony_cg.NMPOLIZA.to_list()

# df_cg_stock = pd.DataFrame(np.zeros([len(mtx_npxs_mejorada), len(df_stock[df_stock['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])].NMPOLIZA)]), 
#                            columns = df_stock[df_stock['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])].NMPOLIZA)

# mtx_cg_no_mejora = pd.concat([df_cg_stock, mtx_cg_no_mejora], axis = 1)

# %% Celda 35
processed_chunks = Parallel(n_jobs = numero_nucleos)(delayed(aplicar_cg)(chunk, mtx_mesadas_des, mtx_vp, num_pagos, 
                                                                         mtx_probs_cg, tabla_diff_edad_cg, fecha_cierre, 
                                                                         mejorar = True, impacto_mortalidad = impacto_mortalidad) for chunk in chunks)

mtx_cg_mejora = pd.concat(processed_chunks).T

mtx_cg_mejora.columns = edades_cony_cg.NMPOLIZA.to_list()

# mtx_cg_mejora = pd.concat([df_cg_stock, mtx_cg_mejora], axis = 1)

# %% Celda 36
mtx_costo_cg_no_mejora = mtx_cg_no_mejora * mtx_mesadas_des * mtx_vigencia * mtx_vp
mtx_costo_cg_mejora = mtx_cg_mejora * mtx_mesadas_des * mtx_vigencia * mtx_vp

# %% Celda 37
def encontrar_gasto_administrativo(mtx_flujos: pd.DataFrame, data: pd.DataFrame):
    return mtx_flujos * np.array(data['% GA_1'] * (1 + gasto_choque_solvencia) / 100)

mtx_gasto_cg_mejora = encontrar_gasto_administrativo(mtx_costo_cg_mejora, data)
mtx_gasto_cg_no_mejora = encontrar_gasto_administrativo(mtx_costo_cg_no_mejora, data)

# %% Celda 39
mtx_ga_ifrs4_contable = encontrar_gasto_administrativo(rva_ifrs4_contable, data)
mtx_ga_ifrs4_deslizamiento = encontrar_gasto_administrativo(rva_ifrs4_deslizamiento, data)
mtx_ga_ifrs4_extralongevidad = encontrar_gasto_administrativo(rva_ifrs4_extralongevidad, data)

# %% Celda 40
def encontrar_auxilio_funerario(mtx_mesadas: pd.DataFrame, mtx_salario_min: pd.DataFrame):
    mtx_smmlv_5  = 5 * mtx_salario_min
    mtx_smmlv_10 = 10 * mtx_salario_min

    mtx_aux = mtx_mesadas.where((mtx_mesadas >= mtx_smmlv_5), mtx_smmlv_5)
    mtx_aux = mtx_aux.where((mtx_aux < mtx_smmlv_10), mtx_smmlv_10)
    return mtx_aux

def encontrar_qx_aux(x: pd.Series, lon_reserva: int, mejorar: bool = False, impacto_mortalidad: bool = False) -> pd.DataFrame:
    if ('Afiliado' not in x.values) or (x['Tiene_Aux'] == 0): return pd.Series(np.zeros((lon_reserva)))

    afi = x == 'Afiliado'
    afi = x[afi].index[0][-1] if x[afi] is not None != 0 else None
    x = x[1:].filter(regex = f'.*{afi}$').copy()
    x.index = ['CDPARENTESCO_A', 'CDSEXO_A', 'FENACIMIENTO_A', 'Estado_A', 'Temporalidad_A', 'Estado_Civil_A']

    x['FENACIMIENTO_B'] = None
    x['Temporalidad_B'] = None
    x['Estado_B'] = None
    x['CDSEXO_B'] = None

    x['FENACIMIENTO_C'] = None
    x['Temporalidad_C'] = None
    x['Estado_C'] = None
    x['CDSEXO_C'] = None

    return encontrar_npx_lineal(x, mejorar = mejorar, auxilio_funerario = True, impacto_mortalidad = impacto_mortalidad)

def aplicar_calculo_qx_aux(df: pd.DataFrame, lon_reserva: int, mejorar: bool = False, impacto_mortalidad: bool = False) -> pd.DataFrame:
    df = df.apply(lambda x: encontrar_qx_aux(x, lon_reserva, mejorar = mejorar, impacto_mortalidad = impacto_mortalidad), axis = 1, result_type = 'expand')
    return df

# %% Celda 41
mtx_aux_fun_des = encontrar_auxilio_funerario(mtx_mesadas_inf, mtx_smmlv_des)
mtx_aux_fun_inf = encontrar_auxilio_funerario(mtx_mesadas_inf, mtx_smmlv_inf)

mtx_aux_fun_inf_des = pd.concat([mtx_aux_fun_inf[df_stock[df_stock['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])].NMPOLIZA], 
                                 mtx_aux_fun_des[df_nuevas[df_nuevas['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])].NMPOLIZA]],axis=1)

chunks = np.array_split(edades_cony, numero_nucleos)

processed_chunks = Parallel(n_jobs = numero_nucleos)(delayed(aplicar_calculo_qx_aux)(chunk, len(mtx_npxs_mejorada), 
                                                                                     mejorar = False, impacto_mortalidad = impacto_mortalidad) for chunk in chunks)

qxs_auxs_no_mejora = pd.concat(processed_chunks).T

qxs_auxs_no_mejora.columns = edades_cony.NMPOLIZA.to_list()

# %% Celda 43
processed_chunks = Parallel(n_jobs = numero_nucleos)(delayed(aplicar_calculo_qx_aux)(chunk, len(mtx_npxs_mejorada), 
                                                                                     mejorar = True, impacto_mortalidad = impacto_mortalidad) for chunk in chunks)

qxs_auxs_mejora = pd.concat(processed_chunks).T

qxs_auxs_mejora.columns = edades_cony.NMPOLIZA.to_list()

# %% Celda 44
qxs_auxs_no_mejora[qxs_auxs_no_mejora.eq(1).cumsum() >= 1] = 0
qxs_auxs_mejora[qxs_auxs_mejora.eq(1).cumsum() >= 1] = 0

# %% Celda 45
mtx_auxilio_no_mejora_inf  = mtx_aux_fun_inf * qxs_auxs_no_mejora * mtx_vp
mtx_auxilio_no_mejora_des  = mtx_aux_fun_des * qxs_auxs_no_mejora * mtx_vp
mtx_auxilio_mejora         = mtx_aux_fun_des * qxs_auxs_mejora * mtx_vp
mtx_auxilio_mejora_inf_des = mtx_aux_fun_inf_des * qxs_auxs_mejora * mtx_vp

# %% Celda 46
def encontrar_gasto_administrativo_auxilio(mtx_flujos: pd.DataFrame, data: pd.DataFrame):
    return mtx_flujos * np.array(data['GASTOS_%_S_1']/100)

mtx_auxilio_ga_no_mejora_inf = encontrar_gasto_administrativo_auxilio(mtx_auxilio_no_mejora_inf,data)
mtx_auxilio_ga_no_mejora_des = encontrar_gasto_administrativo_auxilio(mtx_auxilio_no_mejora_des,data)
mtx_auxilio_ga_mejora = encontrar_gasto_administrativo_auxilio(mtx_auxilio_mejora_inf_des,data)

# %% Celda 48
rva_ifrs4_contable_final = rva_ifrs4_contable + mtx_auxilio_no_mejora_inf + mtx_ga_ifrs4_contable + mtx_auxilio_ga_no_mejora_inf.fillna(0)
rva_ifrs4_deslizamiento_final = rva_ifrs4_deslizamiento + mtx_auxilio_no_mejora_des + mtx_ga_ifrs4_deslizamiento + mtx_auxilio_ga_no_mejora_des.fillna(0)
rva_ifrs4_cg_final = rva_ifrs4_deslizamiento_final + mtx_costo_cg_no_mejora + mtx_gasto_cg_no_mejora.fillna(0)
rva_ifrs4_extralongevidad_final = rva_ifrs4_extralongevidad + mtx_auxilio_mejora_inf_des + mtx_ga_ifrs4_extralongevidad + mtx_auxilio_ga_mejora.fillna(0) + mtx_costo_cg_mejora + mtx_gasto_cg_mejora

# %% Celda 49
#(rva_ifrs4_extralongevidad_final/mtx_vp).to_clipboard() Este código es para imprimir los flujos futuros sin descontar póliza a póliza

# %% Celda 51
# ## Tasa sura hoy
from pyxirr import xirr
 
fecha_mes_siguiente = (fecha_cierre + pd.DateOffset(days=1) - pd.DateOffset(month=1)).strftime('%Y/%m/%d')
 
last_days_aux = generate_last_days(fecha_mes_siguiente, 112)[:1334]
last_days_aux = pd.DatetimeIndex(last_days_aux)
 
fecha_nuevas_string = fecha_cierre_string[:-2] + '01'
nuevas_nuevas = df_nuevas[df_nuevas['FEVIGENCIA_INICIAL'] == fecha_nuevas_string]['NMPOLIZA'].values
 
flujos_nuevas = (
    rva_ifrs4_extralongevidad_final / mtx_vp /
    (1 + (float(data['GASTOS_%_S_1'].values[0]) / 100))
)[nuevas_nuevas].iloc[1:1200, :]
 
fd_nuevas = pd.DataFrame(last_days_aux.year.astype(int).astype(str), columns=['annio'])
 
vector_tmr = pd.read_csv(f'{ruta_mes_parametros}/vector_tmr.csv', sep=';')
vector_tmr['Fecha'] = pd.to_datetime(vector_tmr['Fecha'], dayfirst=True, errors='coerce')
vector_tmr['annio'] = vector_tmr['Fecha'].dt.year.astype(str)
 
fd_nuevas['fecha'] = pd.to_datetime(last_days_aux.astype(str))
fd_nuevas['fecha'] = fd_nuevas['fecha'] + pd.DateOffset(days=1) - pd.DateOffset(months=1)
fd_nuevas['annio_ant'] = (fd_nuevas['annio'].astype(int) - 1).astype(str)
 
annios_disponibles = vector_tmr['annio'].unique()
fd_nuevas = fd_nuevas[fd_nuevas['annio_ant'].isin(annios_disponibles)]
 
fd_nuevas = fd_nuevas.merge(vector_tmr[['annio', 'TMR']], right_on='annio', left_on='annio_ant', how='left')
fd_nuevas['dias'] = (fd_nuevas['fecha'] - fd_nuevas['fecha'].iloc[0]).dt.total_seconds() / (24 * 3600)
fd_nuevas.loc[0, 'TMR'] = 0
 
fd_nuevas['fd_factor_descuento'] = ((1 + fd_nuevas['TMR']) * (1 + pi_ultima_conocida)) ** (-fd_nuevas['dias'] / 365)
 
np.dot(fd_nuevas['fd_factor_descuento'].iloc[:1199], flujos_nuevas)
flujos_nuevas.loc[1] = flujos_nuevas.loc[1] - np.dot(fd_nuevas['fd_factor_descuento'].iloc[:1199], flujos_nuevas)
 
tasas_equivalentes_nuevas = (
    1 + flujos_nuevas.apply(lambda col: xirr(fd_nuevas['fecha'][:1199], col)).values
) / (1 + pi_ultima_conocida) - 1
 
mtx_vp_nuevas_nuevas = pd.DataFrame()
if len(tasas_equivalentes_nuevas.shape) == 1:
    mtx_vp_nuevas_nuevas = pd.DataFrame(
        1 + np.array([tasas_equivalentes_nuevas] * len(flujos_nuevas)),
        columns=[nuevas_nuevas]
    )
 
mtx_vp_sura_nuevas = mtx_vp_nuevas_nuevas
mtx_vp_sura_nuevas.columns = map(lambda x: x[0] if isinstance(x, tuple) else x, mtx_vp_sura_nuevas.columns.to_list())
 
mtx_vp_sura_nuevas

# %% Celda 52
nuevas_nuevas = nuevas_nuevas.flatten() if hasattr(nuevas_nuevas, 'ndim') and nuevas_nuevas.ndim > 1 else nuevas_nuevas
tasas_equivalentes_nuevas = tasas_equivalentes_nuevas.flatten() if hasattr(tasas_equivalentes_nuevas, 'ndim') and tasas_equivalentes_nuevas.ndim > 1 else tasas_equivalentes_nuevas

df_tasas = pd.DataFrame({
    'NMPOLIZA': nuevas_nuevas,
    'TMR%': tasas_equivalentes_nuevas
})
df_tasas

# %% Celda 53
ruta_archivo = f'{ruta_mes_parametros}/Consolidado tasas equivalentes RM.xlsx'

nuevas_nuevas = nuevas_nuevas.flatten() if hasattr(nuevas_nuevas, 'ndim') and nuevas_nuevas.ndim > 1 else nuevas_nuevas
tasas_equivalentes_nuevas = tasas_equivalentes_nuevas.flatten() if hasattr(tasas_equivalentes_nuevas, 'ndim') and tasas_equivalentes_nuevas.ndim > 1 else tasas_equivalentes_nuevas

mes_nombre = fecha_cierre.strftime('%B')
meses_esp = {
    'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril',
    'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto',
    'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
}
mes = meses_esp.get(mes_nombre, mes_nombre)
anio = fecha_cierre.year

df_nuevas_tasas = pd.DataFrame({
    'NMPOLIZA': nuevas_nuevas,
    'TMR%': tasas_equivalentes_nuevas,
    'TMR': tasas_equivalentes_nuevas * 100,
    'MES': mes,
    'AÑO': anio
})

if os.path.exists(ruta_archivo):
    df_consolidado = pd.read_excel(ruta_archivo)
else:
    df_consolidado = pd.DataFrame(columns=['NMPOLIZA', 'TMR%', 'TMR', 'MES', 'AÑO'])

df_final = pd.concat([df_consolidado, df_nuevas_tasas], ignore_index=True)
df_final = df_final.drop_duplicates(subset=['NMPOLIZA', 'MES', 'AÑO'], keep='last')

df_final.to_excel(ruta_archivo, index=False)

# %% Celda 54

df_nuevas = pd.read_csv(ruta_final_nuevas, delimiter=';', engine='pyarrow', encoding='latin-1')

ruta_consolidado = f'{ruta_mes_parametros}/Consolidado tasas equivalentes RM.xlsx'
df_tasas = pd.read_excel(ruta_consolidado)

df_nuevas_tasa_sura = df_nuevas.copy()

df_nuevas_tasa_sura = df_nuevas_tasa_sura.merge(
    df_tasas[['NMPOLIZA', 'TMR']],
    on='NMPOLIZA',
    how='left',
    suffixes=('', '_nuevo')
)

df_nuevas_tasa_sura['POINTERES_TECNICO'] = df_nuevas_tasa_sura['TMR'].combine_first(df_nuevas_tasa_sura['POINTERES_TECNICO'])
df_nuevas_tasa_sura['TASA p1']= df_nuevas_tasa_sura['TMR'].combine_first(df_nuevas_tasa_sura['TASA p1'])

df_nuevas_tasa_sura.drop(columns=['TMR'], inplace=True)

# Guardar la copia actualizada
ruta_salida = f'inputs/{fecha_ruta}/t_consolidada/{fecha_ruta}_t_consolidada_Sura_{nombre_reserva}.csv'
df_nuevas_tasa_sura.to_csv(ruta_salida, sep=';', index=False, encoding='latin-1')
print(f'T_consolidada de lo nuevo en Tasa SURA guardada en: {ruta_salida}')

# %% Celda 55
#  bd_tasas_sura = pd.read_csv(ruta_salidadelimiter = ';', engine = 'pyarrow', encoding = 'latin-1')
bd_tasas_sura = pd.read_csv(ruta_salida, delimiter=';', engine='pyarrow', encoding='latin-1')

if proyecciones or not correr_nuevas:
    bd_tasas_sura = bd_tasas_sura[~bd_tasas_sura.NMPOLIZA.isin(mtx_vp_nuevas_nuevas)]

    tasa_descuento_sura = bd_tasas_sura.POINTERES_TECNICO.to_numpy()/100

    mtx_tasas_desc_sura = tasa_descuento_sura * np.ones((len(mtx_npxs_mejorada), 1))
    mtx_tasas_desc_sura = 1 + pd.DataFrame(mtx_tasas_desc_sura)

    mtx_tasas_desc_sura.columns = bd_tasas_sura.NMPOLIZA

    mtx_tasas_tmr = tasa_interes[[col for col in tasa_interes.columns if col not in mtx_tasas_desc_sura.columns.to_list() + mtx_vp_nuevas_nuevas.columns.to_list()]].copy()

    mtx_tasas_desc_sura = pd.concat([mtx_tasas_tmr, mtx_tasas_desc_sura, mtx_vp_nuevas_nuevas], axis = 1)
    mtx_tasas_desc_sura = mtx_tasas_desc_sura.ffill()
    mtx_tasas_desc_sura = mtx_tasas_desc_sura[[pol for pol in edades_cony.NMPOLIZA]]
else:
    mtx_tasas_desc_sura = tasa_interes
    mtx_tasas_desc_sura = mtx_tasas_desc_sura[[pol for pol in edades_cony.NMPOLIZA]]

# %% Celda 57
print(ruta_final_nuevas)
df_nuevas.iloc[:,:20]

# %% Celda 58
print(ruta_final_stock)
df_stock.iloc[:,:20]

# %% Celda 59
print(ruta_final_nuevas_sura)
bd_tasas_sura.iloc[:,:20]

# %% Celda 60
if proyecciones or not correr_nuevas:
    mtx_vp_sura = 1 / (tasa_inflacion_ * mtx_tasas_desc_sura) ** (1/12)
    mtx_vp_sura = mtx_vp_sura.ffill()
    mtx_vp_sura = mtx_vp_sura.pow(range(len(mtx_vp)), axis = 0)
else:
    mtx_vp_sura = mtx_vp

mtx_vp_sura

# %% Celda 61
mtx_vp_sura = mtx_vp_sura.loc[:,~mtx_vp_sura.columns.duplicated()]
mtx_vp_sura

# %% Celda 63
edades_cony_cg = edades_cony.loc[edades_cony.NMPOLIZA.isin(df_nuevas.NMPOLIZA),:].copy()

chunks = np.array_split(edades_cony_cg, numero_nucleos)

processed_chunks = Parallel(n_jobs = numero_nucleos)(delayed(aplicar_cg)(chunk, mtx_mesadas_des, mtx_vp_sura, num_pagos, 
                                                                         mtx_probs_cg, tabla_diff_edad_cg, fecha_cierre, 
                                                                         mejorar = False, impacto_mortalidad = impacto_mortalidad) for chunk in chunks)

mtx_cg_no_mejora_sura = pd.concat(processed_chunks).T

mtx_cg_no_mejora_sura.columns = edades_cony_cg.NMPOLIZA.to_list()

df_cg_stock = pd.DataFrame(np.zeros([len(mtx_npxs_mejorada), len(df_stock[df_stock['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])].NMPOLIZA)]), 
                           columns = df_stock[df_stock['Estado Póliza'].isin(['VIGENTE ACTIVO', 'VIGENTE SUSPENDIDO'])].NMPOLIZA)

mtx_cg_no_mejora_sura = pd.concat([df_cg_stock, mtx_cg_no_mejora_sura], axis = 1)

# %% Celda 64
processed_chunks = Parallel(n_jobs = numero_nucleos)(delayed(aplicar_cg)(chunk, mtx_mesadas_des, mtx_vp_sura, num_pagos, 
                                                                         mtx_probs_cg, tabla_diff_edad_cg, fecha_cierre, 
                                                                         mejorar = True, impacto_mortalidad = impacto_mortalidad) for chunk in chunks)

mtx_cg_mejora_sura = pd.concat(processed_chunks).T

mtx_cg_mejora_sura.columns = edades_cony_cg.NMPOLIZA.to_list()

mtx_cg_mejora_sura = pd.concat([df_cg_stock, mtx_cg_mejora_sura], axis = 1)

# %% Celda 65
processed_chunks = Parallel(n_jobs = numero_nucleos)(delayed(aplicar_cg)(chunk, mtx_mesadas_des, mtx_vp_sura, num_pagos, 
                                                                         mtx_probs_cg, tabla_diff_edad_cg, fecha_cierre, 
                                                                         mejorar = True, impacto_mortalidad = impacto_mortalidad) for chunk in chunks)

mtx_cg_mejora_sura = pd.concat(processed_chunks).T

mtx_cg_mejora_sura.columns = edades_cony_cg.NMPOLIZA.to_list()

mtx_cg_mejora_sura = pd.concat([df_cg_stock, mtx_cg_mejora_sura], axis = 1)

# %% Celda 66
mtx_costo_cg_no_mejora_sura = mtx_cg_no_mejora_sura * mtx_mesadas_des * mtx_vigencia * mtx_vp_sura
mtx_costo_cg_mejora_sura = mtx_cg_mejora_sura * mtx_mesadas_des * mtx_vigencia * mtx_vp_sura

# %% Celda 67
def encontrar_gasto_administrativo(mtx_flujos: pd.DataFrame, data: pd.DataFrame):
    return mtx_flujos * np.array(data['% GA_1'] * (1 + gasto_choque_solvencia) / 100)

mtx_gasto_cg_mejora_sura = encontrar_gasto_administrativo(mtx_costo_cg_mejora_sura, data)
mtx_gasto_cg_no_mejora_sura = encontrar_gasto_administrativo(mtx_costo_cg_no_mejora_sura, data)

# %% Celda 69
rva_ifrs4_contable_sura = rva_ifrs4_contable / mtx_vp * mtx_vp_sura

rva_ifrs4_deslizamiento_sura = rva_ifrs4_deslizamiento / mtx_vp * mtx_vp_sura

rva_ifrs4_extralongevidad_sura = rva_ifrs4_extralongevidad / mtx_vp * mtx_vp_sura

mtx_auxilio_no_mejora_inf_sura  = mtx_auxilio_no_mejora_inf / mtx_vp * mtx_vp_sura
mtx_auxilio_no_mejora_des_sura  = mtx_auxilio_no_mejora_des / mtx_vp * mtx_vp_sura
mtx_auxilio_mejora_sura         = mtx_auxilio_mejora / mtx_vp * mtx_vp_sura
mtx_auxilio_mejora_inf_des_sura = mtx_auxilio_mejora_inf_des / mtx_vp * mtx_vp_sura

mtx_auxilio_ga_no_mejora_inf_sura = encontrar_gasto_administrativo_auxilio(mtx_auxilio_no_mejora_inf_sura, data)
mtx_auxilio_ga_no_mejora_des_sura = encontrar_gasto_administrativo_auxilio(mtx_auxilio_no_mejora_des_sura, data)
mtx_auxilio_ga_mejora_sura = encontrar_gasto_administrativo_auxilio(mtx_auxilio_mejora_inf_des_sura, data)

mtx_ga_ifrs4_contable_sura = encontrar_gasto_administrativo(rva_ifrs4_contable_sura, data)
mtx_ga_ifrs4_deslizamiento_sura = encontrar_gasto_administrativo(rva_ifrs4_deslizamiento_sura, data)
mtx_ga_ifrs4_extralongevidad_sura = encontrar_gasto_administrativo(rva_ifrs4_extralongevidad_sura, data)

rva_ifrs4_contable_final_sura = rva_ifrs4_contable_sura + mtx_auxilio_no_mejora_inf_sura + mtx_ga_ifrs4_contable_sura + mtx_auxilio_ga_no_mejora_inf_sura
rva_ifrs4_deslizamiento_final_sura = rva_ifrs4_deslizamiento_sura + mtx_auxilio_no_mejora_des_sura + mtx_ga_ifrs4_deslizamiento_sura + mtx_auxilio_ga_no_mejora_des_sura
rva_ifrs4_cg_final_sura = rva_ifrs4_deslizamiento_final_sura + mtx_costo_cg_no_mejora_sura + mtx_gasto_cg_no_mejora_sura
rva_ifrs4_extralongevidad_final_sura = rva_ifrs4_extralongevidad_sura + mtx_auxilio_mejora_inf_des_sura + mtx_ga_ifrs4_extralongevidad_sura + mtx_auxilio_ga_mejora_sura + mtx_costo_cg_mejora_sura + mtx_gasto_cg_mejora_sura

# %% Celda 71
reservas_flujos = pd.concat([pd.Series(last_days),(rva_ifrs4_contable_final / mtx_vp).sum(axis = 1),
                             (rva_ifrs4_deslizamiento_final / mtx_vp).sum(axis = 1),
                             (rva_ifrs4_cg_final / mtx_vp).sum(axis = 1),
                             (rva_ifrs4_extralongevidad_final / mtx_vp).sum(axis = 1)], axis = 1)

reservas_flujos.columns = ['Fecha','IFRS4','IFRS4 + Deslizamiento','IFRS4 + Deslizamiento + CG','IFRS4 + Deslizamiento + CG + Extralongevidad']

reservas_flujos.to_excel(f'inputs/{fecha_ruta}/salida/{fecha_ruta}_flujos_reservas_informe.xlsx')

# %% Celda 72
def reserva_x_riesgo(supervivencia: pd.DataFrame, auxilio_fun: pd.DataFrame, cg: pd.DataFrame,
                     gastos_admin: pd.DataFrame, gastos_aux: pd.DataFrame, gastos_cg: pd.DataFrame,
                     data: pd.DataFrame) -> pd.DataFrame:
    vect_supervivencia = supervivencia.sum()
    vect_auxilio_fun   = auxilio_fun.sum()
    vect_cg = cg.sum()

    vect_gastos_admin  = gastos_admin.sum()
    vect_gastos_aux = gastos_aux.sum()
    vect_gastos_cg = gastos_cg.sum()

    df_resumen = pd.concat([vect_supervivencia, vect_auxilio_fun, vect_cg, vect_gastos_admin, vect_gastos_aux, vect_gastos_cg], axis=1)
    df_resumen.columns = ['Supervivencia', 'Auxilio Funerario', 'Cambio de grupo', 'Gasto Administrativo', 'Gasto Auxilio', 'Gasto Cambio de Grupo']


    df_resumen['Reserva Total'] = df_resumen.sum(axis=1)
    df_resumen['FEVIGENCIA_INICIAL'] = data['FEVIGENCIA_INICIAL'].values
    df_resumen['% GA_1'] = data['% GA_1'].values
    df_resumen['POINTERES_TECNICO'] = data['POINTERES_TECNICO'].values
    df_resumen['LIBERACION_MESADA'] = (num_pagos * mtx_mesadas).loc[0]
    df_resumen['GASTO_AUXILIO'] = (mtx_auxilio_ga_mejora * qxs_auxs_mejora * mtx_vp).sum()
    df_resumen['GASTO_RENTA'] = ((mtx_gasto_cg_mejora + (mtx_ga_ifrs4_extralongevidad * mtx_npxs_mejorada))*mtx_vp).sum()

    cols_numericas = df_resumen.select_dtypes(include=[np.number]).columns
    df_resumen[cols_numericas] = df_resumen[cols_numericas]
    # df_resumen[cols_numericas] = df_resumen[cols_numericas].astype('Int64')


    return df_resumen

cg_contable = pd.DataFrame(np.zeros(rva_ifrs4_contable.shape))
cg_contable.columns = rva_ifrs4_contable.columns

dict_reservas = {
    'Contable': (rva_ifrs4_contable, mtx_auxilio_no_mejora_inf, cg_contable, mtx_ga_ifrs4_contable, mtx_auxilio_ga_no_mejora_inf, cg_contable, data),
    'Deslizamiento': (rva_ifrs4_deslizamiento, mtx_auxilio_no_mejora_des, cg_contable, mtx_ga_ifrs4_deslizamiento, mtx_auxilio_ga_no_mejora_des, cg_contable, data),
    'Deslizamiento + CG': (rva_ifrs4_deslizamiento, mtx_auxilio_no_mejora_des, mtx_costo_cg_no_mejora, mtx_ga_ifrs4_deslizamiento, mtx_auxilio_ga_no_mejora_des, mtx_gasto_cg_no_mejora, data),
    'Deslizamiento + CG + Extralong': (rva_ifrs4_extralongevidad, mtx_auxilio_mejora_inf_des, mtx_costo_cg_mejora, mtx_ga_ifrs4_extralongevidad, mtx_auxilio_ga_mejora, mtx_gasto_cg_mejora, data),
}

dict_reservas_sura = {
    'Contable': (rva_ifrs4_contable_sura, mtx_auxilio_no_mejora_inf_sura, cg_contable, mtx_ga_ifrs4_contable_sura, mtx_auxilio_ga_no_mejora_inf_sura, cg_contable, data),
    'Deslizamiento': (rva_ifrs4_deslizamiento_sura, mtx_auxilio_no_mejora_des_sura, cg_contable, mtx_ga_ifrs4_deslizamiento_sura, mtx_auxilio_ga_no_mejora_des_sura, cg_contable, data),
    'Deslizamiento + CG': (rva_ifrs4_deslizamiento_sura, mtx_auxilio_no_mejora_des_sura, mtx_costo_cg_no_mejora_sura, mtx_ga_ifrs4_deslizamiento_sura, mtx_auxilio_ga_no_mejora_des_sura, mtx_gasto_cg_no_mejora_sura, data),
    'Deslizamiento + CG + Extralong': (rva_ifrs4_extralongevidad_sura, mtx_auxilio_mejora_inf_des_sura, mtx_costo_cg_mejora_sura, mtx_ga_ifrs4_extralongevidad_sura, mtx_auxilio_ga_mejora_sura, mtx_gasto_cg_mejora_sura, data),
}

resumen_reservas = {rva: reserva_x_riesgo(*params) for rva, params in dict_reservas.items()}
resumen_reservas_sura = {rva: reserva_x_riesgo(*params) for rva, params in dict_reservas_sura.items()}

# %% Celda 73
def mostrar_resumen_bases_y_riesgos():
    print("\n------------------- RESUMEN DE BASES Y RIESGOS APLICADOS -------------------")
   
    print("\nBases de datos utilizadas:")
    if 'df_stock' in locals() or 'df_stock' in globals():
        print(f" - t_consolidada_Stock: {ruta_final_stock if 'ruta_final_stock' in locals() or 'ruta_final_stock' in globals() else 'Ruta no definida'}")
    if 'df_nuevas' in locals() or 'df_nuevas' in globals():
        print(f" - t_consolidada_Nuevo: {ruta_final_nuevas if 'ruta_final_nuevas' in locals() or 'ruta_final_nuevas' in globals() else 'Ruta no definida'}")
    if 'ruta_final_nuevas_sura' in locals() or 'ruta_final_nuevas_sura' in globals():
        print(f" - t_consolidada_Sura: {ruta_final_nuevas_sura if 'ruta_final_nuevas_sura' in locals() or 'ruta_final_nuevas_sura' in globals() else 'Ruta no definida'}")
 
    print("\nRiesgos/metodologías aplicados a cada base:\n")
    print(">> t_consolidada_Stock:")
    print("   - Reserva contable normal (rva_ifrs4_contable)")
    print("   - Factores de mejora de mortalidad (rva_ifrs4_extralongevidad)")
 
    print("\n>> t_consolidada_Nuevo:")
    print("   - Reserva contable normal (rva_ifrs4_contable)")
    print("   - Factores de mejora de mortalidad (rva_ifrs4_extralongevidad)")
    print("   - Deslizamiento/SMMLV (rva_ifrs4_deslizamiento)")
    print("   - Cambio de grupo familiar (rva_ifrs4_cg_final, rva_ifrs4_extralongevidad_final)")
    print("   - Auxilio funerario, gastos administrativos y todos los ajustes correspondientes")
 
    print("\n>> t_consolidada_Sura:")
    print("   - Reserva contable normal (rva_ifrs4_contable_sura)")
    print("   - Factores de mejora de mortalidad (rva_ifrs4_extralongevidad_sura)")
    print("   - Deslizamiento/SMMLV (rva_ifrs4_deslizamiento_sura)")
    print("   - Cambio de grupo familiar (rva_ifrs4_cg_final_sura, rva_ifrs4_extralongevidad_final_sura)")
    print("   - Auxilio funerario, gastos administrativos y todos los ajustes correspondientes")
 
    print("\n------------------------------------------------------------------------------\n")
mostrar_resumen_bases_y_riesgos()

# %% Celda 74
reservas = pd.concat([rva_ifrs4_contable_final.sum(), rva_ifrs4_extralongevidad_final.sum()], axis=1)
reservas.columns = ['IFRS4', 'IFRS17']

reservas_sura = pd.concat([rva_ifrs4_contable_final_sura.sum(), rva_ifrs4_extralongevidad_final_sura.sum()], axis=1)
reservas_sura.columns = ['IFRS4', 'IFRS17']


reservas_stock = pd.merge(
    reservas,
    df_stock[['NMPOLIZA']],
    on='NMPOLIZA',
    indicator=True,
    how='left'
).rename(columns={'_merge': 'indicador_stock'})

reservas_stock_nuevas = pd.merge(
    reservas_stock,
    df_nuevas[['NMPOLIZA']],
    on='NMPOLIZA',
    indicator=True,
    how='left'
).rename(columns={'_merge': 'indicador_nuevas'})

condiciones = [
    (reservas_stock_nuevas['indicador_stock'] == 'both'),
    (reservas_stock_nuevas['indicador_nuevas'] == 'both')
]
valores = ['stock', 'nuevo']
reservas_stock_nuevas['tipo'] = np.select(condiciones, valores, default='')
reservas_stock_nuevas = reservas_stock_nuevas.drop(columns=['indicador_stock', 'indicador_nuevas'])
reservas_stock_nuevas = reservas_stock_nuevas.set_index('NMPOLIZA')

# Identificación de "nuevo_nuevo"

mes_anterior = str(int(fecha_ruta) - 1).zfill(6)
ruta_anterior = f'inputs/{mes_anterior}/salida/RM/{mes_anterior}_{nombre_reserva}.xlsx'
reservas_anterior = pd.read_excel(ruta_anterior, sheet_name='Total por reserva TMR')
if not informe:
    try:
        reservas_stock_nuevas = reservas_stock_nuevas.merge(
            reservas_anterior[['NMPOLIZA']],
            on='NMPOLIZA',
            how='left',
            indicator=True
        )

        reservas_stock_nuevas['tipo'] = np.where(
            reservas_stock_nuevas['_merge'] == 'left_only',
            'nuevo_nuevo',
            reservas_stock_nuevas['tipo']
        )
        reservas_stock_nuevas = reservas_stock_nuevas.drop(columns=['_merge'])
    except FileNotFoundError:
        print(f'No se encontró la ruta: {ruta_anterior}!')
    except ValueError:
        print(f'No se encontró la hoja Total por reserva TMR en {ruta_anterior}')

# Asignación de las reservas por tipo
if nombre_reserva == 'Ley100':
    reservas_stock_nuevas['RESERVA'] = np.where(
        reservas_stock_nuevas['tipo'] == 'stock',
        reservas_stock_nuevas['IFRS4'],
        reservas_stock_nuevas['IFRS17']
    )
else:
    reservas_stock_nuevas['RESERVA'] = reservas_stock_nuevas['IFRS17']

# Procesamiento de reservas_sura con la columna tipo
reservas_sura = pd.merge(
    reservas_sura,
    df_stock[['NMPOLIZA']],
    on='NMPOLIZA',
    how='left',
    indicator=True
).rename(columns={'_merge': 'indicador_stock'})

reservas_sura = pd.merge(
    reservas_sura,
    df_nuevas[['NMPOLIZA']],
    on='NMPOLIZA',
    how='left',
    indicator=True
).rename(columns={'_merge': 'indicador_nuevas'})

condiciones_sura = [
    (reservas_sura['indicador_stock'] == 'both'),
    (reservas_sura['indicador_nuevas'] == 'both')
]
valores_sura = ['stock', 'nuevo']
reservas_sura['tipo'] = np.select(condiciones_sura, valores_sura, default='')

if not informe:

    reservas_sura = reservas_sura.merge(
        reservas_anterior[['NMPOLIZA']],
        on='NMPOLIZA',
        how='left',
        indicator=True
    )
    reservas_sura['tipo'] = np.where(
        reservas_sura['_merge'] == 'left_only',
        'nuevo_nuevo',
        reservas_sura['tipo']
    )
    reservas_sura = reservas_sura.drop(columns=['_merge'])

reservas_sura['RESERVA'] = reservas_stock_nuevas['IFRS17']

reservas_stock_nuevas = reservas_stock_nuevas.drop(columns=['indicador_stock', 'indicador_nuevas'], errors='ignore')
reservas_sura = reservas_sura.drop(columns=['indicador_stock', 'indicador_nuevas'], errors='ignore')

with pd.ExcelWriter(f'inputs/{fecha_ruta}/salida/{nombre_reserva}/{fecha_ruta}_{nombre_salida}') as writer:
    reservas_stock_nuevas.to_excel(writer, sheet_name='Total por reserva TMR')
    reservas_sura.to_excel(writer, sheet_name='Total por reserva Sura')

with pd.ExcelWriter(f'inputs/{fecha_ruta}/salida/{nombre_reserva}/informe/{fecha_ruta}_input_informe_{nombre_salida}') as writer:
    for tasa, resumen in {'TMR': resumen_reservas, 'Sura': resumen_reservas_sura}.items():
        resumen['Deslizamiento + CG + Extralong'].to_excel(writer, sheet_name=f'Resumen IFRS17 {tasa}')
        resumen['Contable'].to_excel(writer, sheet_name=f'Resumen Contable {tasa}')

try:
    if not informe:
        if len(data[data['NMPOLIZA'].isin(nuevas_nuevas)]):
            data.loc[data['NMPOLIZA'].isin(nuevas_nuevas), 'POINTERES_TECNICO'] = tasas_equivalentes_nuevas * 100
            data.loc[data['NMPOLIZA'].isin(nuevas_nuevas), 'TASA p1'] = tasas_equivalentes_nuevas * 100

        data[data['NMPOLIZA'].isin(nuevas_nuevas)].to_csv(
            f'inputs/{fecha_mes_ant_ruta}/t_consolidada/{fecha_mes_act_ruta}_nuevas_nuevas_{nombre_reserva}.csv',
            sep=';', encoding='latin-1'
        )
except ValueError:
    print('No se calculó tasa Sura de nuevas nuevas!')
##########   Prints para Control SOX #########

# Cálculo de los totales por tipo
totales_reserva = reservas_stock_nuevas.groupby('tipo')[['IFRS4', 'IFRS17', 'RESERVA']].sum()
# Stock
total_reserva_stock = totales_reserva.loc['stock', 'RESERVA'] if 'stock' in totales_reserva.index else 0
total_reserva_stock_ifrs4 = totales_reserva.loc['stock', 'IFRS4'] if 'stock' in totales_reserva.index else 0
total_reserva_stock_ifrs17 = totales_reserva.loc['stock', 'IFRS17'] if 'stock' in totales_reserva.index else 0

# nuevo
total_reserva_nuevo = (totales_reserva.loc['nuevo', 'RESERVA'] if 'nuevo' in totales_reserva.index else 0) + (totales_reserva.loc['nuevo_nuevo', 'RESERVA'] if 'nuevo_nuevo' in totales_reserva.index else 0)
total_reserva_nuevo_ifrs4 = (totales_reserva.loc['nuevo', 'IFRS4'] if 'nuevo' in totales_reserva.index else 0) + (totales_reserva.loc['nuevo_nuevo', 'IFRS4'] if 'nuevo_nuevo' in totales_reserva.index else 0)
total_reserva_nuevo_ifrs17 = (totales_reserva.loc['nuevo', 'IFRS17'] if 'nuevo' in totales_reserva.index else 0) + (totales_reserva.loc['nuevo_nuevo', 'IFRS17'] if 'nuevo_nuevo' in totales_reserva.index else 0)

# SURA
totales_reserva_sura = reservas_sura.groupby('tipo')[['IFRS4', 'IFRS17', 'RESERVA']].sum()

total_reserva_nuevo_sura = (totales_reserva_sura.loc['nuevo', 'IFRS17'] if 'nuevo' in totales_reserva_sura.index else 0) + (totales_reserva_sura.loc['nuevo_nuevo', 'IFRS17'] if 'nuevo_nuevo' in totales_reserva_sura.index else 0)
total_reserva_nuevo_ifrs4_sura = (totales_reserva_sura.loc['nuevo', 'IFRS4'] if 'nuevo' in totales_reserva_sura.index else 0) + (totales_reserva_sura.loc['nuevo_nuevo', 'IFRS4'] if 'nuevo_nuevo' in totales_reserva_sura.index else 0)
total_reserva_nuevo_ifrs17_sura = (totales_reserva_sura.loc['nuevo', 'IFRS17'] if 'nuevo' in totales_reserva_sura.index else 0) + (totales_reserva_sura.loc['nuevo_nuevo', 'IFRS17'] if 'nuevo_nuevo' in totales_reserva_sura.index else 0)

# Contar polizas
conteo_polizas = reservas_stock_nuevas['tipo'].value_counts()
cantidad_polizas_stock = conteo_polizas.get('stock', 0)
cantidad_polizas_nuevo = conteo_polizas.get('nuevo', 0) + conteo_polizas.get('nuevo_nuevo', 0)
cantidad_polizas_nuevo_sura= conteo_polizas.get('nuevo', 0) + conteo_polizas.get('nuevo_nuevo', 0)

end = datetime.now()

print(f'''
------------------------------------
Se ejecutó la {nombre_reserva}:
------------------------------------
      \tFecha: {fecha_ejecucion}
      \tTiempo ejecución: {end - start} minutos
      \tSe tomaron los archivos:
      \t\tNuevo: {ruta_final_nuevas}
      \t\tStock: {ruta_final_stock}
      \t\tNuevo Sura: {ruta_final_nuevas_sura}
      \tNúmero de Pólizas: {len(edades_cony)}

      \tTotal Reserva Stock: $ {total_reserva_stock:,.2f}
      \t\t- IFRS4: $ {total_reserva_stock_ifrs4:,.2f}
      \t\t- IFRS17: $ {total_reserva_stock_ifrs17:,.2f}
      \t\tPolizas en Stock: {cantidad_polizas_stock}

      \tTotal Reserva Nuevo: $ {total_reserva_nuevo:,.2f}
      \t\t- IFRS4: $ {total_reserva_nuevo_ifrs4:,.2f}
      \t\t- IFRS17: $ {total_reserva_nuevo_ifrs17:,.2f}
      \t\tPolizas en Nuevo: {cantidad_polizas_nuevo}


      \tTotal Reserva SURA: $ {total_reserva_nuevo_sura:,.2f}
      \t\t- IFRS4: $ {total_reserva_nuevo_ifrs4_sura:,.2f}
      \t\t- IFRS17: $ {total_reserva_nuevo_ifrs17_sura:,.2f}
      \t\tPolizas en Nuevo SURA: {cantidad_polizas_nuevo_sura}
------------------------------------
------------------------------------
''')

# %% Celda 77
params = pd.read_table('config_cierre.txt', delimiter = ';').set_index('Parametro')
flujos_proyectados = eval(params.loc['Flujos_proyectados'].Valor)
 
if flujos_proyectados is True:
    flujos_stock = rva_ifrs4_extralongevidad_final[df_stock.NMPOLIZA] / mtx_vp[df_stock.NMPOLIZA]
    flujos_nuevos = rva_ifrs4_extralongevidad_final[df_nuevas.NMPOLIZA] / mtx_vp[df_nuevas.NMPOLIZA]
 
    flujos_total = pd.concat([
        pd.Series(last_days, name='Fecha'),
        flujos_stock.sum(axis=1).rename('Flujo Stock IFRS17'),
        flujos_nuevos.sum(axis=1).rename('Flujo Nuevas IFRS17')
    ], axis=1)
 
    output_path = f'inputs/{fecha_ruta}/salida/{nombre_reserva}/{fecha_ruta}_flujos_sin_descuento.xlsx'
    flujos_total.to_excel(output_path, index=False)
    
    total_stock = flujos_stock.sum().sum()
    total_nuevas = flujos_nuevos.sum().sum()
    
    print(f'''
    ------------------------------------
    Se ejecutaron los flujos proyectados de {nombre_reserva}:
    ------------------------------------
            Fecha de ejecución: {fecha_ejecucion}
            Tiempo de ejecución: {end - start} minutos
            Ruta del archivo generado: {output_path}
            Número de pólizas en stock: {flujos_stock.shape[1]}
            Número de pólizas nuevas: {flujos_nuevos.shape[1]}
            Total Flujos IFRS17 Stock: ${total_stock:,.2f}
            Total Flujos IFRS17 Nuevas: ${total_nuevas:,.2f}
            Total Flujos IFRS17 Stock + Nuevas: ${total_stock + total_nuevas:,.2f}
    ------------------------------------
    ''')

# %% Celda 79
# --- TMR ---
rva_ifrs4_contable_c = mtx_mesadas_inf * mtx_npxs_mejorada * mtx_vp * num_pagos * mtx_vigencia
mtx_auxilio_mejora_c = mtx_aux_fun_inf * qxs_auxs_mejora * mtx_vp
mtx_ga_ifrs4_extralongevidad_c = encontrar_gasto_administrativo(rva_ifrs4_contable_c, data) 
mtx_auxilio_ga_mejora_c = encontrar_gasto_administrativo_auxilio(mtx_auxilio_mejora_c, data)

rva_ifrs4_extralongevidad_c = (
    rva_ifrs4_contable_c
    + mtx_auxilio_mejora_c
    + mtx_ga_ifrs4_extralongevidad_c
    + mtx_auxilio_ga_mejora_c
)

out = (
    rva_ifrs4_extralongevidad_c.sum(axis=0)
    .rename('IFRS4 + extralong')
    .rename_axis('NMPOLIZA')
    .reset_index()
)

# --- SURA ---
rva_ifrs4_contable_c_sura = mtx_mesadas_inf * mtx_npxs_mejorada * mtx_vp_sura * num_pagos * mtx_vigencia
mtx_auxilio_mejora_c_sura = mtx_aux_fun_inf * qxs_auxs_mejora * mtx_vp_sura
mtx_ga_ifrs4_extralongevidad_c_sura = encontrar_gasto_administrativo(rva_ifrs4_contable_c_sura, data) 
mtx_auxilio_ga_mejora_c_sura = encontrar_gasto_administrativo_auxilio(mtx_auxilio_mejora_c_sura, data)

rva_ifrs4_extralongevidad_c_sura = (
    rva_ifrs4_contable_c_sura
    + mtx_auxilio_mejora_c_sura
    + mtx_ga_ifrs4_extralongevidad_c_sura
    + mtx_auxilio_ga_mejora_c_sura
)

out_sura = (
    rva_ifrs4_extralongevidad_c_sura.sum(axis=0)
    .rename('IFRS4 + extralong')
    .rename_axis('NMPOLIZA')
    .reset_index()
)

from pathlib import Path

ruta_dir = Path(f"inputs/{fecha_ruta}/salida/{nombre_reserva}")
if not ruta_dir.exists():
    raise FileNotFoundError(f"La ruta no existe: {ruta_dir}")

ruta_xlsx = ruta_dir / f"{fecha_ruta}_Certificaciones.xlsx"

with pd.ExcelWriter(ruta_xlsx, engine="openpyxl") as writer:
    out.to_excel(writer, sheet_name="IFRS4 extralong tmr", index=False)
    out_sura.to_excel(writer, sheet_name="IFRS4 extralong SURA", index=False)
