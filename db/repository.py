from sqlalchemy.orm import Session
from core_logic import BandejaInput
from db.models import ProyectoCotizacion, BandejaDetalle

def guardar_cotizacion(db: Session, nombre_proyecto: str, resultados: dict, es_nuevo: bool, operacion_24h: bool, es_cama_llena: bool, es_pieza_unica: bool, bandejas_input: list[BandejaInput]):
    """
    Persiste una cotización y sus bandejas en la base de datos.
    """
    
    # 1. Extraer datos del resultado
    fis = resultados["resumen_fisico"]
    c = resultados["costos_directos"]
    f = resultados["factores"]
    t = resultados["totales"]
    p = resultados["precios"]

    # 2. Crear cabecera (Proyecto)
    proyecto = ProyectoCotizacion(
        nombre=nombre_proyecto,
        es_nuevo=es_nuevo,
        operacion_24h=operacion_24h,
        es_cama_llena=es_cama_llena,
        es_pieza_unica=es_pieza_unica,
        
        peso_total_g=fis["peso_total_g"],
        tiempo_real_h=fis["tiempo_real_h"],
        tiempo_efectivo_h=fis["tiempo_efectivo_h"],
        piezas_total=fis["piezas"],
        num_bandejas=fis["bandejas"],
        
        costo_material=c["material"],
        costo_energia=c["energia"],
        costo_desgaste=c["desgaste"],
        costo_mano_obra=c["mano_obra"],
        costo_base_operativo=t["costo_base"],
        
        factor_riesgo_material=f["riesgo_mat"],
        factor_riesgo_modelo=f["riesgo_mod"],
        factor_riesgo_total=f["total_riesgo"],
        factor_penalizacion_tiempo=f["penalizacion_tiempo"],
        costo_tecnico_final=t["costo_tecnico"],
        
        pvp_comercial_promedio=p["comercial"]["Promedio (35%)"]["pvp"],
        pvp_productivo=p["productivo"]["pvp"],
        pvp_cama_llena=p["cama_llena"]["pvp"] if p.get("cama_llena") else None
    )
    
    db.add(proyecto)
    db.flush() # Para obtener el ID del proyecto sin hacer commit todavía

    # 3. Crear detalle (Bandejas)
    for index, bandeja_in in enumerate(bandejas_input):
        # Intentamos obtener el resultado calculado específico si fuera necesario,
        # pero BandejaInput ya tiene los inputs y el dict de resultados no lo devuelve por bandeja en este formato básico, 
        # así que guardamos lo que tenemos o recalculamos lo básico si hiciera falta.
        # Por simplicidad, guardamos los inputs.
        detalle = BandejaDetalle(
            proyecto_id=proyecto.id,
            nombre=bandeja_in.nombre,
            impresora_key=bandeja_in.impresora_key,
            material=bandeja_in.material,
            tiempo_horas=bandeja_in.tiempo_horas,
            peso_gramos=bandeja_in.peso_gramos,
            altura_capa=bandeja_in.altura_capa,
            boquilla=bandeja_in.boquilla,
            piezas=bandeja_in.piezas
        )
        db.add(detalle)
        
    db.commit()
    db.refresh(proyecto)
    return proyecto
