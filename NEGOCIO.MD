# Reglas de Negocio y Factores de Cálculo - Cotizador 3D v38 (Actualizado 2026)

Este documento detalla la lógica financiera y técnica oficial, alineada con las políticas de amortización y energía de 2026.

## 1. Constantes de Costos Directos (Moneda: MXN)
Valores base para la operación. **Nota:** Toda la contabilidad se maneja en Pesos Mexicanos.

| Factor | Valor Exacto | Unidad |
| :--- | :--- | :--- |
| **Costo Material** | 0.35 | MXN / gramo |
| **Tarifa Energía Base** | 8.00 | MXN / kWh (Tarifa DAC Segura) |
| **Desgaste Máquina** | 4.00 | MXN / hora (Unificado) |
| **Mano de Obra (1-2 bandejas)** | 30.00 | MXN (Fijo por pedido) |
| **Mano de Obra (≥ 3 bandejas)** | 10.00 | MXN (Por cada bandeja) |

## 2. Parámetros de Infraestructura
- **Número de impresoras:** 3 (Bambu Lab A1, A1 Mini, Flash Forge AD5X)
- **Horas de trabajo por día:** 12 h (Capacidad estándar)
- **Meta de utilidad diaria:** $350.00 MXN **por impresora** ($1,050.00 MXN total)

### Consumo Eléctrico y Costo por Hora (Material: PLA/PETG)
| Modelo | Consumo (kW) | Costo Energía/Hora |
| :--- | :--- | :--- |
| `A1_MINI` | 0.06 | $0.48 MXN |
| `A1_STD` | 0.11 | $0.88 MXN |
| `AD5X` | 0.13 | $1.04 MXN |

## 3. Factores de Ajuste Técnico (Tiempo Efectivo)
Se calcula el **Tiempo Efectivo** para reflejar el esfuerzo real de la máquina.

### Factores por Altura de Capa
| Altura (mm) | Factor |
| :--- | :--- |
| 0.32 | 0.85 |
| 0.28 | 0.95 |
| 0.24 | 1.00 |
| 0.20 | 1.20 |
| 0.16 | 1.45 |
| 0.12 | 1.80 |

### Factores por Diámetro de Boquilla (Nozzle)
| Boquilla (mm) | Factor |
| :--- | :--- |
| 0.6 | 0.9 |
| 0.4 | 1.0 |
| 0.2 | 1.5 |

## 4. Gestión de Riesgos y Penalizaciones

### Factores de Riesgo por Material
- `PLA`: 1.0 | `PLA+`: 1.1 | `PETG`: 1.2 | `ABS / ASA`: 1.4 | `TPU`: 1.5 | `NYLON`: 1.7

### Factores de Riesgo por Modelo
- `PROBADO`: 1.15
- `NUEVO`: 1.30

### Penalización por Operación 24h
- Si el proyecto requiere funcionamiento de 24 horas (Continuo/Urgente): **x1.5** al precio final.

## 5. Fórmulas de Cálculo Core

1. **Tiempo Efectivo:** `TIEMPO_EFECTIVO = HORAS_BASE × FACTOR_ALTURA × FACTOR_BOQUILLA`
2. **Costo Máquina:** `COSTO_MAQUINA = TIEMPO_EFECTIVO × (COSTO_ENERGIA_H + (DESGASTE_H × FACTOR_ALTURA × FACTOR_BOQUILLA))`
3. **Costo Técnico (Con Riesgo):** `COSTO_RIESGO = (COSTO_MAQUINA + COSTO_MATERIAL + MANO_OBRA) × FACTOR_RIESGO_TOTAL`

## 6. Modos de Cotización

### A. Modo Comercial (Márgenes)
- Se presentan opciones con márgenes de: **20%, 30%, 40% y 50%**.
- Se incluye un **Promedio (35%)** como referencia sugerida.

### B. Modo Productivo (Capacidad)
- **Utilidad por Hora:** `$1,050.00 / (3 impresoras * 12 horas) = $29.166 MXN / h`.
- **Fórmula:** `PVP = COSTO_RIESGO + (TIEMPO_EFECTIVO * $29.166)`.

### C. Modo "Cama Llena" (Volumen)
- **Mano de Obra:** Se cobra una única cuota de **$30.00 MXN** por toda la placa (no por pieza).
- **Margen Comercial:** Se reduce a un fijo de **20% o 25%** para incentivar el volumen.

### D. Socio Comercial (Reparto Transparente)
- **Gasto de Exhibición (Fee):** 5% sobre el Costo Operativo.
- **Niveles de Utilidad Bruta:**
  - Básico (50%): Alta rotación.
  - Estándar (100%): Decorativos.
  - Premium (150%): Impresiones largas (>5h).
  - Exclusivo (200%): Diseños de autor.
- **Reparto:**
  - **Productor:** Recupera Costo Operativo + 50% de la Utilidad Bruta.
  - **Local:** Recibe Fee de Exhibición + 50% de la Utilidad Bruta.

## 7. Recargos Energéticos Especiales
Para materiales que requieran cama caliente >70°C (**ABS, ASA, NYLON**), el costo de energía calculado por hora se incrementa en un **30%** (Factor 1.3).
