#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Reglas de Negocio - Cotizador 3D v38 (2026)
--------------------------------------------------------------------------------
Este módulo implementa las reglas definidas en NEGOCIO.MD (Actualizado 2026).
Todas las constantes y fórmulas están alineadas con la política de amortización y energía vigente.
"""

import math
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

# --- 1. CONSTANTES DE COSTOS DIRECTOS (Moneda: MXN) ---
COSTO_MATERIAL_MXN_GR = 0.35
TARIFA_ENERGIA_BASE_KWH = 8.00  # Tarifa DAC Segura
DESGASTE_MAQUINA_HORA = 4.00    # Unificado
MANO_OBRA_ESTANDAR = 30.00      # 1-2 bandejas (Fijo por pedido)
MANO_OBRA_MULTIBANDEJA = 10.00  # >= 3 bandejas (Por cada bandeja)

# --- 2. PARÁMETROS DE INFRAESTRUCTURA ---
NUM_IMPRESORAS = 3
HORAS_TRABAJO_DIA = 12
META_UTILIDAD_DIARIA_POR_IMPRESORA = 350.00
META_UTILIDAD_DIARIA_TOTAL = META_UTILIDAD_DIARIA_POR_IMPRESORA * NUM_IMPRESORAS  # $1,050.00

# Costo Hora Productivo (Modo Capacidad)
# $1,050.00 / (3 imp * 12 h) = $29.166...
COSTO_HORA_PRODUCTIVO = META_UTILIDAD_DIARIA_TOTAL / (NUM_IMPRESORAS * HORAS_TRABAJO_DIA)

# Consumo Eléctrico (kW)
DB_IMPRESORAS = {
    "A1_MINI": {"kw": 0.06, "nombre": "Bambu Lab A1 Mini"},
    "A1_STD":  {"kw": 0.11, "nombre": "Bambu Lab A1"},
    "AD5X":    {"kw": 0.13, "nombre": "Flash Forge AD5X"}
}

# --- 3. FACTORES TÉCNICOS ---
FACTORES_ALTURA = {
    0.32: 0.85,
    0.28: 0.95,
    0.24: 1.00,
    0.20: 1.20,
    0.16: 1.45,
    0.12: 1.80
}

FACTORES_BOQUILLA = {
    0.6: 0.9,
    0.4: 1.0,
    0.2: 1.5
}

# --- 4. GESTIÓN DE RIESGOS ---
RIESGO_MATERIAL = {
    "PLA": 1.0,
    "PLA+": 1.1,
    "PETG": 1.2,
    "ABS": 1.4,
    "ASA": 1.4,
    "TPU": 1.5,
    "NYLON": 1.7
}

RIESGO_MODELO = {
    "PROBADO": 1.15,
    "NUEVO": 1.30
}

# Materiales que requieren Cama Caliente > 70°C (Recargo Energético +30%)
MATERIALES_TECNICOS = ["ABS", "ASA", "NYLON"]


@dataclass
class BandejaInput:
    nombre: str
    impresora_key: str  # "A1_MINI", "A1_STD", "AD5X"
    material: str       # "PLA", "PETG", etc.
    tiempo_horas: float
    peso_gramos: float
    altura_capa: float
    boquilla: float
    piezas: int = 1


class Cotizador3D:
    """Calculadora de cotizaciones basada en reglas de negocio 2026."""

    def obtener_factor_altura(self, altura: float) -> float:
        return FACTORES_ALTURA.get(altura, 1.0)

    def obtener_factor_boquilla(self, boquilla: float) -> float:
        return FACTORES_BOQUILLA.get(boquilla, 1.0)

    def es_material_tecnico(self, material: str) -> bool:
        return material.upper() in MATERIALES_TECNICOS

    def calcular_tiempo_efectivo(self, horas_base: float, f_altura: float, f_boquilla: float) -> float:
        """Regla 5.1: TIEMPO_EFECTIVO = HORAS_BASE × FACTOR_ALTURA × FACTOR_BOQUILLA"""
        return horas_base * f_altura * f_boquilla

    def calcular_costo_bandeja(self, bandeja: BandejaInput) -> Dict:
        """Calcula los costos directos de una sola bandeja."""
        
        # 1. Factores
        f_alt = self.obtener_factor_altura(bandeja.altura_capa)
        f_boq = self.obtener_factor_boquilla(bandeja.boquilla)
        
        # 2. Tiempo Efectivo
        t_efectivo = self.calcular_tiempo_efectivo(bandeja.tiempo_horas, f_alt, f_boq)
        
        # 3. Energía
        # Regla 7: Recargos Energéticos Especiales (+30% si es técnico)
        tarifa_energia = TARIFA_ENERGIA_BASE_KWH
        if self.es_material_tecnico(bandeja.material):
            tarifa_energia *= 1.3
            
        consumo_kw = DB_IMPRESORAS.get(bandeja.impresora_key, DB_IMPRESORAS["A1_STD"])["kw"]
        # Costo Energía = Tiempo Efectivo * kW * Tarifa
        # Nota: MD dice "Costo Máquina = TIEMPO_EFECTIVO × (COSTO_ENERGIA_H...)"
        # Esto implica que la tarifa horaria también se multiplica por el tiempo efectivo.
        costo_energia_h = consumo_kw * tarifa_energia
        costo_energia_total = t_efectivo * costo_energia_h
        
        # 4. Desgaste
        # Regla 5.2: (DESGASTE_H × FACTOR_ALTURA × FACTOR_BOQUILLA)
        # Multiplicado por TIEMPO_EFECTIVO en la fórmula final de Costo Máquina.
        costo_desgaste_base = DESGASTE_MAQUINA_HORA * f_alt * f_boq
        costo_desgaste_total = t_efectivo * costo_desgaste_base
        
        # 5. Material
        costo_material = bandeja.peso_gramos * COSTO_MATERIAL_MXN_GR
        
        return {
            "tiempo_efectivo": t_efectivo,
            "costo_energia": costo_energia_total,
            "costo_desgaste": costo_desgaste_total,
            "costo_material": costo_material,
            "f_altura": f_alt,
            "f_boquilla": f_boq,
            "es_tecnico": self.es_material_tecnico(bandeja.material)
        }

    def calcular_proyecto(self, bandejas: List[BandejaInput], es_nuevo: bool = False, operacion_24h: bool = False):
        """Calcula el proyecto completo aplicando reglas globales."""
        
        # Acumuladores
        costo_material_total = 0.0
        costo_energia_total = 0.0
        costo_desgaste_total = 0.0
        tiempo_efectivo_total = 0.0
        tiempo_real_total = 0.0
        piezas_total = sum(b.piezas for b in bandejas)
        
        detalle_bandejas = []
        
        for b in bandejas:
            res = self.calcular_costo_bandeja(b)
            costo_material_total += res["costo_material"]
            costo_energia_total += res["costo_energia"]
            costo_desgaste_total += res["costo_desgaste"]
            tiempo_efectivo_total += res["tiempo_efectivo"]
            tiempo_real_total += b.tiempo_horas
            detalle_bandejas.append(res)
            
        # --- Lógica de Mano de Obra (Regla 1) ---
        num_bandejas = len(bandejas)
        if num_bandejas >= 3:
            mano_obra_total = num_bandejas * MANO_OBRA_MULTIBANDEJA
            tipo_mo = f"Multibandeja ({num_bandejas} x ${MANO_OBRA_MULTIBANDEJA})"
        else:
            mano_obra_total = MANO_OBRA_ESTANDAR
            tipo_mo = f"Estándar (Fija ${MANO_OBRA_ESTANDAR})"
            
        # --- Costo Base Operativo ---
        costo_base = costo_material_total + costo_energia_total + costo_desgaste_total + mano_obra_total
        
        # --- Riesgos y Penalizaciones ---
        # Riesgo Material (Usamos el máximo riesgo de las bandejas por seguridad o el del material principal)
        # Asumimos el riesgo del primer material o el más alto. Usaremos el más alto para proteger el proyecto.
        riesgos_m = [RIESGO_MATERIAL.get(b.material, 1.0) for b in bandejas]
        riesgo_material = max(riesgos_m) if riesgos_m else 1.0
        
        riesgo_modelo = RIESGO_MODELO["NUEVO"] if es_nuevo else RIESGO_MODELO["PROBADO"]
        factor_riesgo_total = riesgo_material * riesgo_modelo
        
        # Penalización Tiempo (Regla 4)
        factor_tiempo = 1.5 if (tiempo_real_total >= 24 or operacion_24h) else 1.0
        
        # --- COSTO TÉCNICO FINAL ---
        costo_tecnico = (costo_base * factor_riesgo_total) * factor_tiempo
        
        # --- GENERACIÓN DE PRECIOS ---
        
        # A. MODO COMERCIAL
        precios_comerciales = {}
        for margen in [20, 30, 40, 50]:
            precios_comerciales[f"{margen}%"] = costo_tecnico * (1 + margen/100)
        precios_comerciales["Promedio (35%)"] = costo_tecnico * 1.35
        
        # B. MODO PRODUCTIVO
        # Regla 6.B: PVP = COSTO_RIESGO + (TIEMPO_EFECTIVO * UtilidadHora)
        # Nota: COSTO_RIESGO es el costo técnico final.
        pvp_productivo = costo_tecnico + (tiempo_efectivo_total * COSTO_HORA_PRODUCTIVO)
        
        # C. MODO CAMA LLENA
        # Recalculamos MO y Margen específico
        # MO fija de $30 siempre (aunque sean muchas piezas, es 1 placa llena -> 1 bandeja lógica)
        # Si el input viene como 1 bandeja con muchas piezas, la MO ya es $30.
        # Si son múltiples bandejas físicas para "llenar cama", aplica la regla multibandeja?
        # Asumiremos "Cama Llena" como 1 sesión de impresión masiva.
        mo_cama_llena = MANO_OBRA_ESTANDAR
        costo_base_cama = costo_material_total + costo_energia_total + costo_desgaste_total + mo_cama_llena
        costo_tecnico_cama = (costo_base_cama * factor_riesgo_total) * factor_tiempo
        # Margen reducido 25%
        pvp_cama_llena = costo_tecnico_cama * 1.25
        
        # D. SOCIO COMERCIAL
        # Fee 5% sobre Costo Operativo (Costo Técnico)
        fee_exhibicion = costo_tecnico * 0.05
        escenarios_socio = []
        for nivel, pct in [("Básico", 0.50), ("Estándar", 1.00), ("Premium", 1.50), ("Exclusivo", 2.00)]:
            utilidad_bruta = costo_tecnico * pct
            pvp_final = costo_tecnico + fee_exhibicion + utilidad_bruta
            reparto_productor = costo_tecnico + (utilidad_bruta * 0.50)
            reparto_local = fee_exhibicion + (utilidad_bruta * 0.50)
            
            escenarios_socio.append({
                "Nivel": nivel,
                "Utilidad_%": int(pct*100),
                "PVP_Cliente": pvp_final,
                "Tu_Pago": reparto_productor,
                "Pago_Local": reparto_local
            })

        return {
            "resumen_fisico": {
                "peso_total_g": costo_material_total / COSTO_MATERIAL_MXN_GR,
                "tiempo_real_h": tiempo_real_total,
                "tiempo_efectivo_h": tiempo_efectivo_total,
                "piezas": piezas_total,
                "bandejas": num_bandejas
            },
            "costos_directos": {
                "material": costo_material_total,
                "energia": costo_energia_total,
                "desgaste": costo_desgaste_total,
                "mano_obra": mano_obra_total,
                "tipo_mo": tipo_mo
            },
            "factores": {
                "riesgo_mat": riesgo_material,
                "riesgo_mod": riesgo_modelo,
                "total_riesgo": factor_riesgo_total,
                "penalizacion_tiempo": factor_tiempo
            },
            "totales": {
                "costo_base": costo_base,
                "costo_tecnico": costo_tecnico
            },
            "precios": {
                "comercial": precios_comerciales,
                "productivo": pvp_productivo,
                "cama_llena": pvp_cama_llena,
                "socio": escenarios_socio
            }
        }

# --- INTERFAZ INTERACTIVA (CLI) ---

def leer_texto(mensaje):
    """Lee una entrada de texto no vacía."""
    while True:
        try:
            texto = input(f"{mensaje}: ").strip()
            if texto:
                return texto
            print("(!) El campo no puede estar vacío.")
        except EOFError:
            exit()

def leer_numero(mensaje, tipo=float):
    """Lee un número válido."""
    while True:
        try:
            val_str = input(f"{mensaje}: ").strip()
            if not val_str:
                print("(!) El campo no puede estar vacío.")
                continue
            valor = tipo(val_str)
            if valor < 0:
                print("(!) El valor debe ser positivo.")
                continue
            return valor
        except ValueError:
            print(f"(!) Por favor ingrese un número válido.")
        except EOFError:
            exit()

def seleccionar_opcion(titulo, opciones_dict):
    """Muestra un menú y devuelve la clave seleccionada."""
    print(f"\n--- {titulo} ---")
    keys = list(opciones_dict.keys())
    # Ordenar si es posible para consistencia
    try:
        keys.sort()
    except:
        pass
        
    for i, key in enumerate(keys, 1):
        val = opciones_dict[key]
        desc = val.get('nombre', val) if isinstance(val, dict) else val
        # Si la descripción es igual a la clave, no la mostramos redundante
        if str(desc) == str(key):
             print(f"{i}. {key}")
        else:
             print(f"{i}. {key} ({desc})")
    
    while True:
        try:
            sel_input = input(f"Seleccione una opción (1-{len(keys)}): ").strip()
            if not sel_input:
                continue
            sel = int(sel_input)
            if 1 <= sel <= len(keys):
                return keys[sel-1]
            print("(!) Opción fuera de rango.")
        except ValueError:
            print("(!) Ingrese el número de la opción.")
        except EOFError:
            exit()

def mostrar_reporte(res):
    """Imprime el reporte de cotización formateado."""
    t = res["totales"]
    c = res["costos_directos"]
    p = res["precios"]
    f = res["factores"]
    fis = res["resumen_fisico"]
    
    print(f"\n" + "="*50)
    print(f"      REPORTE DE COTIZACIÓN 3D      ")
    print(f"="*50)
    
    print(f"\n[DATOS FÍSICOS]")
    print(f" Tiempo Real:      {fis['tiempo_real_h']:.2f} h")
    print(f" Tiempo Efectivo:  {fis['tiempo_efectivo_h']:.2f} h (Base cálculo)")
    print(f" Peso Total:       {fis['peso_total_g']:.2f} g")
    print(f" Bandejas:         {fis['bandejas']} (Aplica MO: {c['tipo_mo']})")
    
    print(f"\n[COSTOS DIRECTOS]")
    print(f" Material:         ${c['material']:.2f}")
    print(f" Energía:          ${c['energia']:.2f}")
    print(f" Desgaste:         ${c['desgaste']:.2f}")
    print(f" Mano Obra:        ${c['mano_obra']:.2f}")
    print(f" -------------------------")
    print(f" COSTO BASE:       ${t['costo_base']:.2f}")
    
    print(f"\n[FACTORES Y RIESGOS]")
    print(f" Riesgo Mat/Mod:   x{f['total_riesgo']:.2f} (Mat {f['riesgo_mat']} * Mod {f['riesgo_mod']})")
    print(f" Penalización 24h: x{f['penalizacion_tiempo']:.1f}")
    print(f" -------------------------")
    print(f" COSTO TÉCNICO:    ${t['costo_tecnico']:.2f}")
    
    print(f"\n[PRECIOS SUGERIDOS]")
    print(f" > PRODUCTIVO (Meta):  ${p['productivo']:.2f}")
    print(f" > CAMA LLENA (Vol):   ${p['cama_llena']:.2f}")
    print(f" > COMERCIAL (35%):    ${p['comercial']['Promedio (35%)']:.2f}")
    
    print(f"\n[SOCIO COMERCIAL]")
    print(f" {'Nivel':<10} | {'PVP Cliente':<12} | {'Tu Pago':<10} | {'Local':<10}")
    print("-" * 50)
    for s in p['socio']:
        print(f" {s['Nivel']:<10} | ${s['PVP_Cliente']:<12.2f} | ${s['Tu_Pago']:<10.2f} | ${s['Pago_Local']:<10.2f}")
    print("="*50 + "\n")

def modo_interactivo():
    print("\n=== NUEVA COTIZACIÓN INTERACTIVA ===")
    
    # 1. Configuración Global
    es_nuevo_input = leer_texto("¿Es un modelo NUEVO? (s/n)").lower()
    es_nuevo = es_nuevo_input.startswith('s')
    
    urgencia_input = leer_texto("¿Operación urgente 24h? (s/n)").lower()
    operacion_24h = urgencia_input.startswith('s')
    
    bandejas = []
    
    while True:
        print(f"\n--- Agregando Bandeja #{len(bandejas)+1} ---")
        nombre = leer_texto("Nombre de la bandeja/pieza")
        
        # Selectores
        imp_key = seleccionar_opcion("Impresora", DB_IMPRESORAS)
        mat_key = seleccionar_opcion("Material", {k: k for k in RIESGO_MATERIAL.keys()})
        
        # Altura (Keys son floats, convertir a dict string para menu)
        print("\n--- Altura de Capa ---")
        alturas = sorted(FACTORES_ALTURA.keys())
        for i, h in enumerate(alturas, 1):
            print(f"{i}. {h} mm")
        idx_h = leer_numero(f"Seleccione opción (1-{len(alturas)})", int) - 1
        altura = alturas[idx_h] if 0 <= idx_h < len(alturas) else 0.20
        
        # Boquilla
        print("\n--- Boquilla ---")
        boquillas = sorted(FACTORES_BOQUILLA.keys())
        for i, b in enumerate(boquillas, 1):
            print(f"{i}. {b} mm")
        idx_b = leer_numero(f"Seleccione opción (1-{len(boquillas)})", int) - 1
        boquilla = boquillas[idx_b] if 0 <= idx_b < len(boquillas) else 0.4
        
        tiempo = leer_numero("Tiempo de impresión (horas)", float)
        peso = leer_numero("Peso del material (gramos)", float)
        piezas = leer_numero("Cantidad de piezas en esta bandeja", int)
        
        b = BandejaInput(nombre, imp_key, mat_key, tiempo, peso, altura, boquilla, piezas)
        bandejas.append(b)
        
        if leer_texto("¿Agregar otra bandeja? (s/n)").lower() != 's':
            break
            
    # Calcular
    cotizador = Cotizador3D()
    res = cotizador.calcular_proyecto(bandejas, es_nuevo, operacion_24h)
    mostrar_reporte(res)

def modo_validacion():
    print("=== VALIDACIÓN DE REGLAS DE NEGOCIO COTIZADOR 3D (v38) ===")
    
    # CASO DE PRUEBA:
    # Proyecto "Engranajes Industriales"
    # - Material: ABS (Técnico, Recargo energía, Riesgo 1.4)
    # - Modelo: Nuevo (Riesgo 1.3)
    # - 4 Bandejas (Aplica regla MO >= 3 -> $10 * 4 = $40)
    
    cotizador = Cotizador3D()
    
    bandejas_test = [
        BandejaInput("Engranajes A", "AD5X", "ABS", 2.5, 45.0, 0.20, 0.4, 2), # Altura 0.20 (x1.2), ABS (+30% Ener)
        BandejaInput("Engranajes B", "AD5X", "ABS", 2.5, 45.0, 0.20, 0.4, 2),
        BandejaInput("Soportes",     "A1_STD", "ABS", 1.0, 20.0, 0.28, 0.4, 4), # Altura 0.28 (x0.95)
        BandejaInput("Ejes",         "A1_MINI","ABS", 3.0, 30.0, 0.12, 0.4, 4)  # Altura 0.12 (x1.8 - Lento)
    ]
    
    res = cotizador.calcular_proyecto(bandejas_test, es_nuevo=True)
    mostrar_reporte(res)

# --- BLOQUE DE VALIDACIÓN (MAIN) ---
if __name__ == "__main__":
    while True:
        print("\n=== COTIZADOR 3D - MENÚ PRINCIPAL ===")
        print("1. Nueva Cotización (Interactivo)")
        print("2. Ejecutar Validación (Test de Reglas)")
        print("3. Salir")
        
        try:
            opcion = input("Seleccione una opción: ").strip()
        except EOFError:
            break
            
        if opcion == "1":
            modo_interactivo()
        elif opcion == "2":
            modo_validacion()
        elif opcion == "3":
            print("Hasta luego.")
            break
        else:
            print("Opción no válida.")
