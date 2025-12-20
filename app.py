import streamlit as st
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import time
import io

# ==============================================================================
# 1. CONFIGURACIÓN ESTRUCTURAL Y VISUAL
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro IA", page_icon="📊", layout="wide")

# Estilos CSS Profesionales (Integrando tu diseño visual)
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button {
        background-color: #0d6efd; color: white; border-radius: 8px; 
        font-weight: bold; width: 100%; padding: 10px; border: none;
    }
    .stButton>button:hover { background-color: #0b5ed7; }
    /* Cajas de alerta personalizadas para Auditoría IA */
    .alerta-roja { color: #842029; background-color: #f8d7da; padding: 15px; border-radius: 5px; border-left: 5px solid #dc3545;}
    .alerta-verde { color: #0f5132; background-color: #d1e7dd; padding: 15px; border-radius: 5px; border-left: 5px solid #198754;}
    .metric-card { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. GESTIÓN DE ESTADO Y DATOS (DATABASE SIMULADA)
# ==============================================================================
if 'historial_pagos' not in st.session_state:
    st.session_state.historial_pagos = pd.DataFrame({
        'nit': ['900123456', '88222333', '1098765432'],
        'nombre': ['Suministros SAS', 'Pedro Pintor (Régimen Simple)', 'María Contadora'],
        'acumulado_mes': [0.0, 3500000.0, 150000.0],
        'responsable_iva': [True, False, False]
    })

# Constantes Fiscales 2025
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025
BASE_RETENCION = 4 * UVT_2025

# ==============================================================================
# 3. LÓGICA DEL CEREBRO (FUNCIONES)
# ==============================================================================

# --- A. Lógica de Reglas (Matemática Pura - Lo que ya teníamos) ---
def auditar_reglas_negocio(nit, valor, metodo_pago):
    alertas = []
    bloqueo = False
    
    # 1. Bancarización
    if metodo_pago == 'Efectivo' and valor > TOPE_EFECTIVO:
        alertas.append(f"🔴 **RIESGO FISCAL (Art. 771-5):** Pago en efectivo supera tope individual ({TOPE_EFECTIVO:,.0f}).")
        bloqueo = True
        
    # 2. Retenciones
    tercero = st.session_state.historial_pagos[st.session_state.historial_pagos['nit'] == nit]
    if not tercero.empty:
        acumulado = tercero['acumulado_mes'].values[0]
        if acumulado < BASE_RETENCION and (acumulado + valor) >= BASE_RETENCION:
            alertas.append(f"🔔 **RETENCIÓN:** El acumulado mensual supera la base. Practicar Retención.")
            
    return alertas, bloqueo

def auditar_nomina_ugpp(salario, no_salariales):
    total = salario + no_salariales
    limite_40 = total * 0.40
    if no_salariales > limite_40:
        exceso = no_salariales - limite_40
        return salario + exceso, exceso, "⚠️ EXCESO 40%", "Riesgo"
    return salario, 0, "✅ OK", "Seguro"

# --- B. Lógica de IA (Gemini - Lo Nuevo) ---
def consultar_ia_dian(concepto, valor):
    """Consulta normativa conceptual a Gemini"""
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = f"""
        Actúa como Auditor Tributario en Colombia. Analiza: Gasto="{concepto}", Valor=${valor}.
        Responde SOLO JSON: {{"riesgo": "ALTO/MEDIO/BAJO", "razon": "Explicación corta", "cuenta_puc": "Código sugerido"}}
        """
        response = model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return {"riesgo": "Error", "razon": "Fallo de conexión IA", "cuenta_puc": "N/A"}

def procesar_factura_imagen(image):
    """OCR Inteligente para facturas"""
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = """
        Extrae datos de esta factura en JSON estricto:
        {"fecha": "YYYY-MM-DD", "nit": "sin digito verificacion", "proveedor": "nombre", "concepto": "resumen", "base": numero, "iva": numero, "total": numero}
        Si no es visible pon 0 o null.
        """
        response = model.generate_content([prompt, image])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return None

# ==============================================================================
# 4. INTERFAZ DE USUARIO (SIDEBAR)
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=60)
    st.title("Panel Contador")
    
    # --- CONFIGURACIÓN DE IA ---
    st.markdown("### 🔑 Llave Maestra (Google AI)")
    api_key = st.text_input("API Key", type="password", help="Pega aquí tu API Key de Google AI Studio")
    if api_key:
        genai.configure(api_key=api_key)
        st.success("🟢 IA Conectada")
    else:
        st.warning("🔴 IA Desconectada")
        
    st.markdown("---")
    menu = st.radio("Herramientas:", 
                    ["📸 Digitación IA", 
                     "🛡️ Auditoría Integral", 
                     "👥 Nómina UGPP"])

# ==============================================================================
# 5. PANTALLAS PRINCIPALES
# ==============================================================================

# --- MÓDULO 1: DIGITACIÓN INTELIGENTE (NUEVO) ---
if menu == "📸 Digitación IA":
    st.header("📸 De Papel a Excel (OCR Inteligente)")
    st.markdown("Sube fotos de facturas físicas. La IA extraerá los datos para importar a tu software.")
    
    archivos = st.file_uploader("Cargar Facturas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if archivos and st.button("🚀 Procesar Imágenes"):
        if not api_key:
            st.error("⚠️ Necesitas la API Key para usar visión artificial.")
        else:
            resultados = []
            barra = st.progress(0)
            
            for i, archivo in enumerate(archivos):
                barra.progress((i + 1) / len(archivos))
                img = Image.open(archivo)
                datos = procesar_factura_imagen(img)
                if datos:
                    datos['Archivo'] = archivo.name
                    resultados.append(datos)
                time.sleep(1) # Evitar saturar API
            
            if resultados:
                df_facturas = pd.DataFrame(resultados)
                # Reordenar columnas
                cols = ['fecha', 'nit', 'proveedor', 'concepto', 'base', 'iva', 'total', 'Archivo']
                df_facturas = df_facturas[[c for c in cols if c in df_facturas.columns]]
                
                st.success("✅ Procesamiento terminado")
                st.data_editor(df_facturas, use_container_width=True)
                
                # Descarga Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_facturas.to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel", output.getvalue(), "facturas_ia.xlsx")

# --- MÓDULO 2: AUDITORÍA INTEGRAL (FUSIÓN REGLAS + IA) ---
elif menu == "🛡️ Auditoría Integral":
    st.header("🛡️ Centro de Fiscalización")
    
    tab_reglas, tab_ia, tab_masiva = st.tabs(["⚡ Validación Técnica (Reglas)", "🧠 Consultor DIAN (IA)", "📂 Auditoría Masiva"])
    
    # 2.1 Pestaña Reglas (Lo clásico)
    with tab_reglas:
        st.subheader("Validación de Requisitos Formales")
        c1, c2 = st.columns(2)
        nit = c1.selectbox("Tercero", st.session_state.historial_pagos['nit'])
        valor = c2.number_input("Valor Pago", step=100000)
        metodo = c1.selectbox("Método", ["Transferencia", "Efectivo", "Cheque"])
        
        if st.button("Verificar Reglas"):
            alertas, bloqueo = auditar_reglas_negocio(nit, valor, metodo)
            if not alertas: st.success("✅ Operación Limpia (Formalmente)")
            for a in alertas: 
                if "🔴" in a: st.error(a)
                else: st.warning(a)

    # 2.2 Pestaña IA (Lo nuevo conceptual)
    with tab_ia:
        st.subheader("Análisis de Deducibilidad (IA)")
        st.info("Pregunta sobre gastos complejos. Ej: 'Almuerzo con clientes', 'Ropa para empleados'.")
        consulta = st.text_input("Concepto del gasto:")
        val_consulta = st.number_input("Valor del gasto:", value=0)
        
        if st.button("Consultar a Gemini"):
            if not api_key:
                st.error("Requiere API Key")
            else:
                with st.spinner("Analizando Estatuto Tributario..."):
                    res = consultar_ia_dian(consulta, val_consulta)
                    
                    if "ALTO" in res['riesgo'].upper():
                        st.markdown(f"<div class='alerta-roja'>🚨 <b>RIESGO ALTO:</b> {res['riesgo']}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='alerta-verde'>✅ <b>CONCEPTO FAVORABLE:</b> {res['riesgo']}</div>", unsafe_allow_html=True)
                    
                    st.write(f"**Argumento:** {res['razon']}")
                    st.write(f"**PUC Sugerido:** {res['cuenta_puc']}")

    # 2.3 Pestaña Masiva (Fusión de ambas lógicas)
    with tab_masiva:
        st.subheader("Auditoría de Auxiliares en Excel")
        uploaded = st.file_uploader("Subir Excel (.xlsx)", type=['xlsx'])
        
        if uploaded and api_key:
            if st.button("🔍 Auditar Archivo Completo"):
                df = pd.read_excel(uploaded)
                st.info("Analizando primeras 5 filas para demostración...")
                
                hallazgos = []
                barra = st.progress(0)
                
                # Ejemplo de barrido híbrido
                for idx, row in df.head(5).iterrows():
                    barra.progress((idx+1)/5)
                    # 1. Chequeo IA
                    concepto = str(row.get('Concepto', 'Varios'))
                    valor = float(row.get('Valor', 0))
                    res_ia = consultar_ia_dian(concepto, valor)
                    
                    hallazgos.append({
                        "Fila": idx+1,
                        "Concepto": concepto,
                        "Valor": valor,
                        "Opinión IA": res_ia['riesgo'],
                        "Justificación": res_ia['razon']
                    })
                
                res_df = pd.DataFrame(hallazgos)
                
                def color_riesgo(val):
                    return 'background-color: #ffcccc' if 'ALTO' in str(val) else 'background-color: #ccffcc'
                
                st.dataframe(res_df.style.applymap(color_riesgo, subset=['Opinión IA']))

# --- MÓDULO 3: NÓMINA (UGPP) ---
elif menu == "👥 Nómina UGPP":
    st.header("👮‍♀️ Escudo Anti-UGPP (Ley 1393)")
    
    col1, col2 = st.columns(2)
    with col1:
        salario = st.number_input("Salario Básico", value=1300000.0)
        no_salarial = st.number_input("Pagos No Salariales (Bonos, Auxilios)", value=0.0)
    
    with col2:
        st.write("### Resultados")
        if st.button("Calcular IBC Real"):
            ibc, exc, msg, estado = auditar_nomina_ugpp(salario, no_salarial)
            
            if estado == "Riesgo":
                st.error(f"{msg}")
                st.metric("IBC Ajustado (PILA)", f"${ibc:,.0f}", delta=f"+{exc:,.0f} Ajuste")
            else:
                st.success(msg)
                st.metric("IBC Reportar", f"${ibc:,.0f}")
