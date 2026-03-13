#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Lógico - Cotizador 3D v38 (2026)
--------------------------------------------------------------------------------
Este módulo implementa las reglas definidas en NEGOCIO.MD (Actualizado 2026).
No contiene lógica de presentación (I/O de terminal).
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
        
        f_alt = self.obtener_factor_altura(bandeja.altura_capa)
        f_boq = self.obtener_factor_boquilla(bandeja.boquilla)
        t_efectivo = self.calcular_tiempo_efectivo(bandeja.tiempo_horas, f_alt, f_boq)
        
        tarifa_energia = TARIFA_ENERGIA_BASE_KWH
        if self.es_material_tecnico(bandeja.material):
            tarifa_energia *= 1.3
            
        consumo_kw = DB_IMPRESORAS.get(bandeja.impresora_key, DB_IMPRESORAS["A1_STD"])["kw"]
        costo_energia_h = consumo_kw * tarifa_energia
        costo_energia_total = t_efectivo * costo_energia_h
        
        costo_desgaste_base = DESGASTE_MAQUINA_HORA * f_alt * f_boq
        costo_desgaste_total = t_efectivo * costo_desgaste_base
        
        costo_material = bandeja.peso_gramos * COSTO_MATERIAL_MXN_GR
        
        return {
            "tiempo_efectivo": t_efectivo,
            "costo_energia": costo_energia_total,
            "costo_desgaste": costo_desgaste_total,
            "costo_material": costo_material,
            "f_altura": f_alt,
            "f_boquilla": f_boq,
            "es_tecnico": self.es_material_tecnico(bandeja.material),
            "audit": {
                "formula_tiempo": f"{bandeja.tiempo_horas}h * {f_alt} (alt) * {f_boq} (boq)",
                "formula_energia": f"{t_efectivo:.2f}h * {consumo_kw}kW * ${tarifa_energia:.2f}",
                "formula_desgaste": f"{t_efectivo:.2f}h * (${DESGASTE_MAQUINA_HORA} * {f_alt} * {f_boq})",
                "formula_material": f"{bandeja.peso_gramos}g * ${COSTO_MATERIAL_MXN_GR}"
            }
        }

    def calcular_proyecto(self, bandejas: List[BandejaInput], es_nuevo: bool = False, operacion_24h: bool = False, es_cama_llena: bool = False, figuras_ensambladas: int = None):
        """Calcula el proyecto completo aplicando reglas globales."""
        
        costo_material_total = 0.0
        costo_energia_total = 0.0
        costo_desgaste_total = 0.0
        tiempo_efectivo_total = 0.0
        tiempo_real_total = 0.0
        
        if figuras_ensambladas and figuras_ensambladas > 0:
            piezas_total = figuras_ensambladas
        else:
            piezas_total = sum(b.piezas for b in bandejas)
        
        detalle_bandejas = []
        audit_global = []
        
        for b in bandejas:
            res = self.calcular_costo_bandeja(b)
            costo_material_total += res["costo_material"]
            costo_energia_total += res["costo_energia"]
            costo_desgaste_total += res["costo_desgaste"]
            tiempo_efectivo_total += res["tiempo_efectivo"]
            tiempo_real_total += b.tiempo_horas
            detalle_bandejas.append(res)
            
            # Audit por bandeja
            audit_global.append({
                "nombre": b.nombre,
                "piezas": b.piezas,
                "detalles": res["audit"]
            })
            
        num_bandejas = len(bandejas)
        if num_bandejas >= 3:
            mano_obra_total = num_bandejas * MANO_OBRA_MULTIBANDEJA
            tipo_mo = f"Multibandeja ({num_bandejas} x ${MANO_OBRA_MULTIBANDEJA})"
        else:
            mano_obra_total = MANO_OBRA_ESTANDAR
            tipo_mo = f"Estándar (Fija ${MANO_OBRA_ESTANDAR})"
            
        costo_base = costo_material_total + costo_energia_total + costo_desgaste_total + mano_obra_total
        
        riesgos_m = [RIESGO_MATERIAL.get(b.material, 1.0) for b in bandejas]
        riesgo_material = max(riesgos_m) if riesgos_m else 1.0
        
        riesgo_modelo = RIESGO_MODELO["NUEVO"] if es_nuevo else RIESGO_MODELO["PROBADO"]
        factor_riesgo_total = riesgo_material * riesgo_modelo
        
        factor_tiempo = 1.5 if (tiempo_real_total >= 24 or operacion_24h) else 1.0
        
        costo_tecnico = (costo_base * factor_riesgo_total) * factor_tiempo
        
        precios_comerciales = {}
        for margen in [20, 30, 40, 50]:
            pvp = costo_tecnico * (1 + margen/100)
            precios_comerciales[f"{margen}%"] = {"pvp": pvp, "utilidad": pvp - costo_tecnico}
        pvp_prom = costo_tecnico * 1.35
        precios_comerciales["Promedio (35%)"] = {"pvp": pvp_prom, "utilidad": pvp_prom - costo_tecnico}
        
        pvp_productivo = costo_tecnico + (tiempo_efectivo_total * COSTO_HORA_PRODUCTIVO)
        obj_productivo = {"pvp": pvp_productivo, "utilidad": pvp_productivo - costo_tecnico}
        
        # MODO CAMA LLENA (Solo si se solicita)
        obj_cama_llena = None
        if es_cama_llena:
            mo_cama_llena = MANO_OBRA_ESTANDAR
            costo_base_cama = costo_material_total + costo_energia_total + costo_desgaste_total + mo_cama_llena
            costo_tecnico_cama = (costo_base_cama * factor_riesgo_total) * factor_tiempo
            pvp_cama_llena = costo_tecnico_cama * 1.25
            obj_cama_llena = {"pvp": pvp_cama_llena, "utilidad": pvp_cama_llena - costo_tecnico_cama}
        
        fee_exhibicion = costo_tecnico * 0.05
        escenarios_socio = []
        for nivel, pct in [("Básico", 0.50), ("Estándar", 1.00), ("Premium", 1.50), ("Exclusivo", 2.00)]:
            utilidad_bruta = costo_tecnico * pct
            utilidad_mitad = utilidad_bruta * 0.50
            pvp_final = costo_tecnico + fee_exhibicion + utilidad_bruta
            reparto_productor = costo_tecnico + utilidad_mitad
            reparto_local = fee_exhibicion + utilidad_mitad
            
            escenarios_socio.append({
                "Nivel": nivel,
                "Utilidad_%": int(pct*100),
                "PVP_Cliente": pvp_final,
                "Tu_Pago": reparto_productor,
                "Pago_Local": reparto_local,
                "Utilidad_Socio": utilidad_mitad
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
                "productivo": obj_productivo,
                "cama_llena": obj_cama_llena,
                "socio": escenarios_socio
            },
            "auditoria": audit_global
            }