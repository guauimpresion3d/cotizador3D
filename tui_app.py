#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Terminal UI "Hacker" - Cotizador 3D
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Button, Static, Input, Select, Label, DataTable, Switch
from textual.screen import Screen
from textual import work
from rich.text import Text
from rich.table import Table
from textual.coordinate import Coordinate

# Import the core logic decoupled previously
from core_logic import Cotizador3D, BandejaInput, DB_IMPRESORAS, RIESGO_MATERIAL, FACTORES_ALTURA, FACTORES_BOQUILLA
from db.config import SessionLocal
from db.repository import guardar_cotizacion

# CSS Hacker Style
CSS = """
Screen {
    background: #0a0a0a;
    color: #00ff00;
    align: center middle;
}

Header {
    background: #003300;
    color: #00ff00;
    text-style: bold;
}

Footer {
    background: #002200;
    color: #00cc00;
}

Button {
    background: #000000;
    color: #00ff00;
    border: solid #00ff00;
    margin: 1;
}

Button:hover {
    background: #00ff00;
    color: #000000;
}

Input {
    background: #000000;
    color: #00ff00;
    border: solid #006600;
}

Input:focus {
    border: solid #00ff00;
}

Select {
    background: #000000;
    color: #00ff00;
    border: solid #006600;
}

Label {
    color: #00cc00;
    margin-top: 1;
}

DataTable {
    background: #0a0a0a;
    color: #00ff00;
    border: solid #00ff00;
    margin-bottom: 1;
    height: auto;
    max-height: 15;
}

DataTable > .datatable--header {
    background: #003300;
    color: #00ff00;
    text-style: bold;
}

.title {
    content-align: center middle;
    text-style: bold;
    color: #00ff00;
    margin-bottom: 1;
}

.box {
    border: solid #00ff00;
    padding: 1 2;
    margin: 1;
    width: 95%;
    max-width: 130;
    height: auto;
    max-height: 95%;
}

.buttons_container {
    height: auto;
    align: center middle;
    margin-top: 1;
}

#lbl_bandejas {
    content-align: center middle;
    color: #00ffff;
    text-style: bold;
    margin-bottom: 1;
}

#switches_container {
    height: auto;
    margin: 0;
}

#switches_container > Vertical {
    align: center top;
    height: auto;
    margin: 0 1;
}

#switches_container Label {
    margin: 0;
    padding: 0;
}

#switches_container Switch {
    margin: 0;
}

#add_btn_container {
    height: 3;
    width: 100%;
    align: center middle;
}

#btn_add {
    width: 30;
    height: 3;
    text-style: bold;
}
"""

class DashboardScreen(Screen):
    """Main menu of the application."""
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="box"):
            yield Static("/// SISTEMA DE COTIZACION 3D - ACCESO CONCEDIDO ///", classes="title")
            with Vertical(id="btn_container"):
                yield Button("INICIAR NUEVA COTIZACION", id="btn_new", variant="success")
                yield Button("SALIR DEL SISTEMA", id="btn_exit", variant="error")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_new":
            self.app.push_screen("cotizacion")
        elif event.button.id == "btn_exit":
            self.app.exit()


class CotizacionScreen(Screen):
    """Screen to input tray data."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bandejas = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(classes="box"):
            yield Static(">>> INGRESE PARAMETROS DE LA BANDEJA <<<", classes="title")
            yield Label("BANDEJAS EN COLA: 0", id="lbl_bandejas")
            
            # --- Configuración Global (Movida Arriba) ---
            with Horizontal(id="switches_container"):
                with Vertical():
                    yield Label("¿Modelo Nuevo?")
                    yield Switch(id="sw_nuevo")
                with Vertical():
                    yield Label("¿Urgencia 24h?")
                    yield Switch(id="sw_urgencia")
                with Vertical():
                    yield Label("¿Cama Llena?")
                    yield Switch(id="sw_cama")
                with Vertical():
                    yield Label("¿Figuras a Armar? (Opcional)")
                    yield Input(placeholder="Auto", id="input_ensambladas")

            # --- Formulario de Bandeja ---
            yield Label("Nombre del Proyecto/Bandeja:")
            yield Input(placeholder="Ej: Engranajes ABS", id="input_nombre")
            
            yield Label("Impresora:")
            yield Select(
                [(data["nombre"], key) for key, data in DB_IMPRESORAS.items()],
                id="select_impresora"
            )
            
            yield Label("Material:")
            yield Select(
                [(mat, mat) for mat in RIESGO_MATERIAL.keys()],
                id="select_material"
            )
            
            yield Label("Altura de Capa (mm):")
            yield Select(
                [(str(h), h) for h in sorted(FACTORES_ALTURA.keys())],
                id="select_altura"
            )
            
            yield Label("Boquilla (mm):")
            yield Select(
                [(str(b), b) for b in sorted(FACTORES_BOQUILLA.keys())],
                id="select_boquilla"
            )
            
            yield Label("Tiempo (Horas - decimal, ej. 2.5 para 2h 30m):")
            yield Input(placeholder="0.0", id="input_tiempo")
            
            yield Label("Peso (Gramos):")
            yield Input(placeholder="0.0", id="input_peso")
            
            yield Label("Piezas:")
            yield Input(value="1", id="input_piezas")

            with Horizontal(id="add_btn_container", classes="buttons_container"):
                yield Button("AGREGAR BANDEJA", id="btn_add")

            # --- Visualización de Bandejas ---
            yield Label("\n>>> BANDEJAS EN COLA <<<")
            yield DataTable(id="table_queue")

            with Horizontal(classes="buttons_container"):
                yield Button("[>> CALCULAR TOTAL]", id="btn_calc", variant="primary")
                yield Button("[<< CANCELAR]", id="btn_cancel", variant="warning")
        yield Footer()

    def on_mount(self):
        # Configurar tabla de cola
        tq = self.query_one("#table_queue", DataTable)
        tq.add_columns("ID", "NOMBRE", "IMP", "MAT", "TIEMPO", "PESO", "PZAS")

    def on_screen_resume(self):
        self.bandejas = []
        self._update_counter()
        self._reset_inputs()

    def _update_counter(self):
        lbl = self.query_one("#lbl_bandejas", Label)
        lbl.update(f"BANDEJAS EN COLA: {len(self.bandejas)}")
        
        # Actualizar tabla
        tq = self.query_one("#table_queue", DataTable)
        tq.clear()
        for i, b in enumerate(self.bandejas, 1):
            tq.add_row(
                str(i),
                b.nombre,
                b.impresora_key,
                b.material,
                f"{b.tiempo_horas:.2f}h",
                f"{b.peso_gramos:.2f}g",
                str(b.piezas)
            )

    def _reset_inputs(self):
        self.query_one("#input_nombre", Input).value = ""
        self.query_one("#input_tiempo", Input).value = ""
        self.query_one("#input_peso", Input).value = ""
        self.query_one("#input_piezas", Input).value = "1"

    def _leer_bandeja_actual(self) -> BandejaInput:
        nombre = self.query_one("#input_nombre", Input).value or f"Bandeja {len(self.bandejas)+1}"
        imp = self.query_one("#select_impresora", Select).value or "A1_STD"
        mat = self.query_one("#select_material", Select).value or "PLA"
        alt = self.query_one("#select_altura", Select).value or 0.20
        boq = self.query_one("#select_boquilla", Select).value or 0.4
        tiempo = float(self.query_one("#input_tiempo", Input).value or 0)
        peso = float(self.query_one("#input_peso", Input).value or 0)
        piezas = int(self.query_one("#input_piezas", Input).value or 1)
        
        return BandejaInput(nombre, imp, mat, tiempo, peso, alt, boq, piezas)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.app.pop_screen()
        elif event.button.id == "btn_add":
            try:
                bandeja = self._leer_bandeja_actual()
                if bandeja.tiempo_horas > 0 and bandeja.peso_gramos > 0:
                    self.bandejas.append(bandeja)
                    self._update_counter()
                    self._reset_inputs()
                    self.app.notify(f"Bandeja '{bandeja.nombre}' agregada a la cola.", title="OK")
                else:
                    self.app.notify("El tiempo y peso deben ser mayores a 0", title="ALERTA", severity="warning")
            except Exception as e:
                self.app.notify(f"Error al leer datos: {e}", title="ERROR", severity="error")
        elif event.button.id == "btn_calc":
            self._calcular()
            
    def _calcular(self):
        try:
            bandeja_actual = self._leer_bandeja_actual()
            bandejas_a_calcular = list(self.bandejas)
            
            if bandeja_actual.tiempo_horas > 0 and bandeja_actual.peso_gramos > 0:
                bandejas_a_calcular.append(bandeja_actual)

            if not bandejas_a_calcular:
                self.app.notify("No hay bandejas para calcular.", title="ALERTA", severity="warning")
                return
            
            es_nuevo = self.query_one("#sw_nuevo", Switch).value
            es_urgente = self.query_one("#sw_urgencia", Switch).value
            es_cama = self.query_one("#sw_cama", Switch).value
            
            ensambladas_str = self.query_one("#input_ensambladas", Input).value
            figuras_ensambladas = None
            if ensambladas_str and ensambladas_str.isdigit():
                figuras_ensambladas = int(ensambladas_str)

            cotizador = Cotizador3D()
            resultados = cotizador.calcular_proyecto(
                bandejas_a_calcular, 
                es_nuevo=es_nuevo, 
                operacion_24h=es_urgente,
                es_cama_llena=es_cama,
                figuras_ensambladas=figuras_ensambladas
            )
            
            context_data = {
                "es_nuevo": es_nuevo,
                "operacion_24h": es_urgente,
                "es_cama_llena": es_cama,
                "figuras_ensambladas": figuras_ensambladas,
                "bandejas_input": bandejas_a_calcular
            }
            
            self.app.push_screen(ReporteScreen(resultados=resultados, context_data=context_data))
            
        except Exception as e:
            self.app.notify(f"ERROR I/O: {str(e)}", title="SYSTEM FAULT", severity="error")


class ReporteScreen(Screen):
    """Screen to display calculation results in styled tables."""
    def __init__(self, resultados: dict, context_data: dict = None, **kwargs):
        super().__init__(**kwargs)
        self.resultados = resultados
        self.context_data = context_data

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(classes="box"):
            yield Static("/// RESULTADOS DE COMPUTO ///", classes="title")
            
            yield Label(">>> TABLA DE COSTOS DIRECTOS <<<")
            yield DataTable(id="table_costos")
            
            yield Label("\n>>> MODO COMERCIAL (Márgenes) <<<")
            yield DataTable(id="table_comercial")
            
            yield Label("\n>>> MODO PRODUCTIVO (Capacidad) <<<")
            yield DataTable(id="table_productivo")
            
            if self.resultados["precios"].get("cama_llena") is not None:
                yield Label("\n>>> MODO CAMA LLENA (Volumen) <<<")
                yield DataTable(id="table_cama_llena")
            
            yield Label("\n>>> ESCENARIOS SOCIO COMERCIAL <<<")
            yield DataTable(id="table_socios")

            yield Label("\n>>> DESGLOSE DE CALCULOS (Auditoría) <<<")
            yield DataTable(id="table_audit")

            with Horizontal(classes="buttons_container"):
                yield Button("<< REGRESAR", id="btn_back", variant="warning")
                yield Button("GUARDAR EN BD", id="btn_save", variant="success")
        yield Footer()

    def on_mount(self):
        # Configurar tablas
        tc = self.query_one("#table_costos", DataTable)
        tc.add_columns("CONCEPTO", "VALOR (MXN)")
        
        tcm = self.query_one("#table_comercial", DataTable)
        tcm.add_columns("MARGEN", "PRECIO TOTAL", "UNITARIO", "UTILIDAD", "UTIL. UNIT")
        
        tp = self.query_one("#table_productivo", DataTable)
        tp.add_columns("CONCEPTO", "PRECIO TOTAL", "UNITARIO", "UTILIDAD", "UTIL. UNIT")
        
        if self.resultados["precios"].get("cama_llena") is not None:
            tcl = self.query_one("#table_cama_llena", DataTable)
            tcl.add_columns("CONCEPTO", "PRECIO TOTAL", "UNITARIO", "UTILIDAD", "UTIL. UNIT")
        
        ts = self.query_one("#table_socios", DataTable)
        ts.add_columns("NIVEL", "UTILIDAD %", "PVP CLIENTE", "TU PAGO (NETO)", "TU UTILIDAD", "PAGO LOCAL", "UTIL. SOCIO")
        
        ta = self.query_one("#table_audit", DataTable)
        ta.add_columns("BANDEJA", "CONCEPTO", "FÓRMULA / DESGLOSE")

        self._cargar_datos()

    def _cargar_datos(self):
        if not hasattr(self, "resultados"):
            return
            
        res = self.resultados
        pzas = res["resumen_fisico"]["piezas"]
        
        # 1. Costos Directos
        tc = self.query_one("#table_costos", DataTable)
        tc.clear()
        c = res["costos_directos"]
        t = res["totales"]
        tc.add_row("Material", f"${c['material']:.2f}")
        tc.add_row("Energía", f"${c['energia']:.2f}")
        tc.add_row("Desgaste", f"${c['desgaste']:.2f}")
        tc.add_row("Mano Obra", f"${c['mano_obra']:.2f} ({c['tipo_mo']})")
        tc.add_row("COSTO BASE", f"${t['costo_base']:.2f}")
        tc.add_row("COSTO TÉCNICO", f"${t['costo_tecnico']:.2f}")
        
        # 2. Modo Comercial
        tcm = self.query_one("#table_comercial", DataTable)
        tcm.clear()
        p = res["precios"]
        for k, v in p["comercial"].items():
            pvp = v["pvp"]
            uti = v["utilidad"]
            tcm.add_row(k, f"${pvp:.2f}", f"${(pvp/pzas):.2f}", f"${uti:.2f}", f"${(uti/pzas):.2f}")
        
        # 3. Modo Productivo
        tp = self.query_one("#table_productivo", DataTable)
        tp.clear()
        vp = p["productivo"]["pvp"]
        vu = p["productivo"]["utilidad"]
        tp.add_row("Meta de Utilidad", f"${vp:.2f}", f"${(vp/pzas):.2f}", f"${vu:.2f}", f"${(vu/pzas):.2f}")
        
        # 4. Cama Llena
        if p.get("cama_llena") is not None:
            tcl = self.query_one("#table_cama_llena", DataTable)
            tcl.clear()
            vcl = p["cama_llena"]["pvp"]
            vul = p["cama_llena"]["utilidad"]
            tcl.add_row("Volumen Masivo", f"${vcl:.2f}", f"${(vcl/pzas):.2f}", f"${vul:.2f}", f"${(vul/pzas):.2f}")
        
        # 5. Socios
        ts = self.query_one("#table_socios", DataTable)
        ts.clear()
        for s in p["socio"]:
            tu_utilidad = s['Tu_Pago'] - t['costo_tecnico']
            ts.add_row(
                s["Nivel"], 
                f"{s['Utilidad_%']}%", 
                f"${s['PVP_Cliente']:.2f}", 
                f"${s['Tu_Pago']:.2f}", 
                f"${tu_utilidad:.2f}",
                f"${s['Pago_Local']:.2f}",
                f"${s['Utilidad_Socio']:.2f}"
            )

        # 6. Auditoría (Fórmulas)
        ta = self.query_one("#table_audit", DataTable)
        ta.clear()
        for item in res.get("auditoria", []):
            nombre = item["nombre"]
            d = item["detalles"]
            ta.add_row(nombre, "Tiempo Efec.", d["formula_tiempo"])
            ta.add_row(nombre, "Energía", d["formula_energia"])
            ta.add_row(nombre, "Desgaste", d["formula_desgaste"])
            ta.add_row(nombre, "Material", d["formula_material"])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_back":
            self.app.pop_screen()
        elif event.button.id == "btn_save":
            try:
                if not self.context_data:
                    self.app.notify("No hay datos de contexto para guardar.", title="ERROR", severity="error")
                    return
                
                nombre_proyecto = self.context_data["bandejas_input"][0].nombre if self.context_data["bandejas_input"] else "Proyecto_Desconocido"
                
                db = SessionLocal()
                try:
                    guardar_cotizacion(
                        db=db,
                        nombre_proyecto=nombre_proyecto,
                        resultados=self.resultados,
                        es_nuevo=self.context_data["es_nuevo"],
                        operacion_24h=self.context_data["operacion_24h"],
                        es_cama_llena=self.context_data["es_cama_llena"],
                        figuras_ensambladas=self.context_data["figuras_ensambladas"],
                        bandejas_input=self.context_data["bandejas_input"]
                    )
                    self.app.notify("Cotización guardada exitosamente en BD", title="ÉXITO")
                    # Disable button to prevent double saving
                    self.query_one("#btn_save", Button).disabled = True
                except Exception as db_e:
                    db.rollback()
                    self.app.notify(f"Error BD: {str(db_e)}", title="ERROR", severity="error")
                finally:
                    db.close()
            except Exception as e:
                self.app.notify(f"Error al procesar: {str(e)}", title="ERROR", severity="error")


class CotizadorApp(App):
    """Main textual application."""
    CSS = CSS
    SCREENS = {
        "dashboard": DashboardScreen,
        "cotizacion": CotizacionScreen,
    }
    
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit app")
    ]

    def on_mount(self) -> None:
        self.push_screen("dashboard")


if __name__ == "__main__":
    app = CotizadorApp()
    app.run()
