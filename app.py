import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import io

# ==============================================================================
# 1. CONFIGURACIÓN VISUAL PROFESIONAL
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    h1 { color: #0d6efd; font-weight: 800; }
    h2, h3 { color: #343a40; }
    .stButton>button {
        background-color: #0d6efd; color: white; border-radius: 8px; 
        font-weight: bold; width: 100%; height: 3.5em; border: none;
    }
    .stButton>button:hover { background-color: #0b5ed7; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
    .reporte-box {
        background-color: #ffffff; padding: 20px; border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 6px solid #0d6efd;
    }
    .riesgo-alto { color: #dc3545; font-weight: bold; }
    .riesgo-medio { color: #ffc107; font-weight: bold; }
    .ok { color: #198754; font-weight: bold; }
    /* Estilo para el buscador RUES */
    .rues-card {
        background-color: #e3f2fd; padding: 20px; border-radius: 10px; border: 1px solid #90caf9;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. CONSTANTES FISCALES 2025 (Parametrización)
# ==============================================================================
SMMLV_2025 = 1430000
AUX_TRANS_2025 = 175000
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025  # Art 771-5 E.T.
BASE_RET_SERVICIOS = 4 * UVT_2025
BASE_RET_COMPRAS = 27 * UVT_2025

# ==============================================================================
# 3. LÓGICA DE NEGOCIO (EL MOTOR CONTABLE)
# ==============================================================================

def calcular_dv(nit):
    """Calcula el Dígito de Verificación (DV) según la fórmula de la DIAN."""
    try:
        nit = str(nit).strip()
        if not nit.isdigit():
            return "?"
        
        primos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        suma = 0
        for i, numero in enumerate(reversed(nit)):
            if i < len(primos):
                suma += int(numero) * primos[i]
        
        resto = suma % 11
        if resto > 1:
            dv = 11 - resto
        else:
            dv = resto
        return str(dv)
    except:
        return "?"

def analizar_gasto_fila(row, col_valor, col_metodo, col_concepto):
    hallazgos = []
    riesgo = "BAJO"
    valor = float(row[col_valor]) if pd.notnull(row[col_valor]) else 0
    metodo = str(row[col_metodo]) if pd.notnull(row[col_metodo]) else ""
    
    if 'efectivo' in metodo.lower() and valor > TOPE_EFECTIVO:
        hallazgos.append(f"⛔ RECHAZO FISCAL: Pago en efectivo (${valor:,.0f}) supera tope individual.")
        riesgo = "ALTO"
    
    if valor >= BASE_RET_SERVICIOS and valor < BASE_RET_COMPRAS:
        hallazgos.append("⚠️ ALERTA: Verificar si se practicó Retención (Base Servicios superada).")
        if riesgo == "BAJO": riesgo = "MEDIO"
    elif valor >= BASE_RET_COMPRAS:
        hallazgos.append("⚠️ ALERTA: Verificar Retención (Base Compras superada).")
        if riesgo == "BAJO": riesgo = "MEDIO"

    return " | ".join(hallazgos) if hallazgos else "OK", riesgo

def calcular_ugpp_fila(row, col_salario, col_no_salarial):
    salario = float(row[col_salario]) if pd.notnull(row[col_salario]) else 0
    no_salarial = float(row[col_no_salarial]) if pd.notnull(row[col_no_salarial]) else 0
    total_ingresos = salario + no_salarial
    limite_40 = total_ingresos * 0.40
    
    if no_salarial > limite_40:
        exceso = no_salarial - limite_40
        ibc_ajustado = salario + exceso
        return ibc_ajustado, exceso, "RIESGO ALTO", f"Excede límite por ${exceso:,.0f}"
    else:
        return salario, 0, "OK", "Cumple norma"

def calcular_costo_empresa_fila(row, col_salario, col_aux, col_arl, col_exo):
    salario = float(row[col_salario])
    tiene_aux = str(row[col_aux]).strip().lower() in ['si', 's', 'true', '1', 'yes']
    nivel_arl = int(row[col_arl]) if pd.notnull(row[col_arl]) else 1
    es_exonerado = str(row[col_exo]).strip().lower() in ['si', 's', 'true', '1', 'yes']
    
    aux_trans = AUX_TRANS_2025 if tiene_aux else 0
    ibc = salario
    base_prestaciones = salario + aux_trans
    
    salud = 0 if es_exonerado else ibc * 0.085
    pension = ibc * 0.12
    arl_tabla = {1:0.00522, 2:0.01044, 3:0.02436, 4:0.0435, 5:0.0696}
    arl_val = ibc * arl_tabla.get(nivel_arl, 0.00522)
    parafiscales = ibc * 0.04 
    if not es_exonerado: parafiscales += ibc * 0.05
    prestaciones = base_prestaciones * 0.2183 
    
    total_costo = base_prestaciones + salud + pension + arl_val + parafiscales + prestaciones
    return total_costo, (total_costo - base_prestaciones)

# --- FUNCIONES IA ---
def consultar_ia_gemini(prompt):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error de conexión IA: {str(e)}"

def ocr_factura(imagen):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = """
        Extrae los datos contables de esta imagen en formato JSON estricto:
        {"fecha": "YYYY-MM-DD", "nit": "sin digito", "proveedor": "texto", "concepto": "texto", "base": numero, "iva": numero, "total": numero}
        """
        response = model.generate_content([prompt, imagen])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return None

# ==============================================================================
# 4. BARRA LATERAL (CONFIGURACIÓN)
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    st.title("Suite Contable IA")
    st.markdown("---")
    
    menu = st.radio("Selecciona Herramienta:", 
                    ["🔎 Buscador RUT/RUES", # <--- NUEVO
                     "📂 Auditoría Masiva de Gastos", 
                     "👥 Escáner de Nómina (UGPP)", 
                     "💰 Calculadora Costos (Masiva)",
                     "📸 Digitalización (OCR)",
                     "📊 Analítica Financiera"])
    
    st.markdown("---")
    with st.expander("🔑 Activar Inteligencia Artificial"):
        st.info("Pega tu API Key de Google aquí para habilitar las funciones de razonamiento y lectura de facturas.")
        api_key = st.text_input("API Key:", type="password")
        if api_key: genai.configure(api_key=api_key)

# ==============================================================================
# 5. PESTAÑAS Y FUNCIONALIDADES
# ==============================================================================

# ------------------------------------------------------------------------------
# NUEVO MÓDULO: BUSCADOR RUT / RUES
# ------------------------------------------------------------------------------
if menu == "🔎 Buscador RUT/RUES":
    st.header("🔎 Buscador y Validador Tributario")
    st.info("Valida el NIT, calcula el Dígito de Verificación (DV) y accede directamente a los portales oficiales sin dar vueltas.")
    
    col_bus_1, col_bus_2 = st.columns([1, 2])
    
    with col_bus_1:
        st.subheader("Datos del Tercero")
        nit_busqueda = st.text_input("Ingresa el NIT (Sin DV y sin puntos):", placeholder="Ej: 900123456")
        
        if nit_busqueda:
            dv_calculado = calcular_dv(nit_busqueda)
            st.markdown(f"""
            <div class='rues-card'>
                <h4>Dígito de Verificación</h4>
                <h1 style='color: #0d6efd; margin: 0;'>{dv_calculado}</h1>
                <p>NIT Completo: <b>{nit_busqueda}-{dv_calculado}</b></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Escribe un NIT para comenzar.")

    with col_bus_2:
        st.subheader("🌐 Accesos Directos Oficiales")
        st.markdown("Selecciona dónde quieres consultar este NIT. La App te llevará a la ficha exacta si es posible.")
        
        c_rues, c_dian = st.columns(2)
        
        with c_rues:
            st.markdown("### 🏢 RUES (Cámaras)")
            st.write("Consulta matrícula mercantil y renovación.")
            # RUES no permite enlace directo por query, llevamos al buscador principal
            st.link_button("🌍 Consultar en RUES.org.co", "https://www.rues.org.co/")
        
        with c_dian:
            st.markdown("### 🏛️ DIAN (RUT)")
            st.write("Consulta estado del RUT y obligaciones.")
            st.link_button("🌍 Estado del RUT (Muisca)", "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces")
            
        st.markdown("---")
        st.markdown("### 🛠️ Herramientas Extra")
        c_junta, c_ante = st.columns(2)
        with c_junta:
            st.link_button("🎓 Certificado Contadores (JCC)", "https://www.jcc.gov.co/")
        with c_ante:
            st.link_button("⚖️ Antecedentes Judiciales", "https://antecedentes.policia.gov.co:7005/WebJudicial/")

# ------------------------------------------------------------------------------
# MÓDULO 1: AUDITORÍA MASIVA DE GASTOS
# ------------------------------------------------------------------------------
elif menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal Masiva")
    st.info("Descarga el auxiliar de gastos de tu software y súbelo aquí. Buscaremos errores de Bancarización y Retenciones.")
    
    archivo = st.file_uploader("Cargar Auxiliar (.xlsx) - Soporta hasta 5GB", type=['xlsx'])
    
    if archivo:
        df = pd.read_excel(archivo)
        st.write("### 1. Mapeo de Columnas")
        c1, c2, c3, c4 = st.columns(4)
        col_fecha = c1.selectbox("Fecha:", df.columns)
        col_tercero = c2.selectbox("Nombre Tercero:", df.columns)
        col_concepto = c3.selectbox("Concepto/Detalle:", df.columns)
        col_valor = c4.selectbox("Valor Gasto:", df.columns)
        col_metodo = st.selectbox("Forma de Pago (Opcional):", ["No disponible"] + list(df.columns))
        
        if st.button("🔍 INICIAR AUDITORÍA AUTOMÁTICA"):
            st.write("🔄 Ejecutando validaciones...")
            barra = st.progress(0)
            resultados = []
            
            for idx, row in df.iterrows():
                barra.progress((idx + 1) / len(df))
                metodo_val = row[col_metodo] if col_metodo != "No disponible" else "Efectivo"
                hallazgo, nivel_riesgo = analizar_gasto_fila(row, col_valor, col_fecha, col_concepto) 
                
                # Lógica local
                hallazgo_texto = []
                riesgo_val = "BAJO"
                val = float(row[col_valor]) if pd.notnull(row[col_valor]) else 0
                if "efectivo" in str(metodo_val).lower() and val > TOPE_EFECTIVO:
                    hallazgo_texto.append("RECHAZO 771-5 (Efectivo)")
                    riesgo_val = "ALTO"
                if val >= BASE_RET_SERVICIOS:
                    hallazgo_texto.append("Revisar Retención")
                    if riesgo_val == "BAJO": riesgo_val = "MEDIO"
                
                resultados.append({
                    "Fila": idx + 2, "Fecha": row[col_fecha], "Tercero": row[col_tercero],
                    "Concepto": row[col_concepto], "Valor": val,
                    "Hallazgos": " | ".join(hallazgo_texto) if hallazgo_texto else "OK", "Riesgo": riesgo_val
                })
            
            df_res = pd.DataFrame(resultados)
            
            if api_key:
                st.write("🧠 IA Analizando conceptos...")
                top = df.groupby(col_concepto)[col_valor].sum().sort_values(ascending=False).head(10)
                st.info(consultar_ia_gemini(f"Busca NO DEDUCIBLES en: {top.to_string()}"))
            
            def color(val):
                return f'background-color: {"#ffcccc" if "ALTO" in str(val) else ("#fff3cd" if "MEDIO" in str(val) else "#d1e7dd")}'
            
            st.dataframe(df_res.style.applymap(color, subset=['Riesgo']), use_container_width=True)
            
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                df_res.to_excel(writer, index=False)
            st.download_button("📥 Descargar Auditoría", out.getvalue(), "Auditoria_Gastos.xlsx")

# ------------------------------------------------------------------------------
# MÓDULO 2: ESCÁNER DE NÓMINA (UGPP)
# ------------------------------------------------------------------------------
elif menu == "👥 Escáner de Nómina (UGPP)":
    st.header("👥 Escáner Masivo Anti-UGPP")
    st.info("Valida la Ley 1393 (Regla del 40%) en tu nómina.")
    
    archivo_nom = st.file_uploader("Cargar Nómina (.xlsx) - Soporta hasta 5GB", type=['xlsx'])
    
    if archivo_nom:
        df_nom = pd.read_excel(archivo_nom)
        st.write("### Mapeo de Columnas")
        c1, c2, c3 = st.columns(3)
        col_nom = c1.selectbox("Empleado:", df_nom.columns)
        col_sal = c2.selectbox("Salario Básico:", df_nom.columns)
        col_nosal = c3.selectbox("Total NO Salarial:", df_nom.columns)
        
        if st.button("👮‍♀️ AUDITAR NÓMINA"):
            res_ugpp = []
            riesgo_total = 0
            for idx, row in df_nom.iterrows():
                ibc, exc, est, msg = calcular_ugpp_fila(row, col_sal, col_nosal)
                if est == "RIESGO ALTO": riesgo_total += exc
                res_ugpp.append({
                    "Empleado": row[col_nom], "Salario": row[col_sal], "No Salarial": row[col_nosal],
                    "Estado": est, "Exceso Reportar": exc, "IBC PILA": ibc
                })
            
            df_ugpp = pd.DataFrame(res_ugpp)
            st.metric("Riesgo Total Omisión", f"${riesgo_total:,.0f}")
            st.dataframe(df_ugpp)

# ------------------------------------------------------------------------------
# MÓDULO 3: CALCULADORA COSTOS
# ------------------------------------------------------------------------------
elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Presupuesto de Nómina Real")
    st.info("Calcula el costo total empresa (SS + Prestaciones).")
    
    archivo_costos = st.file_uploader("Cargar Planta (.xlsx) - Soporta hasta 5GB", type=['xlsx'])
    
    if archivo_costos:
        df_c = pd.read_excel(archivo_costos)
        c1, c2, c3, c4 = st.columns(4)
        col_n = c1.selectbox("Empleado:", df_c.columns)
        col_s = c2.selectbox("Salario:", df_c.columns)
        col_a = c3.selectbox("¿Aux Trans? (SI/NO):", df_c.columns)
        col_r = c4.selectbox("Riesgo ARL (1-5):", df_c.columns)
        col_e = st.selectbox("¿Exonerado? (SI/NO):", df_c.columns)
        
        if st.button("🧮 CALCULAR COSTOS"):
            res_c = []
            tot = 0
            for idx, row in df_c.iterrows():
                costo, carga = calcular_costo_empresa_fila(row, col_s, col_a, col_r, col_e)
                tot += costo
                res_c.append({"Empleado": row[col_n], "Costo Total": costo, "Carga Oculta": carga})
            
            st.metric("COSTO NÓMINA TOTAL", f"${tot:,.0f}")
            st.dataframe(pd.DataFrame(res_c))

# ------------------------------------------------------------------------------
# MÓDULO 4: DIGITALIZACIÓN
# ------------------------------------------------------------------------------
elif menu == "📸 Digitalización (OCR)":
    st.header("📸 De Papel a Excel")
    st.info("Sube fotos de facturas físicas. La IA extraerá los datos.")
    
    archivos = st.file_uploader("Cargar Fotos - Soporta hasta 5GB", type=["jpg", "png"], accept_multiple_files=True)
    
    if archivos and st.button("🚀 PROCESAR") and api_key:
        ocr_data = []
        bar = st.progress(0)
        for i, f in enumerate(archivos):
            bar.progress((i+1)/len(archivos))
            d = ocr_factura(Image.open(f))
            if d: ocr_data.append(d)
        
        df_ocr = pd.DataFrame(ocr_data)
        st.data_editor(df_ocr)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as w:
            df_ocr.to_excel(w, index=False)
        st.download_button("📥 Descargar Excel", out.getvalue(), "Facturas.xlsx")

# ------------------------------------------------------------------------------
# MÓDULO 5: ANALÍTICA
# ------------------------------------------------------------------------------
elif menu == "📊 Analítica Financiera":
    st.header("📊 Tablero de Control Inteligente")
    st.info("Sube tu Balance o Libro Diario para diagnóstico IA.")
    
    archivo_fin = st.file_uploader("Cargar Datos - Soporta hasta 5GB", type=['csv', 'xlsx'])
    
    if archivo_fin and api_key:
        if archivo_fin.name.endswith('.csv'): df_fin = pd.read_csv(archivo_fin)
        else: df_fin = pd.read_excel(archivo_fin)
        
        col_d = st.selectbox("Descripción:", df_fin.columns)
        col_v = st.selectbox("Valor:", df_fin.columns)
        
        if st.button("🤖 ANALIZAR"):
            res = df_fin.groupby(col_d)[col_v].sum().sort_values(ascending=False).head(15)
            st.bar_chart(res)
            with st.spinner("IA Pensando..."):
                st.markdown(consultar_ia_gemini(f"Analiza saldos: {res.to_string()}"))

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown("<center>Desarrollado para Contadores 4.0 | Bucaramanga, Colombia</center>", unsafe_allow_html=True)
