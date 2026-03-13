import math
import os
import glob
import json
import time
import re
import csv
import hashlib
import google.generativeai as genai
import PIL.Image

# --- CONFIGURACIÓN DE IA ---
# REEMPLAZA CON TU API KEY REAL
GOOGLE_API_KEY = "AIzaSyCazj2wAt2N_Pv_PwoPbb1IDGNfKeilpGA"
genai.configure(api_key=GOOGLE_API_KEY)

MODELO_NOMBRE = 'gemini-2.5-flash'

try:
    model = genai.GenerativeModel(MODELO_NOMBRE, generation_config={"response_mime_type": "application/json"})
    print(f"[INIT] Sistema IA listo")
except Exception as e:
    print(f"[ERROR] Falló init IA: {e}")

# --- CONSTANTES DE NEGOCIO (REGLAS PDF 2026) ---
COSTO_MATERIAL_GR = 0.35      
TARIFA_ENERGIA_KWH = 8.00     
DESGASTE_H_UNIFICADO = 4.00   
MANO_OBRA_ESTANDAR = 30.00    
UTILIDAD_DIARIA_META = 350.00 
HORAS_TRABAJO_DIA = 12        
NUM_IMPRESORAS = 3            
NOMBRE_ARCHIVO_LOG = "Historial_Cotizaciones_Log.txt"
NOMBRE_ARCHIVO_CACHE = "gemini_cache.json"

DB_IMPRESORAS = {
    "A1_MINI": {"alias": ["mini"], "kw": 0.06, "nombre": "Bambu Lab A1 Mini"},
    "A1_STD":  {"alias": ["a1"], "kw": 0.11, "nombre": "Bambu Lab A1"},
    "AD5X":    {"alias": ["ad5x", "ad5m", "forge"], "kw": 0.13, "nombre": "Flash Forge AD5X"}
}

FACTORES_ALTURA = {0.32: 0.85, 0.28: 0.95, 0.24: 1.00, 0.20: 1.20, 0.16: 1.45, 0.12: 1.80}
FACTORES_BOQUILLA = {0.6: 0.9, 0.4: 1.0, 0.2: 1.5}
RIESGO_MATERIAL = {"PLA": 1.0, "PLA+": 1.1, "PETG": 1.2, "ABS": 1.4, "ASA": 1.4, "TPU": 1.5, "NYLON": 1.7}
RIESGO_MODELO = {"PROBADO": 1.15, "NUEVO": 1.30}

REGISTRO_COTIZACIONES = []

# --- SISTEMA DE CACHÉ ---
CACHE_DATOS = {}

def cargar_cache():
    global CACHE_DATOS
    if os.path.exists(NOMBRE_ARCHIVO_CACHE):
        try:
            with open(NOMBRE_ARCHIVO_CACHE, 'r', encoding='utf-8') as f:
                CACHE_DATOS = json.load(f)
            print(f"[SISTEMA] Caché de IA cargado ({len(CACHE_DATOS)} registros).")
        except:
            print("[SISTEMA] Error cargando caché, se iniciará vacío.")
            CACHE_DATOS = {}

def guardar_cache():
    try:
        with open(NOMBRE_ARCHIVO_CACHE, 'w', encoding='utf-8') as f:
            json.dump(CACHE_DATOS, f, indent=4)
    except Exception as e:
        print(f"[ERROR] No se pudo guardar caché: {e}")

def calcular_hash_imagen(ruta_imagen):
    try:
        with open(ruta_imagen, "rb") as f:
            file_hash = hashlib.md5()
            while chunk := f.read(8192):
                file_hash.update(chunk)
        return file_hash.hexdigest()
    except:
        return None

cargar_cache()

# --- UTILIDADES DE ARCHIVO Y MEMORIA ---
def verificar_existencia_en_log(nombre_proyecto):
    if not os.path.exists(NOMBRE_ARCHIVO_LOG):
        return False
    patron = f"PROYECTO: {nombre_proyecto.upper()}"
    try:
        with open(NOMBRE_ARCHIVO_LOG, "r", encoding="utf-8") as f:
            if patron in f.read(): return True
    except: return False
    return False

def guardar_en_log(texto_completo):
    try:
        with open(NOMBRE_ARCHIVO_LOG, "a", encoding="utf-8") as f:
            f.write(texto_completo + "\n\n" + ("#"*80) + "\n\n")
        print(f"\n[SISTEMA] Guardado en '{NOMBRE_ARCHIVO_LOG}'")
    except Exception as e:
        print(f"\n[ERROR] Falló log: {e}")

def listar_subcarpetas(ruta_base):
    try:
        items = [f for f in os.scandir(ruta_base) if f.is_dir()]
        if not items:
            print(" [!] No se encontraron carpetas en esta ruta.")
            return None
        
        print(f"\n--- CARPETAS ENCONTRADAS EN: {os.path.basename(ruta_base)} ---")
        for i, item in enumerate(items):
            print(f" {i+1}. {item.name}")
        print("-" * 40)
        
        seleccion = input(" Seleccione el número de la carpeta a cotizar: ")
        try:
            idx = int(seleccion) - 1
            if 0 <= idx < len(items):
                return items[idx].path
            else:
                print(" [!] Número inválido.")
                return None
        except:
            print(" [!] Entrada inválida.")
            return None
    except Exception as e:
        print(f" [!] Error leyendo ruta: {e}")
        return None

# --- UTILIDADES GENERALES ---
def normalizar_impresora(texto):
    if not texto: return None
    s = texto.lower()
    for key, data in DB_IMPRESORAS.items():
        for a in data["alias"]:
            if a in s: return key
    return None

def parse_tiempo(input_str):
    if not input_str: return 0.0
    s = str(input_str).lower()
    h = float(re.search(r'(\d+)\s*h', s).group(1)) if 'h' in s else 0.0
    m = float(re.search(r'(\d+)\s*m', s).group(1)) if 'm' in s else 0.0
    return h + (m/60.0)

def seleccionar_impresora_manual():
    print("\n1. A1 Mini | 2. A1 Std | 3. AD5X")
    op = input("Seleccione impresora: ")
    return {"1": "A1_MINI", "2": "A1_STD", "3": "AD5X"}.get(op, "A1_STD")

# --- REPORTE VISUAL ---
def generar_y_mostrar_reporte(res):
    lines = []
    pzas = res['Piezas']
    c_tec = res['Costo_Tecnico_Total']
    
    lines.append("\n" + "="*80)
    lines.append(f" FECHA: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f" PROYECTO: {res['Proyecto'].upper()}")
    lines.append(f" MODO: {res['Modo_Trabajo']}")
    lines.append("="*80)
    
    # [0] DETALLE MIXTO (FULL TICKET POR BANDEJA)
    if res['Es_Mixto']:
        lines.append(f"\n[!] DESGLOSE COMPLETO POR BANDEJA (LOTE MIXTO)")
        lines.append(f" *Mano de Obra Global (${res['Raw_MO']:.2f}) dividida entre {res['Num_Bandejas']} bandejas*")
        
        for det in res['Detalle_Mixto']:
            pzas_tray = det['Piezas']
            c_tec_tray = det['Costo_Tec_Total_Tray']
            
            lines.append("\n" + ("-" * 65))
            lines.append(f" TICKET: {det['Nombre'].upper()} ({pzas_tray} piezas)")
            lines.append("-" * 65)
            
            # A. VARIABLES
            lines.append(f" A. VARIABLES FÍSICAS:")
            lines.append(f"    - Peso: {det['Peso_Gr']}g | Tiempo: {det['Tiempo_H']}h")
            lines.append(f"    - Factor Altura: x{det['Audit_Factor_Altura']:.2f} | Boquilla: x{det['Audit_Factor_Boquilla']:.2f}")
            lines.append(f"    - Tiempo Efectivo (Calc): {det['Audit_H_Efec']:.2f}h")
            
            # B. COSTOS
            lines.append("-" * 65)
            lines.append(f" B. COSTOS DIRECTOS:")
            lines.append(f"   (+) Material:     ${det['Raw_Mat']:.2f}")
            lines.append(f"       -> ({det['Peso_Gr']}g * ${COSTO_MATERIAL_GR})")
            lines.append(f"   (+) Energía:      ${det['Raw_Ener']:.2f}")
            lines.append(f"   (+) Desgaste:     ${det['Raw_Desgaste']:.2f}")
            lines.append(f"       -> ({det['Audit_H_Efec']:.2f}h * ${DESGASTE_H_UNIFICADO})")
            lines.append(f"   (+) MO (Prorrat): ${det['Raw_MO_Prorrateada']:.2f}")
            
            # C. TOTALES
            lines.append("-" * 65)
            lines.append(f"   (=) COSTO BASE:   ${det['Audit_Base_Tray']:.2f}")
            lines.append(f"   (x) Riesgos:      x{det['Audit_Riesgo']:.2f}")
            lines.append(f"   (x) Penalización: x{det['Audit_Tiempo_Penalizacion']:.1f}")
            lines.append("-" * 65)
            lines.append(f"   TOTAL TÉCNICO BANDEJA: ${c_tec_tray:.2f}")
            
            # D. PRODUCTIVO
            lines.append("-" * 65)
            lines.append(f"   REF: MODO PRODUCTIVO:  ${det['PVP_Productivo_Total']:.2f}")
            lines.append(f"        -> (Costo + [Horas * Utilidad Meta])")
            lines.append(f"        UNITARIO PROD:     ${det['PVP_Productivo_Unit']:.2f}")

            # E. COMERCIAL
            lines.append(f"\n   [2] MODO COMERCIAL (BANDEJA)")
            lines.append(f"   Margen     | Total          | Unitario")
            lines.append("   " + "-"*45)
            for m in [20, 30, 40, 50]:
                t_m = det[f'Comercial_{m}%_Total']
                u_m = det[f'Comercial_{m}%_Unit']
                lines.append(f"   {m}%{'':<7} | ${t_m:<13.2f} | ${u_m:<10.2f}")
            
            # F. SOCIO (DINÁMICO + DESGLOSE UNITARIO)
            lines.append(f"\n   [#] SOCIO COMERCIAL - ESCENARIOS DE UTILIDAD")
            lines.append(f"   % Util | PVP Total    | PVP Unit   | Costo Tec  | Gana Local | TU Neto")
            lines.append("   " + "-"*75)
            for s_item in det['Socio_Tabla_Tray']:
                pct_str = f"{int(s_item['Pct']*100)}%"
                lines.append(f"   {pct_str:<6} | ${s_item['PVP_Total']:<11.2f} | ${s_item['PVP_Unit']:<9.2f} | ${s_item['Costo_Tec_Unit']:<9.2f} | ${s_item['Gana_Local_Unit']:<9.2f} | ${s_item['Utilidad_Neta_Unit']:<9.2f}")
            
            # G. DISTRIBUCION
            lines.append(f"\n   [#] DISTRIBUCIÓN 50/50 (BANDEJA)")
            lines.append(f"   PVP SUGERIDO:       ${det['PVP_Dist_Total']:.2f} (Unit: ${det['PVP_Dist_Unit']:.2f})")
            lines.append(f"   REPARTO UNITARIO:")
            lines.append(f"    > Gana Local:      ${det['Ganancia_Local_Dist_Unit']:.2f}")
            lines.append(f"    > Tú recibes:      ${det['Ingreso_Prod_Dist_Unit']:.2f}")
            lines.append(f"    > TU UTILIDAD:     ${det['Util_Neta_Prod_Dist_Unit']:.2f} (NETO)")
            lines.append("-" * 65)

    # 1. TICKET TÉCNICO GLOBAL
    lines.append(f"\n[1] TICKET DE COSTOS TÉCNICOS GLOBAL (PROYECTO COMPLETO)")
    lines.append("-" * 60)
    lines.append(f" A. VARIABLES FÍSICAS:")
    lines.append(f"    - Tiempo Impresión:  {res['Tiempo_Total_Horas']:.2f} h")
    lines.append(f"    - Factor Altura:     x{res['Audit_Factor_Altura_Prom']:.2f}")
    lines.append(f"    - Factor Boquilla:   x{res['Audit_Factor_Boquilla_Prom']:.2f}")
    lines.append(f"    - Tiempo Efectivo:   {res['Audit_Tiempo_Efectivo_Total']:.2f} h (Base Cobro)")
    lines.append(f"    - Peso Total:        {res['Peso_Total_Gr']:.2f} g")
    lines.append("-" * 60)
    lines.append(f" B. COSTOS DIRECTOS:")
    lines.append(f" (+) Material:       ${res['Raw_Mat']:.2f}")
    lines.append(f"     -> ({res['Peso_Total_Gr']:.2f}g * ${COSTO_MATERIAL_GR})")
    lines.append(f" (+) Energía:        ${res['Raw_Ener']:.2f}")
    lines.append(f"     -> (Tiempo_Efectivo * kW * Tarifa)")
    lines.append(f" (+) Desgaste:       ${res['Raw_Desgaste']:.2f}")
    lines.append(f"     -> ({res['Audit_Tiempo_Efectivo_Total']:.2f}h * ${DESGASTE_H_UNIFICADO})")
    lines.append(f" (+) Mano de Obra:   ${res['Raw_MO']:.2f}")
    lines.append(f"     -> ({res['Audit_MO_Explicacion']})")
    lines.append("-" * 60)
    lines.append(f" (=) COSTO OPERATIVO BASE:  ${res['Audit_Base_Operativa']:.2f}")
    lines.append(f" (x) Riesgos (Mat/Mod):     x{res['F_Riesgo']:.2f}")
    lines.append(f" (x) Penalización Tiempo:   x{res['F_Tiempo']:.1f}")
    lines.append("-" * 60)
    lines.append(f" TOTAL TÉCNICO:      ${c_tec:.2f}")
    if pzas > 1 and not res['Es_Mixto']: 
        lines.append(f" UNITARIO TÉCNICO:   ${res['Costo_Tecnico_Unit']:.2f}")
    
    # MODO PRODUCTIVO
    lines.append("-" * 60)
    lines.append(f" REF: MODO PRODUCTIVO:  ${res['PVP_Productivo_Total']:.2f}")
    lines.append(f"      -> (Costo Técnico + [Horas * Utilidad Meta/Hora])")
    if pzas > 1:
        lines.append(f"      UNITARIO PROD:     ${res['PVP_Productivo_Unit']:.2f}")

    if res['Modo_Trabajo'] == "CAMA LLENA":
        lines.append(f"\n[!] ANÁLISIS DE AHORRO (CAMA LLENA)")
        lines.append(f"  A. Precio Individual: ${res['Cama_Precio_Indiv_Sugerido']:.2f} c/u")
        lines.append(f"  B. Precio en Lote:    ${res['Cama_Precio_Lote_Unit_Sugerido']:.2f} c/u")
        lines.append(f"     -> Formula: (${res['Costo_Tecnico_Unit']:.2f} * 1.25)")
        lines.append(f"  >>> AHORRO:           {res['Cama_Ahorro_Porcentaje']:.1f}%")

    lines.append(f"\n[2] MODO COMERCIAL (CON FÓRMULAS)")
    lines.append(f" {'Margen':<10} | {'Total':<15} | {'Unitario':<10}")
    lines.append("-" * 55)
    for m in [20, 30, 40, 50]:
        t = res[f'Comercial_{m}%_Total']
        u = res[f'Comercial_{m}%_Unit']
        factor = 1 + (m/100)
        lines.append(f" {m}%{'':<7} | ${t:<14.2f} | ${u:<10.2f}")
        lines.append(f"            -> (${c_tec:.2f} * {factor:.2f})")
    lines.append(f" PROMEDIO:  | ${res['Com_Promedio_Total']:.2f}          | ${res['Com_Promedio_Unit']:.2f}")

    # SOCIO COMERCIAL GLOBAL (DINÁMICO + DESGLOSE UNITARIO)
    lines.append(f"\n[#] SOCIO COMERCIAL (GLOBAL) - ESCENARIOS DE UTILIDAD")
    lines.append(f" % Util | PVP Total    | PVP Unit   | Costo Tec  | Gana Local | TU Neto (U)")
    lines.append("-" * 78)
    for s_item in res['Socio_Tabla_Global']:
        pct_str = f"{int(s_item['Pct']*100)}%"
        lines.append(f" {pct_str:<6} | ${s_item['PVP_Total']:<11.2f} | ${s_item['PVP_Unit']:<9.2f} | ${s_item['Costo_Tec_Unit']:<9.2f} | ${s_item['Gana_Local_Unit']:<9.2f} | ${s_item['Utilidad_Neta_Unit']:<9.2f}")

    lines.append(f"\n[#] DISTRIBUCIÓN 50/50 (Pág 11)")
    lines.append(f" PVP SUGERIDO:       ${res['PVP_Dist_Total']:.2f} (Unit: ${res['PVP_Dist_Unit']:.2f})")
    lines.append(f"     -> Formula: Costo(${c_tec:.2f}) * 2.5")
    lines.append(f" REPARTO UNITARIO:")
    lines.append(f"  > Gana el Local:   ${res['Ganancia_Local_Dist_Unit']:.2f}")
    lines.append(f"     -> Formula: (PVP * 0.50) / {pzas} pzas")
    lines.append(f"  > Tú recibes:      ${res['Ingreso_Prod_Dist_Unit']:.2f}")
    lines.append(f"     -> Formula: (PVP * 0.50) / {pzas}")
    lines.append(f"  > TU UTILIDAD:     ${res['Util_Neta_Prod_Dist_Unit']:.2f} (NETO LIBRE)")
    lines.append(f"     -> Formula: (Ingreso - Costo) / {pzas}")
    
    lines.append("\n" + "="*80)
    texto_final = "\n".join(lines)
    print(texto_final)
    guardar_en_log(texto_final)

# --- NÚCLEO MATEMÁTICO ---
def calcular_proyecto(nombre, datos, es_nuevo, es_dividida, es_cama_llena, es_mixto):
    acum_mat = sum(d['peso'] * COSTO_MATERIAL_GR for d in datos)
    acum_ener, acum_desg, t_horas = 0, 0, 0
    t_pzas = 1 if es_dividida else sum(d['piezas'] for d in datos)
    peso_total = sum(d['peso'] for d in datos)
    
    audit_t_efectivo_total = 0
    sum_f_altura, sum_f_boquilla = 0, 0

    for d in datos:
        imp = DB_IMPRESORAS[d['impresora_key']]
        f_alt = FACTORES_ALTURA.get(d['altura'], 1.0)
        f_boq = FACTORES_BOQUILLA.get(d['boquilla'], 1.0)
        sum_f_altura += f_alt; sum_f_boquilla += f_boq
        h_efec = d['tiempo_h'] * f_alt * f_boq
        audit_t_efectivo_total += h_efec
        tarifa = TARIFA_ENERGIA_KWH * (1.3 if d['material'] in ["ABS","ASA","NYLON"] else 1.0)
        acum_ener += h_efec * imp['kw'] * tarifa
        acum_desg += h_efec * DESGASTE_H_UNIFICADO
        t_horas += d['tiempo_h']

    avg_f_alt = sum_f_altura / len(datos) if datos else 0
    avg_f_boq = sum_f_boquilla / len(datos) if datos else 0
    mo = 0 if len(datos) >= 3 else MANO_OBRA_ESTANDAR
    ex_bandejas = (len(datos) * 10.0) if len(datos) >= 3 else 0.0
    mo_total = mo + ex_bandejas
    base_operativa = acum_mat + acum_ener + acum_desg + mo_total
    
    riesgo_mat = RIESGO_MATERIAL.get(datos[0]['material'], 1.0)
    riesgo_mod = RIESGO_MODELO["NUEVO"] if es_nuevo else RIESGO_MODELO["PROBADO"]
    f_riesgo_total = riesgo_mat * riesgo_mod
    f_tiempo = 1.5 if t_horas >= 24 else 1.0
    costo_tec = (base_operativa * f_riesgo_total) * f_tiempo
    
    # PRODUCTIVO GLOBAL
    horas_disp = NUM_IMPRESORAS * HORAS_TRABAJO_DIA
    utilidad_h = UTILIDAD_DIARIA_META / horas_disp
    pvp_prod = costo_tec + (t_horas * utilidad_h)

    # Detalle Mixto (CALCULO COMPLETO POR BANDEJA)
    detalle_mixto = []
    if es_mixto:
        mo_por_bandeja = mo_total / len(datos)
        for idx, d in enumerate(datos):
            imp = DB_IMPRESORAS[d['impresora_key']]
            f_alt_t = FACTORES_ALTURA.get(d['altura'], 1.0)
            f_boq_t = FACTORES_BOQUILLA.get(d['boquilla'], 1.0)
            h_efec = d['tiempo_h'] * f_alt_t * f_boq_t
            tarifa = TARIFA_ENERGIA_KWH * (1.3 if d['material'] in ["ABS","ASA","NYLON"] else 1.0)
            
            c_mat = d['peso'] * COSTO_MATERIAL_GR
            c_ener = h_efec * imp['kw'] * tarifa
            c_desg = h_efec * DESGASTE_H_UNIFICADO
            base_tray = c_mat + c_ener + c_desg + mo_por_bandeja
            c_tec_tray = (base_tray * f_riesgo_total) * f_tiempo
            
            # --- CÁLCULOS FINANCIEROS POR BANDEJA ---
            # 1. Productivo
            pvp_prod_tray = c_tec_tray + (d['tiempo_h'] * utilidad_h)
            
            # 2. Socio (TABLA DINÁMICA POR BANDEJA + DESGLOSE UNIT)
            socio_tabla_tray = []
            fee_tray = c_tec_tray * 0.05
            for pct_util in [0.5, 1.0, 1.5, 2.0]:
                util_amount = c_tec_tray * pct_util
                pvp_s = c_tec_tray + fee_tray + util_amount
                socio_tabla_tray.append({
                    "Pct": pct_util,
                    "PVP_Total": pvp_s,
                    "PVP_Unit": pvp_s / d['piezas'],
                    "Costo_Tec_Unit": c_tec_tray / d['piezas'],
                    "Gana_Local_Unit": (fee_tray + (util_amount * 0.5)) / d['piezas'],
                    "Utilidad_Neta_Unit": (util_amount * 0.5) / d['piezas']
                })
            
            # 3. Dist
            pvp_dist_tray = c_tec_tray * 2.5

            info_tray = {
                "Nombre": f"Bandeja {idx+1}", "Piezas": d['piezas'], "Peso_Gr": d['peso'], "Tiempo_H": d['tiempo_h'],
                "Raw_Mat": c_mat, "Raw_Ener": c_ener, "Raw_Desgaste": c_desg, "Raw_MO_Prorrateada": mo_por_bandeja,
                "Audit_Base_Tray": base_tray, "Audit_Riesgo": f_riesgo_total, "Audit_Tiempo_Penalizacion": f_tiempo,
                "Audit_H_Efec": h_efec, "Audit_Factor_Altura": f_alt_t, "Audit_Factor_Boquilla": f_boq_t,
                "Costo_Tec_Total_Tray": c_tec_tray, "Unitario_Tecnico": c_tec_tray / d['piezas'],
                "PVP_Productivo_Total": pvp_prod_tray, "PVP_Productivo_Unit": pvp_prod_tray / d['piezas'],
                "Socio_Tabla_Tray": socio_tabla_tray,
                "PVP_Dist_Total": pvp_dist_tray, "PVP_Dist_Unit": pvp_dist_tray / d['piezas'],
                "Ganancia_Local_Dist_Unit": (pvp_dist_tray * 0.5)/d['piezas'],
                "Ingreso_Prod_Dist_Unit": (pvp_dist_tray * 0.5)/d['piezas'],
                "Util_Neta_Prod_Dist_Unit": ((pvp_dist_tray * 0.5) - c_tec_tray)/d['piezas']
            }
            # 4. Comercial (Tabla)
            for m in [20, 30, 40, 50]:
                t_m = c_tec_tray * (1 + m/100)
                info_tray[f"Comercial_{m}%_Total"] = t_m
                info_tray[f"Comercial_{m}%_Unit"] = t_m / d['piezas']
            
            detalle_mixto.append(info_tray)

    modo = "STANDARD"
    if es_dividida: modo = "PIEZA DIVIDIDA"
    if es_cama_llena: modo = "CAMA LLENA"
    if es_mixto: modo = "LOTE MIXTO"

    # TABLA SOCIO GLOBAL (DINÁMICA + DESGLOSE UNIT)
    socio_tabla_global = []
    fee_global = costo_tec * 0.05
    for pct_util in [0.5, 1.0, 1.5, 2.0]:
        util_amount = costo_tec * pct_util
        pvp_s = costo_tec + fee_global + util_amount
        socio_tabla_global.append({
            "Pct": pct_util,
            "PVP_Total": pvp_s,
            "PVP_Unit": pvp_s / t_pzas,
            "Costo_Tec_Unit": costo_tec / t_pzas,
            "Gana_Local_Unit": (fee_global + (util_amount * 0.5)) / t_pzas,
            "Utilidad_Neta_Unit": (util_amount * 0.5) / t_pzas
        })

    res = {
        "Proyecto": nombre, "Piezas": t_pzas, "Modo_Trabajo": modo, "Es_Dividida": es_dividida, "Es_Mixto": es_mixto,
        "Detalle_Mixto": detalle_mixto,
        "Tiempo_Total_Horas": t_horas, "Peso_Total_Gr": peso_total, "Num_Bandejas": len(datos),
        "Raw_Mat": acum_mat, "Raw_Ener": acum_ener, "Raw_Desgaste": acum_desg, "Raw_MO": mo_total, 
        "Audit_Tiempo_Efectivo_Total": audit_t_efectivo_total,
        "Audit_Factor_Altura_Prom": avg_f_alt, "Audit_Factor_Boquilla_Prom": avg_f_boq,
        "Audit_Base_Operativa": base_operativa, "Audit_MO_Explicacion": f"Tarifa Fija (${MANO_OBRA_ESTANDAR})" if mo > 0 else f"{len(datos)} bandejas x $10",
        "F_Riesgo": round(f_riesgo_total, 2), "F_Tiempo": f_tiempo,
        "Costo_Tecnico_Total": costo_tec, "Costo_Tecnico_Unit": costo_tec/t_pzas,
        "PVP_Productivo_Total": pvp_prod, "PVP_Productivo_Unit": pvp_prod / t_pzas if t_pzas > 0 else 0,
        "Socio_Tabla_Global": socio_tabla_global
    }
    
    if es_cama_llena and t_pzas > 1:
        costo_ops_unitario = (acum_mat + acum_ener + acum_desg) / t_pzas
        base_individual = costo_ops_unitario + MANO_OBRA_ESTANDAR
        costo_tec_individual = (base_individual * f_riesgo_total) * f_tiempo
        precio_indiv_sugerido = costo_tec_individual * 1.35
        precio_lote_unit = (costo_tec / t_pzas) * 1.25
        ahorro_pct = ((precio_indiv_sugerido - precio_lote_unit) / precio_indiv_sugerido) * 100
        res.update({"Cama_Precio_Indiv_Sugerido": precio_indiv_sugerido, "Cama_Precio_Lote_Unit_Sugerido": precio_lote_unit, "Cama_Ahorro_Porcentaje": ahorro_pct})

    # Comercial
    sum_c = 0
    for m in [0.2, 0.3, 0.4, 0.5]:
        pvp = costo_tec * (1 + m)
        res[f"Comercial_{int(m*100)}%_Total"] = pvp
        res[f"Comercial_{int(m*100)}%_Unit"] = pvp/t_pzas
        sum_c += pvp
    res["Com_Promedio_Total"] = sum_c / 4
    res["Com_Promedio_Unit"] = res["Com_Promedio_Total"] / t_pzas

    # Socio & Dist (STATIC PLACEHOLDERS IF NEEDED, BUT WE USE TABLES NOW)
    # Keeping Dist for now
    pvp_dist = costo_tec * 2.5
    res.update({"PVP_Dist_Total": pvp_dist, "PVP_Dist_Unit": pvp_dist/t_pzas, "Ganancia_Local_Dist_Unit": (pvp_dist * 0.5)/t_pzas, "Ingreso_Prod_Dist_Unit": (pvp_dist * 0.5)/t_pzas, "Util_Neta_Prod_Dist_Unit": ((pvp_dist * 0.5) - costo_tec)/t_pzas})
    
    return res

# --- PROCESAMIENTO ---
def capturar_datos(img_path=None):
    if img_path:
        # 1. VERIFICAR CACHÉ
        file_hash = calcular_hash_imagen(img_path)
        if file_hash and file_hash in CACHE_DATOS:
            print(f"   [CACHE] Datos recuperados de memoria.", end="", flush=True)
            d = CACHE_DATOS[file_hash]
            print(" [OK]")
            k_imp = normalizar_impresora(d.get("impresora_detectada")) or seleccionar_impresora_manual()
            return {"impresora_key": k_imp, "material": d.get("material", "PLA"), "tiempo_h": parse_tiempo(d.get("tiempo_str")), "peso": d.get("peso_g", 0), "altura": d.get("altura_capa", 0.2), "boquilla": d.get("boquilla", 0.4)}

        # 2. SI NO ESTÁ EN CACHÉ, CONSULTAR IA
        print(f"   [IA] Conectando con Gemini para {os.path.basename(img_path)}...", end="", flush=True)
        prompt = """
        Analiza esta captura de pantalla de un Slicer 3D (Orca/Bambu/FlashPrint).
        Extrae la siguiente información técnica con precisión:
        1. Impresora: Busca 'A1', 'A1 Mini', 'FlashForge', 'AD5M', 'Bambu'.
        2. Material: Tipo de filamento (PLA, PETG, ABS, TPU, ASA).
        3. Tiempo: Tiempo de impresión estimado (Ej: '2h 30m', '45m').
        4. Peso: Peso del filamento usado en gramos (Ej: '150.5g').
        5. Altura de Capa (Layer Height): En mm (Ej: 0.20, 0.16, 0.24). Si no es visible, asume 0.2.
        6. Boquilla (Nozzle): Diámetro en mm (Ej: 0.4, 0.6). Si no es visible, asume 0.4.

        Responde ÚNICAMENTE con este JSON válido:
        {"impresora_detectada": "string", "material": "string", "tiempo_str": "string", "peso_g": float, "altura_capa": float, "boquilla": float}
        """
        try:
            raw_text = model.generate_content([prompt, PIL.Image.open(img_path)]).text
            d = json.loads(raw_text.replace('```json','').replace('```',''))
            
            # 3. GUARDAR EN CACHÉ
            if file_hash:
                CACHE_DATOS[file_hash] = d
                guardar_cache()
            
            print(" [OK]")
            k_imp = normalizar_impresora(d.get("impresora_detectada")) or seleccionar_impresora_manual()
            return {"impresora_key": k_imp, "material": d.get("material", "PLA"), "tiempo_h": parse_tiempo(d.get("tiempo_str")), "peso": d.get("peso_g", 0), "altura": d.get("altura_capa", 0.2), "boquilla": d.get("boquilla", 0.4)}
        except Exception as e: 
            print(f" [ERROR] {e}")
            return capturar_datos(None) 
    else:
        k_imp = seleccionar_impresora_manual()
        return {"impresora_key": k_imp, "material": input(" Material (PLA/ABS): ").upper(), "tiempo_h": parse_tiempo(input(" Tiempo: ")), "peso": float(input(" Peso (g): ")), "altura": float(input(" Altura: ")), "boquilla": float(input(" Boquilla: "))}

def ejecutar_flujo_carpeta(nombre, ruta_carpeta):
    imgs = glob.glob(os.path.join(ruta_carpeta, "*.png")) + glob.glob(os.path.join(ruta_carpeta, "*.jpg"))
    if not imgs: 
        print(f" [!] Carpeta vacía: {nombre}")
        return None
    
    es_div = input(f"\n¿'{nombre}' es una sola pieza dividida? (s/n): ").lower() == 's'
    es_mixto = False
    es_cama = False
    
    if not es_div:
        if len(imgs) > 1:
            es_mixto = input(f"¿'{nombre}' contiene figuras DIFERENTES en cada bandeja? (s/n): ").lower() == 's'
        if not es_mixto:
            es_cama = input(f"¿Es cotización de CAMA LLENA? (s/n): ").lower() == 's'
    
    lista = []
    for im in imgs:
        item = capturar_datos(im)
        if es_mixto or (not es_div and not es_mixto):
            item["piezas"] = int(input(f"   > Piezas en placa '{os.path.basename(im)}': ") or 1)
        else:
            item["piezas"] = 1
        lista.append(item)
    
    res = calcular_proyecto(nombre, lista, input(" ¿Modelo nuevo? (s/n): ") == 's', es_div, es_cama, es_mixto)
    generar_y_mostrar_reporte(res)
    return res

def main():
    while True:
        print("\n--- GESTIÓN DE COTIZACIONES v38 (DESGLOSE UNITARIO) ---")
        print("1. Lote de Carpetas (Batch)")
        print("2. Carpeta Única (Seleccionar de Lista)")
        print("3. Manual")
        print("4. Exportar CSV y Salir")
        op = input("Seleccione: ")
        
        if op == "1":
            ruta = input("Ruta carpeta maestra: ")
            for sub in [f.path for f in os.scandir(ruta) if f.is_dir()]:
                nom = os.path.basename(sub)
                if verificar_existencia_en_log(nom):
                    print(f" [!] OMITIDO (YA EXISTE): {nom}")
                    continue
                r = ejecutar_flujo_carpeta(nom, sub)
                if r: REGISTRO_COTIZACIONES.append(r)

        elif op == "2":
            ruta_maestra = input("Ruta de la carpeta maestra (donde están los proyectos): ")
            ruta_elegida = listar_subcarpetas(ruta_maestra)
            
            if ruta_elegida:
                nom = os.path.basename(ruta_elegida)
                if verificar_existencia_en_log(nom):
                    print(f" [!] ALERTA: '{nom}' ya fue cotizado.")
                    if input(" ¿Re-cotizar? (s/n): ").lower() != 's': continue
                r = ejecutar_flujo_carpeta(nom, ruta_elegida)
                if r: REGISTRO_COTIZACIONES.append(r)

        elif op == "3":
            nom = input("Nombre Proyecto: ")
            if verificar_existencia_en_log(nom):
                print(f" [!] ALERTA: '{nom}' ya existe.")
                if input(" ¿Continuar? (s/n): ").lower() != 's': continue
            
            es_div = input("¿Es pieza dividida? (s/n): ").lower() == 's'
            es_mixto = False
            es_cama = False
            if not es_div:
                 es_mixto = input("¿Son figuras DIFERENTES por bandeja? (s/n): ").lower() == 's'
                 if not es_mixto: es_cama = input("¿Es Cama Llena? (s/n): ").lower() == 's'
            
            lista = []
            while True:
                item = capturar_datos()
                if es_mixto or (not es_div and not es_mixto):
                    item["piezas"] = int(input("  Piezas en placa: ") or 1)
                else:
                    item["piezas"] = 1
                lista.append(item)
                if input(" ¿Otra placa? (s/n): ") != 's': break
            res = calcular_proyecto(nom, lista, input(" ¿Modelo nuevo? (s/n): ") == 's', es_div, es_cama, es_mixto)
            generar_y_mostrar_reporte(res)
            REGISTRO_COTIZACIONES.append(res)
        
        elif op == "4":
            if REGISTRO_COTIZACIONES:
                fname = f"Reporte_Final_v38_{int(time.time())}.csv"
                with open(fname, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=REGISTRO_COTIZACIONES[0].keys())
                    writer.writeheader()
                    writer.writerows(REGISTRO_COTIZACIONES)
                print(f"Exportado: {fname}")
            break

if __name__ == "__main__":
    main()