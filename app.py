import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import time
import io

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Asistente Contable IA", page_icon="📊", layout="wide")

# Estilos visuales para que se vea limpio y profesional
def local_css():
    st.markdown("""
        <style>
        html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
        .stButton>button {
            background-color: #0056b3; color: white; border-radius: 8px; 
            font-weight: bold; width: 100%; padding: 10px;
        }
        /* Cajas de alerta personalizadas */
        .alerta-roja { color: #721c24; background-color: #f8d7da; padding: 10px; border-radius: 5px; border-left: 5px solid red;}
        .alerta-verde { color: #155724; background-color: #d4edda; padding: 10px; border-radius: 5px; border-left: 5px solid green;}
        </style>
        """, unsafe_allow_html=True)
local_css()

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    st.title("Panel de Control")
    st.markdown("---")
    
    # Explicación clara de la llave
    st.markdown("### 🔑 Paso 1: Activar Sistema")
    api_key_input = st.text_input("Pega aquí tu API Key de Google", type="password", help="Es la contraseña que conecta con la Inteligencia Artificial.")
    
    if api_key_input:
        genai.configure(api_key=api_key_input)
        st.success("✅ Sistema ACTIVADO y listo.")
    else:
        st.warning("⚠️ El sistema está en pausa. Ingresa la llave para iniciar.")

    st.markdown("---")
    st.info("ℹ️ **Soporte:** Esta herramienta ayuda a agilizar la digitación y revisión, pero el criterio final es del Contador.")

# --- FUNCIONES DEL CEREBRO (IA) ---
def encontrar_modelo():
    """Busca el mejor modelo de IA disponible"""
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Priorizamos el modelo Flash que es rápido y bueno para documentos
        preferidos = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        for pref in preferidos:
            if pref in modelos: return pref
        return modelos[0] if modelos else None
    except:
        return None

def auditar_gasto(concepto, valor):
    """Consulta normativa sobre un gasto específico"""
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = f"""
        Actúa como un Auditor Tributario Senior de Colombia.
        Analiza este gasto según el Estatuto Tributario vigente:
        Concepto: "{concepto}"
        Valor: ${valor}
        
        Responde SOLO en formato JSON:
        {{"riesgo": "ALTO (No Deducible) / MEDIO / BAJO (Deducible)", "razon": "Explicación breve normativa", "cuenta_puc": "Código sugerido"}}
        """
        response = model.generate_content(prompt)
        texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)
    except:
        return {"riesgo": "Error", "razon": "No se pudo analizar", "cuenta_puc": "N/A"}

# --- TÍTULO PRINCIPAL ---
st.title("🤖 Asistente Contable Inteligente")
st.markdown("### Automatización y Auditoría para Contadores Modernos")

# --- PESTAÑAS (TABS) CLARAS ---
tab1, tab2 = st.tabs(["📄 1. Digitación Automática (De Foto a Excel)", "⚖️ 2. Auditoría y Conceptos DIAN"])

# ==============================================================================
# PESTAÑA 1: DIGITACIÓN (Para ahorrar tiempo de tecleo)
# ==============================================================================
with tab1:
    st.header("📸 De Papel a Excel en Segundos")
    st.markdown("""
    **Instrucciones:**
    1. Sube fotos de facturas físicas, recibos de caja o cuentas de cobro.
    2. La IA leerá la **Fecha, NIT, Proveedor, Base e IVA**.
    3. Descarga el Excel listo para copiar y pegar en tu software contable (Siigo, World Office, etc.).
    """)

    archivos = st.file_uploader("📂 Cargar imágenes de facturas (JPG, PNG)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    if archivos and st.button("🚀 Extraer Datos y Generar Excel"):
        if not api_key_input:
            st.error("⛔ Por favor ingresa la API Key en el menú de la izquierda primero.")
        else:
            modelo_usar = encontrar_modelo()
            if not modelo_usar:
                st.error("Error de conexión con Google.")
            else:
                model = genai.GenerativeModel(modelo_usar)
                resultados = []
                barra = st.progress(0)
                st.info("⏳ Leyendo documentos... Por favor espera.")

                for i, archivo in enumerate(archivos):
                    # Barra de progreso
                    barra.progress((i + 1) / len(archivos))
                    
                    try:
                        image = Image.open(archivo)
                        # Prompt directo para extracción contable
                        prompt_factura = """
                        Actúa como auxiliar contable. Extrae los datos de esta imagen en formato JSON estricto:
                        {"fecha_factura": "YYYY-MM-DD", "nit_proveedor": "solo numeros", "nombre_proveedor": "texto", "descripcion_breve": "texto", "subtotal": numero, "iva": numero, "total_pagar": numero}
                        Si algún dato no se ve, pon null o 0.
                        """
                        response = model.generate_content([prompt_factura, image])
                        texto_json = response.text.replace("```json", "").replace("```", "").strip()
                        data = json.loads(texto_json)
                        data["Nombre Archivo"] = archivo.name # Para saber de cuál factura viene
                        resultados.append(data)
                        time.sleep(1) # Pausa técnica
                    except Exception as e:
                        resultados.append({"Nombre Archivo": archivo.name, "nombre_proveedor": "ERROR DE LECTURA", "descripcion_breve": str(e)})

                # Éxito
                st.success("✅ ¡Lectura finalizada!")
                
                # Mostrar Tabla
                df = pd.DataFrame(resultados)
                
                # Reordenar columnas para que sea lógico contablemente
                columnas_orden = ["fecha_factura", "nit_proveedor", "nombre_proveedor", "descripcion_breve", "subtotal", "iva", "total_pagar", "Nombre Archivo"]
                # Aseguramos que existan las columnas antes de ordenar
                cols_finales = [c for c in columnas_orden if c in df.columns]
                df = df[cols_finales]

                st.data_editor(df, use_container_width=True)

                # Botón Descarga
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Importar_Contabilidad')
                
                st.download_button(
                    label="📥 Descargar Excel Listo",
                    data=output.getvalue(),
                    file_name="Facturas_Digitadas_IA.xlsx",
                    mime="application/vnd.ms-excel"
                )

# ==============================================================================
# PESTAÑA 2: AUDITORÍA (Para evitar errores y sanciones)
# ==============================================================================
with tab2:
    st.header("🛡️ Auditoría Tributaria Preventiva")
    st.markdown("Esta herramienta actúa como un **segundo filtro** para revisar gastos dudosos antes de enviarlos a la DIAN.")

    # Opción A: Consulta rápida
    with st.container():
        st.subheader("🔍 A. Consulta Rápida de un Gasto")
        st.caption("Ejemplo: 'Pagué un almuerzo de $200.000 para un cliente. ¿Es deducible de renta?'")
        
        col_preg, col_resp = st.columns([2, 1])
        caso_usuario = col_preg.text_area("Describe el gasto o la duda tributaria:", height=100)
        
        if col_resp.button("Consultar Normativa"):
            if not api_key_input:
                st.error("Falta la API Key en el menú izquierdo.")
            elif not caso_usuario:
                st.warning("Escribe algo para consultar.")
            else:
                with st.spinner("Consultando Estatuto Tributario..."):
                    res = auditar_gasto(caso_usuario, "N/A")
                    
                    # Mostrar resultado visualmente atractivo
                    if "ALTO" in res['riesgo'].upper() or "NO DEDUCIBLE" in res['riesgo'].upper():
                        st.markdown(f"<div class='alerta-roja'>🚨 <b>VEREDICTO:</b> {res['riesgo']}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='alerta-verde'>✅ <b>VEREDICTO:</b> {res['riesgo']}</div>", unsafe_allow_html=True)
                    
                    st.write(f"**Justificación:** {res['razon']}")
                    st.write(f"**Cuenta sugerida:** {res['cuenta_puc']}")

    st.markdown("---")

    # Opción B: Auditoría Masiva
    with st.container():
        st.subheader("📊 B. Revisión Masiva de Auxiliares (Excel)")
        st.markdown("""
        **Instrucciones:**
        1. Descarga un auxiliar de gastos de Siigo/World Office en Excel.
        2. Súbelo aquí.
        3. La IA analizará línea por línea buscando **gastos no deducibles o riesgosos**.
        """)
        
        archivo_excel = st.file_uploader("Sube tu archivo Excel (.xlsx)", type=["xlsx"], key="excel_audit")

        if archivo_excel:
            df_audit = pd.read_excel(archivo_excel)
            st.write("Vista previa (Primeras 3 filas):")
            st.dataframe(df_audit.head(3))

            c1, c2 = st.columns(2)
            col_concepto = c1.selectbox("Selecciona la columna del DETALLE/CONCEPTO:", df_audit.columns)
            col_valor = c2.selectbox("Selecciona la columna del VALOR:", df_audit.columns)

            if st.button("📉 Iniciar Auditoría del Archivo"):
                if not api_key_input:
                    st.error("Falta la API Key.")
                else:
                    st.info("🕵️‍♂️ Analizando gastos... (Esto toma unos segundos por fila)")
                    
                    # Tomamos solo 8 filas para la demo rápida (se puede quitar el .head(8) luego)
                    df_procesar = df_audit.head(8).copy()
                    
                    lista_hallazgos = []
                    barra2 = st.progress(0)

                    for idx, row in df_procesar.iterrows():
                        barra2.progress((idx + 1) / len(df_procesar))
                        resultado = auditar_gasto(str(row[col_concepto]), str(row[col_valor]))
                        
                        lista_hallazgos.append({
                            "Concepto Original": row[col_concepto],
                            "Valor": row[col_valor],
                            "Semáforo Riesgo": resultado['riesgo'],
                            "Opinión Auditor IA": resultado['razon'],
                            "Cuenta Sugerida": resultado['cuenta_puc']
                        })
                        time.sleep(0.5)

                    df_final_audit = pd.DataFrame(lista_hallazgos)
                    st.success("¡Análisis completado!")
                    
                    # Colorear la tabla para impacto visual
                    def pintar_riesgo(val):
                        estilo = ''
                        if 'ALTO' in str(val).upper(): estilo = 'background-color: #ffcccc; color: darkred' # Rojo claro
                        elif 'BAJO' in str(val).upper(): estilo = 'background-color: #ccffcc; color: darkgreen' # Verde claro
                        return estilo

                    st.dataframe(df_final_audit.style.applymap(pintar_riesgo, subset=['Semáforo Riesgo']), use_container_width=True)
