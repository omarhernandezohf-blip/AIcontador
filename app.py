import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import time
import io

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="ContadorIA Pro", page_icon="💼", layout="wide")

def local_css():
    st.markdown("""
        <style>
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .stButton>button {
            background: linear-gradient(90deg, #2563EB 0%, #1E40AF 100%);
            color: white; border: none; padding: 0.6rem 1.2rem;
            border-radius: 8px; font-weight: 600; width: 100%;
        }
        .audit-box {
            padding: 15px; border-radius: 10px; margin-bottom: 10px;
            border-left: 5px solid #ccc; background-color: #f8f9fa;
        }
        .risk-high { border-left-color: #ef4444; background-color: #fef2f2; }
        .risk-medium { border-left-color: #f59e0b; background-color: #fffbeb; }
        .risk-low { border-left-color: #10b981; background-color: #ecfdf5; }
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
    st.markdown("### Herramientas:")
    st.markdown("- **Digitalizador:** Pasa fotos a Excel.")
    st.markdown("- **Auditoría:** Detecta riesgos fiscales.")

# --- FUNCIÓN INTELIGENTE DE AUTO-DETECCIÓN ---
def encontrar_modelo_disponible():
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferidos = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro-vision']
        for pref in preferidos:
            if pref in modelos: return pref
        return modelos[0] if modelos else None
    except:
        return None

# --- ESTRUCTURA DE PESTAÑAS ---
tab1, tab2 = st.tabs(["📤 Digitalizador de Facturas", "🕵️ Auditor de Riesgos (NUEVO)"])

# ==========================================
# PESTAÑA 1: TU CÓDIGO ORIGINAL (MEJORADO)
# ==========================================
with tab1:
    st.header("⚡ Digitalización Masiva")
    st.markdown("Sube tus facturas (imágenes) y obtén el Excel consolidado.")

    if not api_key:
        st.info("👈 Conecta la API Key primero.")
    else:
        archivos = st.file_uploader("Arrastra facturas aquí (Máx 10)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

        if archivos:
            if st.button(f"Procesar {len(archivos)} Facturas"):
                nombre_modelo = encontrar_modelo_disponible()
                model = genai.GenerativeModel(nombre_modelo)
                resultados = []
                
                barra = st.progress(0)
                
                for i, archivo in enumerate(archivos):
                    barra.progress((i + 1) / len(archivos))
                    try:
                        image = Image.open(archivo)
                        prompt = """
                        Analiza esta factura colombiana. Extrae JSON:
                        {"fecha": "YYYY-MM-DD", "proveedor": "texto", "nit": "texto", "concepto": "resumen corto", "total": numero, "iva": numero}
                        """
                        response = model.generate_content([prompt, image])
                        # Limpieza básica del JSON
                        txt = response.text.replace("```json", "").replace("```", "").strip()
                        data = json.loads(txt)
                        data["archivo"] = archivo.name
                        resultados.append(data)
                        time.sleep(1) # Respetar límites
                    except Exception as e:
                        resultados.append({"archivo": archivo.name, "proveedor": "ERROR", "nota": str(e)})

                st.success("¡Procesado!")
                
                # Mostrar Tabla
                df = pd.DataFrame(resultados)
                st.data_editor(df, use_container_width=True)
                
                # Descargar
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar Excel/CSV", data=csv, file_name="gastos_procesados.csv", mime="text/csv")

# ==========================================
# PESTAÑA 2: LA INNOVACIÓN (AUDITOR IA)
# ==========================================
with tab2:
    st.header("🕵️ Auditoría Tributaria Preventiva")
    st.markdown("""
    **¿Dudas si un gasto es deducible?** ¿No sabes qué retención aplicar? 
    Pregúntale al Auditor IA antes de registrarlo en Siigo y evita sanciones.
    """)

    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Consulta Rápida")
        caso_usuario = st.text_area("Describe el gasto o la situación:", 
                                   placeholder="Ej: Voy a pagar una factura de $500.000 por 'Atenciones a clientes' (almuerzo) a un restaurante régimen simple. ¿Es deducible? ¿Qué retención aplico?",
                                   height=150)
        
        analizar_btn = st.button("🔍 Auditar Caso")

    with col2:
        st.subheader("Dictamen del Auditor IA")
        if analizar_btn and api_key and caso_usuario:
            with st.spinner("Consultando Estatuto Tributario..."):
                try:
                    modelo_txt = 'models/gemini-1.5-flash'
                    model_audit = genai.GenerativeModel(modelo_txt)
                    
                    prompt_audit = f"""
                    Actúa como un Auditor Tributario Experto de Colombia (DIAN).
                    Analiza el siguiente caso: "{caso_usuario}"
                    
                    Responde en este formato estricto:
                    1. **Veredicto:** (Deducible / No Deducible / Riesgoso)
                    2. **Retención en la Fuente:** (Indica el % y el concepto exacto según tabla 2024/2025)
                    3. **Cuenta Contable Sugerida (PUC):** (Código y nombre)
                    4. **Justificación Legal:** (Cita artículos del Estatuto Tributario brevemente)
                    
                    Sé directo y profesional.
                    """
                    
                    respuesta = model_audit.generate_content(prompt_audit)
                    st.markdown(respuesta.text)
                    
                except Exception as e:
                    st.error(f"Error en consulta: {e}")
        elif analizar_btn and not api_key:
            st.error("Falta la API Key")
        else:
            st.info("Los resultados aparecerán aquí.")

    st.markdown("---")
    st.markdown("### 📊 O carga un listado de gastos (Excel) para auditar masivamente")
    st.caption("Próximamente: Sube tu 'Auxiliar de Gastos' y detectaremos anomalías automáticamente.")
