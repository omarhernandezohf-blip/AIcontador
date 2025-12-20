import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import time
import io

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="ContadorIA Pro", page_icon="🕵️‍♂️", layout="wide")

def local_css():
    st.markdown("""
        <style>
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .stButton>button {
            background: linear-gradient(90deg, #2563EB 0%, #1E40AF 100%);
            color: white; border: none; padding: 0.6rem 1.2rem;
            border-radius: 8px; font-weight: 600; width: 100%;
        }
        /* Estilos para semáforo de riesgo */
        .riesgo-alto { color: #dc2626; font-weight: bold; }
        .riesgo-medio { color: #d97706; font-weight: bold; }
        .riesgo-bajo { color: #059669; font-weight: bold; }
        </style>
        """, unsafe_allow_html=True)
local_css()

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830305.png", width=80)
    st.title("ContadorIA Suite")
    st.markdown("---")
    api_key_input = st.text_input("🔑 Tu API Key de Google", type="password")
    api_key = api_key_input.strip() if api_key_input else None
    
    if api_key:
        genai.configure(api_key=api_key)
        st.success("Sistema Conectado")
    else:
        st.warning("Ingresa la Key para activar el cerebro.")

    st.markdown("---")
    st.info("💡 Tip: Para la auditoría masiva, asegúrate de que tu Excel tenga una columna llamada 'Concepto' o 'Detalle'.")

# --- FUNCIONES ---
def encontrar_modelo_disponible():
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferidos = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        for pref in preferidos:
            if pref in modelos: return pref
        return modelos[0] if modelos else None
    except:
        return None

def auditar_fila(concepto, valor):
    """Envía un solo gasto a la IA para evaluación rápida"""
    try:
        # Usamos flash por velocidad y economía
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = f"""
        Actúa como auditor de la DIAN (Colombia). Analiza este gasto:
        Concepto: "{concepto}"
        Valor: ${valor}
        
        Responde SOLO con un objeto JSON (sin markdown):
        {{"riesgo": "Alto/Medio/Bajo", "justificacion": "Explicación corta de 10 palabras", "cuenta_sugerida": "Código PUC"}}
        """
        response = model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return {"riesgo": "Error", "justificacion": "Fallo en IA", "cuenta_sugerida": "N/A"}

# --- ESTRUCTURA DE PESTAÑAS (Aquí empieza el contenido principal) ---
tab1, tab2 = st.tabs(["📤 Digitalizador de Facturas", "🕵️ Auditor de Riesgos (IA)"])

# ==========================================
# PESTAÑA 1: DIGITALIZADOR (Facturas)
# ==========================================
with tab1:
    st.header("⚡ De Imagen a Excel")
    st.markdown("Sube fotos de facturas y extrae los datos automáticamente.")

    archivos = st.file_uploader("Arrastra facturas aquí", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="facturas")

    if archivos and st.button("Procesar Facturas"):
        if not api_key:
            st.error("Falta la API Key")
        else:
            nombre_modelo = encontrar_modelo_disponible()
            model = genai.GenerativeModel(nombre_modelo)
            resultados = []
            barra = st.progress(0)
            
            for i, archivo in enumerate(archivos):
                barra.progress((i + 1) / len(archivos))
                try:
                    image = Image.open(archivo)
                    # Prompt limpio en una sola línea para evitar errores
                    prompt_factura = """Extrae en JSON: {"fecha": "YYYY-MM-DD", "proveedor": "texto", "nit": "texto", "total": numero, "iva": numero}"""
                    
                    response = model.generate_content([prompt_factura, image])
                    data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
                    data["archivo"] = archivo.name
                    resultados.append(data)
                    time.sleep(1)
                except:
                    resultados.append({"archivo": archivo.name, "proveedor": "ERROR"})

            st.data_editor(pd.DataFrame(resultados), use_container_width=True)

# ==========================================
# PESTAÑA 2: AUDITOR IA (Consulta + Masivo)
# ==========================================
with tab2:
    st.header("🕵️ Auditoría Tributaria Inteligente")
    
    # --- SECCIÓN A: CONSULTA RÁPIDA ---
    with st.expander("🔍 Consulta Rápida (Un solo caso)", expanded=True):
        c1, c2 = st.columns([2, 1])
        caso = c1.text_input("Describe el gasto:", placeholder="Ej: Almuerzo de negocios por $200.000")
        if c2.button("Auditar Caso") and api_key:
            res = auditar_fila(caso, "N/A")
            st.write(f"**Veredicto:** {res['riesgo']} - {res['justificacion']}")

    st.divider()

    # --- SECCIÓN B: AUDITORÍA MASIVA ---
    st.subheader("📊 Auditoría Masiva de Auxiliares")
    st.markdown("Sube tu archivo de Excel (de Siigo, World Office, etc.) y detecta riesgos fiscales automáticamente.")

    archivo_excel = st.file_uploader("Sube tu Excel (.xlsx)", type=["xlsx"])

    if archivo_excel:
        df = pd.read_excel(archivo_excel)
        st.write("Vista previa de tus datos:")
        st.dataframe(df.head(3))

        # Selector de columnas
        col_concepto = st.selectbox("¿En qué columna está la descripción del gasto?", df.columns)
        col_valor = st.selectbox("¿En qué columna está el valor?", df.columns)

        if st.button("🚀 Iniciar Auditoría Masiva") and api_key:
            st.info("⏳ Iniciando análisis con IA... Esto puede tomar unos segundos por fila.")
            
            df_a_procesar = df.head(10).copy() # Procesamos solo 10 para demo
            
            resultados_auditoria = []
            barra_audit = st.progress(0)

            for index, row in df_a_procesar.iterrows():
                barra_audit.progress((index + 1) / len(df_a_procesar))
                
                analisis = auditar_fila(row[col_concepto], row[col_valor])
                
                resultados_auditoria.append({
                    "Concepto Original": row[col_concepto],
                    "Valor": row[col_valor],
                    "🚨 Nivel de Riesgo": analisis['riesgo'],
                    "💡 Observación IA": analisis['justificacion'],
                    "📚 Cuenta Sugerida": analisis['cuenta_sugerida']
                })
                time.sleep(0.5) 

            df_final = pd.DataFrame(resultados_auditoria)
            
            st.success("¡Análisis completado!")
            st.markdown("### 📋 Reporte de Hallazgos")
            
            def color_riesgo(val):
                if not isinstance(val, str): return ''
                color = 'green' if 'Bajo' in val else 'orange' if 'Medio' in val else 'red'
                return f'color: {color}; font-weight: bold'

            st.dataframe(df_final.style.applymap(color_riesgo, subset=['🚨 Nivel de Riesgo']), use_container_width=True)
            
            csv_audit = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar Reporte", data=csv_audit, file_name="Reporte_Riesgos_IA.csv")

        elif not api_key:
            st.error("⚠️ Por favor conecta tu API Key en el menú izquierdo.")
