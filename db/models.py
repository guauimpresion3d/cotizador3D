from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from db.config import Base

class ProyectoCotizacion(Base):
    __tablename__ = "proyectos_cotizacion"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    
    # Parametros Globales
    es_nuevo = Column(Boolean, default=False)
    operacion_24h = Column(Boolean, default=False)
    es_cama_llena = Column(Boolean, default=False)
    figuras_ensambladas_total = Column(Integer, nullable=True)

    # Resultados Físicos
    peso_total_g = Column(Float)
    tiempo_real_h = Column(Float)
    tiempo_efectivo_h = Column(Float)
    piezas_total = Column(Integer)
    num_bandejas = Column(Integer)

    # Costos Directos
    costo_material = Column(Float)
    costo_energia = Column(Float)
    costo_desgaste = Column(Float)
    costo_mano_obra = Column(Float)
    costo_base_operativo = Column(Float)

    # Factores de Riesgo (Auditables)
    factor_riesgo_material = Column(Float)
    factor_riesgo_modelo = Column(Float)
    factor_riesgo_total = Column(Float)
    factor_penalizacion_tiempo = Column(Float)
    costo_tecnico_final = Column(Float)

    # Precios Sugeridos
    pvp_comercial_promedio = Column(Float)
    pvp_productivo = Column(Float)
    pvp_cama_llena = Column(Float, nullable=True) # Solo si aplica

    # Relacion
    bandejas = relationship("BandejaDetalle", back_populates="proyecto")

class BandejaDetalle(Base):
    __tablename__ = "bandejas_detalle"

    id = Column(Integer, primary_key=True, index=True)
    proyecto_id = Column(Integer, ForeignKey("proyectos_cotizacion.id"))
    
    nombre = Column(String)
    impresora_key = Column(String)
    material = Column(String)
    tiempo_horas = Column(Float)
    peso_gramos = Column(Float)
    altura_capa = Column(Float)
    boquilla = Column(Float)
    piezas = Column(Integer)

    # Resultados calculados de la bandeja
    tiempo_efectivo = Column(Float)
    costo_energia = Column(Float)
    costo_desgaste = Column(Float)
    costo_material = Column(Float)
    factor_altura = Column(Float)
    factor_boquilla = Column(Float)
    es_material_tecnico = Column(Boolean)

    # Auditoría: Fórmulas aplicadas
    formula_tiempo = Column(String, nullable=True)
    formula_energia = Column(String, nullable=True)
    formula_desgaste = Column(String, nullable=True)
    formula_material = Column(String, nullable=True)

    # Relacion
    proyecto = relationship("ProyectoCotizacion", back_populates="bandejas")
