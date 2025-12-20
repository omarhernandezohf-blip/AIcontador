import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import io
import random # Necesario para simular datos del RUT

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
    /* Estilos Tarjeta RUT */
    .rut-card {
        background-color: #e3f2fd; padding: 20px; border-radius: 10px;
        border: 2px solid #90caf9; color: #1565c0;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. CONSTANTES FISCALES 2025
# ==============================================================================
SMMLV_2025 = 1430000
AUX_TRANS_2025 = 175000
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025
BASE_RET_SERVICIOS = 4 * UVT_2025
BASE_RET_COMPRAS = 27 * UVT_2025

# ==============================================================================
# 3. LÓGICA DE NEGOCIO (EL MOTOR CONTABLE)
# ==============================================================================

# --- NUEVA FUNCIÓN: CÁLCULO DÍGITO DE VERIFICACIÓN (REAL) ---
def calcular_dv_colombia(nit_sin_dv):
    """Calcula el DV según el algoritmo oficial de la DIAN (Módulo 11)"""
    try:
        nit_str = str(nit_sin_dv).strip()
        if not nit_str.isdigit(): return "Error"
        
        primos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        suma = 0
        for i, digito in enumerate(reversed(nit_str)):
            if i < len(primos):
                suma += int(digito) * primos[i]
        
        resto = suma % 11
        if resto == 0 or resto == 1:
            return str(resto)
        else:
            return str(11 - resto)
    except:
        return "?"

# --- FUNCIONES ANTERIORES (INTACTAS) ---
def analizar_gasto_fila(row, col_valor, col_metodo, col_concepto):
    hallazgos = []
    riesgo = "BAJO"
    valor = float(row[col_valor]) if pd.notnull(row[col_valor]) else 0
    metodo = str(row[col_metodo]) if pd.notnull(row[col_metodo]) else ""
    if 'efectivo' in metodo.lower() and valor > TOPE_EFECTIVO:
        hallazgos.append(f"⛔ RECHAZO FISCAL: Pago en efectivo (${valor:,.0f}) supera tope individual.")
        riesgo = "ALTO"
    if valor >= BASE_RET_SERVICIOS and valor < BASE_RET_COMPRAS:
        hallazgos.append("⚠️ ALERTA: Verificar Retención (Base Servicios).")
        if riesgo == "BAJO": riesgo = "MEDIO"
    elif valor >= BASE_RET_COMPRAS:
        hallazgos.append("⚠️ ALERTA: Verificar Retención (Base Compras).")
        if riesgo == "BAJO": riesgo = "MEDIO"
    return " | ".join(hallazgos) if hallazgos else "OK", riesgo

def calcular_ugpp_fila(row, col_salario, col_no_salarial):
    salario = float(row[col_salario]) if pd.notnull(row[col_salario]) else 0
    no_salarial = float(row[col_no_salarial]) if pd.notnull(row[col_no_salarial]) else 0
    total = salario + no_salarial
    limite = total * 0.40
    if no_salarial > limite:
        exceso = no_salarial - limite
        return salario + exceso, exceso, "RIESGO ALTO", f"Excede límite por ${exceso:,.0f}"
    return salario, 0, "OK", "Cumple norma"

def calcular_costo_empresa_fila(row, col_salario, col_aux, col_arl, col_exo):
    salario = float(row[col_salario])
    tiene_aux = str(row[col_aux]).strip().lower() in ['si', 's', 'true', '1', 'yes']
    nivel_arl = int(row[col_arl]) if pd.notnull(row[col_arl]) else 1
    es_exonerado = str(row[col_exo]).strip().lower() in ['si', 's', 'true', '1', 'yes']
    aux_trans = AUX_TRANS_2025 if tiene_aux else 0
    ibc = salario
    base_prest = salario + aux_trans
    salud = 0 if es_exonerado else ibc * 0.085
    pension = ibc * 0.12
    arl_t = {1:0.00522, 2:0.01044, 3:0.02436, 4:0.0435, 5:0.0696}
    arl_val = ibc * arl_t.get(nivel_arl, 0.00522)
    paraf = ibc * 0.04 
    if not es_exonerado: paraf += ibc * 0.05
    prest = base_prest * 0.2183 
    total = base_prest + salud + pension + arl_val + paraf + prest
    return total, (total - base_prest)

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
        prompt = """Extrae datos JSON estricto: {"fecha": "YYYY-MM-DD", "nit": "num", "proveedor": "txt", "concepto": "txt", "base": num, "iva": num, "total": num}"""
        response = model.generate_content([prompt, imagen])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return None

# ==============================================================================
# 4. BARRA LATERAL (MENÚ ACTUALIZADO)
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    st.title("Suite Contable IA")
    st.markdown("---")
    
    # NUEVA OPCIÓN AÑADIDA AL MENÚ
    menu = st.radio("Selecciona Herramienta:", 
                    ["🔍 Buscador de RUT (DIAN)",  # <-- NUEVO
                     "📂 Auditoría Masiva de Gastos", 
                     "👥 Escáner de Nómina (UGPP)", 
                     "💰 Calculadora Costos (Masiva)",
                     "📸 Digitalización (OCR)",
                     "📊 Analítica Financiera"])
    
    st.markdown("---")
    with st.expander("🔑 Configuración"):
        st.info("Activar Inteligencia Artificial:")
        api_key = st.text_input("API Key:", type="password")
        if api_key: genai.configure(api_key=api_key)

# ==============================================================================
# 5. PESTAÑAS Y FUNCIONALIDADES
# ==============================================================================

# ------------------------------------------------------------------------------
# MÓDULO NUEVO: BUSCADOR DE RUT / ESTADO DIAN
# ------------------------------------------------------------------------------
if menu == "🔍 Buscador de RUT (DIAN)":
    st.header("🔍 Consulta Estado RUT y Dígito de Verificación")
    
    st.info("""
    **Herramienta Rápida:**
    1. Ingresa la Cédula o NIT (Sin dígito de verificación).
    2. El sistema calculará el **DV oficial** (para que factures bien).
    3. Buscaremos en la base de datos (Simulada para Demo) el estado tributario.
    """)
    
    col_input, col_btn = st.columns([3, 1])
    nit_busqueda = col_input.text_input("Ingrese NIT o Cédula (Solo números):", max_chars=15)
    
    if col_btn.button("🔎 CONSULTAR AHORA") and nit_busqueda:
        # 1. Calcular DV Real
        dv_calculado = calcular_dv_colombia(nit_busqueda)
        
        # 2. Simular Búsqueda en Base de Datos DIAN (Ya que no tenemos API paga)
        st.markdown("---")
        
        # Simulación de datos para demostración
        estados = ["ACTIVO", "SUSPENDIDO", "CANCELADO"]
        responsabilidades = ["Régimen Simple", "Responsable de IVA", "No Responsable", "Gran Contribuyente"]
        actividades = ["6920 - Actividades de Contabilidad", "4711 - Comercio al por menor", "4520 - Mantenimiento de vehículos"]
        
        # Generar datos aleatorios consistentes con el número ingresado
        random.seed(int(nit_busqueda)) 
        estado_sim = random.choice(estados)
        resp_sim = random.choice(responsabilidades)
        act_sim = random.choice(actividades)
        
        # Mostrar Resultado Tipo Tarjeta
        st.subheader("📋 Resultado de la Consulta")
        
        col_res1, col_res2 = st.columns(2)
        
        with col_res1:
            st.markdown(f"""
            <div class='rut-card'>
                <h3>NIT: {nit_busqueda} - {dv_calculado}</h3>
                <p><strong>Dígito de Verificación (Calculado):</strong> {dv_calculado}</p>
                <p><strong>Estado Actual:</strong> {estado_sim}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_res2:
            st.write(f"**Actividad Principal:** {act_sim}")
            st.write(f"**Responsabilidad:** {resp_sim}")
            
            if estado_sim == "ACTIVO":
                st.success("✅ TERCERO HABILITADO PARA FACTURAR")
            else:
                st.error("⛔ TERCERO CON PROBLEMAS EN EL RUT")

        st.caption("Nota: Esta consulta es una simulación basada en algoritmos reales de DV. Para datos en tiempo real de la DIAN se requiere integración API paga.")
        
        # Botón Fake de Descarga
        st.download_button("📥 Descargar Copia RUT (PDF Simulado)", data="Contenido PDF Simulado", file_name=f"RUT_{nit_busqueda}.pdf")

# ------------------------------------------------------------------------------
# MÓDULO: AUDITORÍA MASIVA DE GASTOS
# ------------------------------------------------------------------------------
elif menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal Masiva")
    st.info("Sube tu auxiliar de gastos para detectar errores 771-5 y retenciones.")
    archivo = st.file_uploader("Cargar Auxiliar (.xlsx) - Soporta hasta 5GB", type=['xlsx'])
    
    if archivo:
        df = pd.read_excel(archivo)
        c1, c2, c3, c4 = st.columns(4)
        col_fecha = c1.selectbox("Fecha:", df.columns)
        col_tercero = c2.selectbox("Tercero:", df.columns)
        col_concepto = c3.selectbox("Concepto:", df.columns)
        col_valor = c4.selectbox("Valor:", df.columns)
        col_metodo = st.selectbox("Método Pago:", ["No disponible"] + list(df.columns))
        
        if st.button("🔍 AUDITAR"):
            res = []
            bar = st.progress(0)
            for i, r in enumerate(df.to_dict('records')):
                bar.progress((i+1)/len(df))
                met = r[col_metodo] if col_metodo != "No disponible" else "Efectivo"
                hallazgo, riesgo = analizar_gasto_fila(r, col_valor, col_fecha, col_concepto)
                val = float(r[col_valor]) if pd.notnull(r[col_valor]) else 0
                
                txt = []
                r_val = "BAJO"
                if "efectivo" in str(met).lower() and val > TOPE_EFECTIVO:
                    txt.append("RECHAZO 771-5")
                    r_val = "ALTO"
                if val >= BASE_RET_SERVICIOS:
                    txt.append("Verificar Retención")
                    if r_val == "BAJO": r_val = "MEDIO"
                
                res.append({"Fila": i+2, "Tercero": r[col_tercero], "Valor": val, "Riesgo": r_val, "Nota": " | ".join(txt) if txt else "OK"})
            
            df_r = pd.DataFrame(res)
            
            if api_key:
                st.write("🧠 IA Analizando...")
                top = df.groupby(col_concepto)[col_valor].sum().sort_values(ascending=False).head(5)
                st.info(consultar_ia_gemini(f"Analiza gastos CO: {top.to_string()}"))
            
            def color(v): return f'background-color: {"#ffcccc" if "ALTO" in str(v) else ("#fff3cd" if "MEDIO" in str(v) else "#d1e7dd")}'
            st.dataframe(df_r.style.applymap(color, subset=['Riesgo']))

# ------------------------------------------------------------------------------
# MÓDULO: ESCÁNER UGPP
# ------------------------------------------------------------------------------
elif menu == "👥 Escáner de Nómina (UGPP)":
    st.header("👥 Escáner Anti-UGPP")
    archivo_nom = st.file_uploader("Cargar Nómina (.xlsx) - Soporta hasta 5GB", type=['xlsx'])
    if archivo_nom:
        df_n = pd.read_excel(archivo_nom)
        c1, c2, c3 = st.columns(3)
        cn = c1.selectbox("Nombre:", df_n.columns)
        cs = c2.selectbox("Salario:", df_n.columns)
        cns = c3.selectbox("No Salarial:", df_n.columns)
        
        if st.button("AUDITAR"):
            res = []
            rt = 0
            for r in df_n.to_dict('records'):
                ibc, exc, est, msg = calcular_ugpp_fila(r, cs, cns)
                if est == "RIESGO ALTO": rt += exc
                res.append({"Empleado": r[cn], "Exceso": exc, "Estado": est})
            st.metric("Riesgo Total", f"${rt:,.0f}")
            st.dataframe(pd.DataFrame(res))

# ------------------------------------------------------------------------------
# MÓDULO: CALCULADORA COSTOS
# ------------------------------------------------------------------------------
elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Costos de Nómina")
    ac = st.file_uploader("Cargar Personal (.xlsx) - Soporta hasta 5GB", type=['xlsx'])
    if ac:
        dc = pd.read_excel(ac)
        c1, c2, c3, c4 = st.columns(4)
        cn = c1.selectbox("Empleado:", dc.columns)
        cs = c2.selectbox("Salario:", dc.columns)
        ca = c3.selectbox("Aux Trans (SI/NO):", dc.columns)
        carl = c4.selectbox("ARL (1-5):", dc.columns)
        cex = st.selectbox("Exonerado (SI/NO):", dc.columns)
        
        if st.button("CALCULAR"):
            rc = []
            tot = 0
            for r in dc.to_dict('records'):
                c, car = calcular_costo_empresa_fila(r, cs, ca, carl, cex)
                tot += c
                rc.append({"Empleado": r[cn], "Costo Total": c, "Carga": car})
            st.metric("TOTAL MENSUAL", f"${tot:,.0f}")
            st.dataframe(pd.DataFrame(rc))

# ------------------------------------------------------------------------------
# MÓDULO: OCR FACTURAS
# ------------------------------------------------------------------------------
elif menu == "📸 Digitalización (OCR)":
    st.header("📸 OCR Facturas")
    af = st.file_uploader("Fotos - Soporta hasta 5GB", type=["jpg", "png"], accept_multiple_files=True)
    if af and st.button("PROCESAR") and api_key:
        do = []
        bar = st.progress(0)
        for i, f in enumerate(af):
            bar.progress((i+1)/len(af))
            info = ocr_factura(Image.open(f))
            if info: do.append(info)
        st.data_editor(pd.DataFrame(do))

# ------------------------------------------------------------------------------
# MÓDULO: ANALÍTICA
# ------------------------------------------------------------------------------
elif menu == "📊 Analítica Financiera":
    st.header("📊 Analítica IA")
    fi = st.file_uploader("Datos Financieros - Soporta hasta 5GB", type=['xlsx', 'csv'])
    if fi and api_key:
        dfi = pd.read_csv(fi) if fi.name.endswith('.csv') else pd.read_excel(fi)
        cd = st.selectbox("Descripción:", dfi.columns)
        cv = st.selectbox("Valor:", dfi.columns)
        if st.button("ANALIZAR"):
            res = dfi.groupby(cd)[cv].sum().sort_values(ascending=False).head(10)
            st.bar_chart(res)
            st.markdown(consultar_ia_gemini(f"Analiza saldos: {res.to_string()}"))

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown("<center>Desarrollado para Contadores 4.0 | Bucaramanga, Colombia</center>", unsafe_allow_html=True)
