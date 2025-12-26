import streamlit as st
import pandas as pd
import gspread
import google.generativeai as genai
from PIL import Image
import json
import time
import io
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# ==============================================================================
# 1. CONFIGURACIÓN VISUAL (Debe ir al principio obligatoriamente)
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="📊", layout="wide")

# ==============================================================================
# 2. CONEXIÓN A GOOGLE SHEETS (USANDO SECRETS)
# ==============================================================================
try:
    if "gcp_service_account" in st.secrets:
        credentials_dict = st.secrets["gcp_service_account"]
        # Conectar con Google Sheets usando el diccionario de secretos
        gc = gspread.service_account_from_dict(credentials_dict)
    else:
        # Si no hay secretos, la variable queda nula pero la app no se rompe
        gc = None
except Exception as e:
    st.error(f"Error conectando a Google Sheets: {e}")
    gc = None

# ==============================================================================
# 3. ESTILOS Y CONSTANTES
# ==============================================================================

# Lógica para saludo dinámico
hora_actual = datetime.now().hour
if 5 <= hora_actual < 12:
    saludo = "Buenos días"
    icono_saludo = "☀️"
elif 12 <= hora_actual < 18:
    saludo = "Buenas tardes"
    icono_saludo = "🌤️"
else:
    saludo = "Buenas noches"
    icono_saludo = "🌙"

st.markdown("""
    <style>
    /* --- 1. FONDO Y TIPOGRAFÍA --- */
    .stApp {
        background-color: #0e1117 !important;
        color: #e0e0e0 !important;
    }
    
    html, body, [class*="css"] {
        font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    }

    /* --- 2. TÍTULOS CON DEGRADADO --- */
    h1 {
        background: -webkit-linear-gradient(45deg, #0d6efd, #00d2ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        letter-spacing: -1px;
    }
    h2, h3 { color: #f0f2f6 !important; font-weight: 700; }

    /* --- 3. TARJETAS INTERACTIVAS (GLASSMORPHISM) --- */
    .instruccion-box, .rut-card, .reporte-box, .tutorial-step {
        background: rgba(38, 39, 48, 0.7) !important;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
        transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
    }

    .instruccion-box:hover, .rut-card:hover, .reporte-box:hover, .tutorial-step:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.4);
        border-color: #0d6efd;
    }

    .instruccion-box { border-left: 4px solid #0d6efd; }
    .instruccion-box h4 { color: #0d6efd !important; margin-top: 0; font-weight: bold; }
    .instruccion-box p, .instruccion-box li { color: #b0b3b8 !important; }

    /* --- 4. BOTONES ELEGANTES --- */
    .stButton>button {
        background: linear-gradient(90deg, #0d6efd 0%, #0056b3 100%) !important;
        color: white !important;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        height: 3.5em;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    .stButton>button:hover {
        background: linear-gradient(90deg, #0b5ed7 0%, #004494 100%) !important;
        box-shadow: 0 6px 12px rgba(13, 110, 253, 0.4);
        transform: scale(1.02);
    }

    /* --- 5. ENLACES --- */
    a { color: #4dabf7 !important; text-decoration: none; transition: color 0.2s; }
    a:hover { color: #a5d8ff !important; text-decoration: none; }

    /* --- 6. ALERTAS ESTILIZADAS --- */
    .metric-box-red { 
        background: rgba(62, 18, 22, 0.8) !important; 
        color: #ffaeb6 !important; 
        padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #842029;
    }
    .metric-box-green { 
        background: rgba(15, 41, 30, 0.8) !important; 
        color: #a3cfbb !important; 
        padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #0f5132;
    }
    
    ::-webkit-scrollbar { width: 10px; }
    ::-webkit-scrollbar-track { background: #0e1117; }
    ::-webkit-scrollbar-thumb { background: #303030; border-radius: 5px; }
    ::-webkit-scrollbar-thumb:hover { background: #0d6efd; }
    </style>
    """, unsafe_allow_html=True)

# CONSTANTES FISCALES 2025
SMMLV_2025 = 1430000
AUX_TRANS_2025 = 175000
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025
BASE_RET_SERVICIOS = 4 * UVT_2025
BASE_RET_COMPRAS = 27 * UVT_2025

# ==============================================================================
# 5. FUNCIONES DE LÓGICA DE NEGOCIO
# ==============================================================================

def calcular_dv_colombia(nit_sin_dv):
    try:
        nit_str = str(nit_sin_dv).strip()
        if not nit_str.isdigit(): return "Error"
        primos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        suma = 0
        for i, digito in enumerate(reversed(nit_str)):
            if i < len(primos):
                suma += int(digito) * primos[i]
        resto = suma % 11
        return str(resto) if resto <= 1 else str(11 - resto)
    except:
        return "?"

def analizar_gasto_fila(row, col_valor, col_metodo, col_concepto):
    hallazgos = []
    riesgo = "BAJO"
    valor = float(row[col_valor]) if pd.notnull(row[col_valor]) else 0
    metodo = str(row[col_metodo]) if pd.notnull(row[col_metodo]) else ""
    if 'efectivo' in metodo.lower() and valor > TOPE_EFECTIVO:
        hallazgos.append(f"⛔ RECHAZO FISCAL: Pago en efectivo (${valor:,.0f}) supera tope.")
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

def parsear_xml_dian(archivo_xml):
    try:
        tree = ET.parse(archivo_xml)
        root = tree.getroot()
        ns = {'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
              'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}
        def get_text(path, root_elem=root):
            elem = root_elem.find(path, ns)
            return elem.text if elem is not None else ""
        data = {}
        data['Archivo'] = archivo_xml.name
        data['Prefijo'] = get_text('.//cbc:ID')
        data['Fecha Emision'] = get_text('.//cbc:IssueDate')
        emisor = root.find('.//cac:AccountingSupplierParty', ns)
        if emisor:
            data['NIT Emisor'] = get_text('.//cbc:CompanyID', emisor.find('.//cac:PartyTaxScheme', ns))
            data['Emisor'] = get_text('.//cbc:RegistrationName', emisor.find('.//cac:PartyTaxScheme', ns))
        receptor = root.find('.//cac:AccountingCustomerParty', ns)
        if receptor:
            data['NIT Receptor'] = get_text('.//cbc:CompanyID', receptor.find('.//cac:PartyTaxScheme', ns))
            data['Receptor'] = get_text('.//cbc:RegistrationName', receptor.find('.//cac:PartyTaxScheme', ns))
        monetary = root.find('.//cac:LegalMonetaryTotal', ns)
        if monetary:
            data['Total a Pagar'] = float(get_text('cbc:PayableAmount', monetary) or 0)
            data['Base Imponible'] = float(get_text('cbc:LineExtensionAmount', monetary) or 0)
            data['Total Impuestos'] = float(get_text('cbc:TaxInclusiveAmount', monetary) or 0) - data['Base Imponible']
        return data
    except:
        return {"Archivo": archivo_xml.name, "Error": "Error XML"}

# ==============================================================================
# 6. INTERFAZ DE USUARIO (SIDEBAR & MENÚ)
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    st.markdown("### 🏢 Panel de Control")
    st.markdown("---")
    
    opciones_menu = [
        "🏠 Inicio / Quiénes Somos",
        "⚖️ Cruce DIAN vs Contabilidad",
        "📧 Lector XML (Facturación)",
        "🤝 Conciliador Bancario (IA)",
        "📂 Auditoría Masiva de Gastos",
        "👥 Escáner de Nómina (UGPP)",
        "💰 Tesorería & Flujo de Caja",
        "💰 Calculadora Costos (Masiva)",
        "📊 Analítica Financiera",
        "🔍 Validador de RUT (Real)",
        "📸 Digitalización (OCR)"
    ]
    
    menu = st.radio("Herramientas Profesionales:", opciones_menu)
    
    st.markdown("---")
    with st.expander("🔐 Configuración & Seguridad"):
        st.info("Pega aquí tu llave para activar el modo 'Cerebro IA':")
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)
    
    st.markdown("<br><center><small>v5.0 | Build 2025</small></center>", unsafe_allow_html=True)

# ==============================================================================
# 7. DESARROLLO DE PESTAÑAS (PÁGINAS)
# ==============================================================================

# ------------------------------------------------------------------------------
# 0. INICIO / QUIÉNES SOMOS
# ------------------------------------------------------------------------------
if menu == "🏠 Inicio / Quiénes Somos":
    st.markdown(f"# {icono_saludo} {saludo}, Colega.")
    st.markdown("### Bienvenido a tu Centro de Comando Contable Inteligente.")
    
    col_intro1, col_intro2 = st.columns([1.5, 1])
    
    with col_intro1:
        st.markdown("""
        <div class='instruccion-box' style='border-left: 4px solid #00d2ff;'>
            <h4>🚀 La Nueva Era Contable</h4>
            <p>Olvídate de la "carpintería". Esta suite ha sido diseñada para automatizar lo operativo y dejarte tiempo para lo estratégico.</p>
            <p><strong>Nuestra Filosofía:</strong> Menos clics, más análisis. Menos errores, más tranquilidad.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 🛠️ Herramientas de Alto Impacto:")
        c_tool1, c_tool2 = st.columns(2)
        with c_tool1:
            st.info("⚖️ **Cruce DIAN:** Compara lo que la DIAN sabe de ti vs. tu Contabilidad.")
            st.info("📧 **XML Miner:** Extrae datos de miles de facturas en segundos.")
        with c_tool2:
            st.info("🤝 **Bank Match:** Concilia bancos con IA.")
            st.info("🛡️ **Escudo Fiscal:** Audita gastos y nómina masivamente.")
        
    with col_intro2:
        st.markdown("""
        <div class='reporte-box'>
            <h4>💡 Workflow Recomendado</h4>
            <ol>
                <li>Descarga auxiliares de tu ERP (Siigo, World Office).</li>
                <li>Descarga el reporte de terceros de la DIAN.</li>
                <li>Usa el "Cruce DIAN" para detectar ingresos/costos omitidos.</li>
                <li>Usa "Escudo Fiscal" para auditar deducibilidad.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    st.subheader("🔑 Activación del Núcleo IA (Gratuito)")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>1. Acceso</h4>
        <p>Entra a Google AI Studio con tu cuenta Gmail.</p>
        <p><a href='https://aistudio.google.com/app/apikey' target='_blank'>🔗 Ir al sitio oficial</a></p>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>2. Creación</h4>
        <p>Busca el botón azul <strong>"Get API Key"</strong> y dale clic a "Create Key".</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>3. Conexión</h4>
        <p>Copia el código (AIza...) y pégalo en el menú lateral izquierdo.</p>
        </div>
        """, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# NUEVO: CRUCE DIAN VS CONTABILIDAD
# ------------------------------------------------------------------------------
elif menu == "⚖️ Cruce DIAN vs Contabilidad":
    st.header("⚖️ Auditor de Exógena (Cruce DIAN)")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 El "Detector de Mentiras" Fiscal</h4>
        <p>Esta herramienta es vital para el cierre contable. Compara la información que la DIAN tiene de ti (Reporte de Terceros) contra tu Contabilidad Interna. Detecta facturas que proveedores reportaron pero tú no causaste, o ingresos que olvidaste declarar.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_dian, col_conta = st.columns(2)
    with col_dian:
        st.subheader("🏛️ 1. Archivo DIAN")
        file_dian = st.file_uploader("Subir 'Reporte Terceros DIAN' (.xlsx)", type=['xlsx'])
    with col_conta:
        st.subheader("📒 2. Contabilidad")
        file_conta = st.file_uploader("Subir Auxiliar por Tercero (.xlsx)", type=['xlsx'])
        
    if file_dian and file_conta:
        df_dian = pd.read_excel(file_dian)
        df_conta = pd.read_excel(file_conta)
        
        st.write("---")
        st.subheader("⚙️ Mapeo de Columnas (NIT y Valor)")
        c1, c2, c3, c4 = st.columns(4)
        nit_dian = c1.selectbox("NIT (Archivo DIAN):", df_dian.columns)
        val_dian = c2.selectbox("Valor (Archivo DIAN):", df_dian.columns)
        nit_conta = c3.selectbox("NIT (Tu Contabilidad):", df_conta.columns)
        val_conta = c4.selectbox("Saldo (Tu Contabilidad):", df_conta.columns)
        
        if st.button("🔎 EJECUTAR CRUCE FISCAL"):
            # Agrupamos por NIT para tener totales por tercero
            dian_grouped = df_dian.groupby(nit_dian)[val_dian].sum().reset_index()
            dian_grouped.columns = ['NIT', 'Valor_DIAN']
            
            conta_grouped = df_conta.groupby(nit_conta)[val_conta].sum().reset_index()
            conta_grouped.columns = ['NIT', 'Valor_Conta']
            
            # Cruce (Merge)
            cruce = pd.merge(dian_grouped, conta_grouped, on='NIT', how='outer').fillna(0)
            cruce['Diferencia'] = cruce['Valor_DIAN'] - cruce['Valor_Conta']
            
            # Filtrar solo diferencias significativas
            diferencias = cruce[abs(cruce['Diferencia']) > 1000] # Umbral de $1.000 pesos
            
            st.success("Cruce Finalizado.")
            
            # Métricas
            m1, m2 = st.columns(2)
            m1.metric("Total Reportado DIAN", f"${cruce['Valor_DIAN'].sum():,.0f}")
            m2.metric("Total Tu Contabilidad", f"${cruce['Valor_Conta'].sum():,.0f}")
            
            if not diferencias.empty:
                st.error(f"⚠️ Se encontraron {len(diferencias)} terceros con diferencias significativas.")
                st.dataframe(diferencias.style.format("{:,.0f}"), use_container_width=True)
                
                # Descarga
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as w:
                    diferencias.to_excel(w, index=False)
                st.download_button("📥 Descargar Reporte de Diferencias", out.getvalue(), "Auditoria_Exogena.xlsx")
            else:
                st.balloons()
                st.success("✅ ¡Increíble! Tu contabilidad cuadra perfectamente con la DIAN.")

# ------------------------------------------------------------------------------
# 1. LECTOR XML
# ------------------------------------------------------------------------------
elif menu == "📧 Lector XML (Facturación)":
    st.header("📧 Minería de Datos XML (Facturación)")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Auditoría desde la Fuente</h4>
        <p>El PDF es solo una imagen. La verdad legal está en el XML. Arrastra aquí tus archivos de Facturación Electrónica para generar un reporte contable exacto en segundos.</p>
    </div>
    """, unsafe_allow_html=True)
    
    archivos_xml = st.file_uploader("Arrastra XMLs (Máx 5GB)", type=['xml'], accept_multiple_files=True)
    if archivos_xml and st.button("🚀 INICIAR EXTRACCIÓN MASIVA"):
        datos_xml = []
        barra = st.progress(0)
        for i, f in enumerate(archivos_xml):
            barra.progress((i+1)/len(archivos_xml))
            datos_xml.append(parsear_xml_dian(f))
        df_xml = pd.DataFrame(datos_xml)
        st.dataframe(df_xml, use_container_width=True)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as w: df_xml.to_excel(w, index=False)
        st.download_button("📥 Descargar Reporte Maestro (.xlsx)", out.getvalue(), "Resumen_XML.xlsx")

# ------------------------------------------------------------------------------
# 2. CONCILIADOR BANCARIO
# ------------------------------------------------------------------------------
elif menu == "🤝 Conciliador Bancario (IA)":
    st.header("🤝 Conciliación Bancaria Inteligente")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Cruce Automático</h4>
        <p>Sube tu extracto y tu libro auxiliar. El algoritmo buscará coincidencias por valor y fecha aproximada, identificando automáticamente las partidas pendientes.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_banco, col_libro = st.columns(2)
    with col_banco:
        st.subheader("🏦 Extracto Bancario")
        file_banco = st.file_uploader("Subir Excel Banco", type=['xlsx'])
    with col_libro:
        st.subheader("📒 Libro Auxiliar")
        file_libro = st.file_uploader("Subir Excel Contabilidad", type=['xlsx'])
    if file_banco and file_libro:
        df_banco = pd.read_excel(file_banco); df_libro = pd.read_excel(file_libro)
        c1, c2, c3, c4 = st.columns(4)
        col_fecha_b = c1.selectbox("Fecha Banco:", df_banco.columns, key="fb")
        col_valor_b = c2.selectbox("Valor Banco:", df_banco.columns, key="vb")
        col_fecha_l = c3.selectbox("Fecha Conta:", df_libro.columns, key="fl")
        col_valor_l = c4.selectbox("Valor Conta:", df_libro.columns, key="vl")
        col_desc_b = st.selectbox("Descripción Banco (Para detalle):", df_banco.columns, key="db")
        
        if st.button("🔄 EJECUTAR CONCILIACIÓN"):
            df_banco['Fecha_Dt'] = pd.to_datetime(df_banco[col_fecha_b])
            df_libro['Fecha_Dt'] = pd.to_datetime(df_libro[col_fecha_l])
            df_banco['Conciliado'] = False; df_libro['Conciliado'] = False
            matches = []
            bar = st.progress(0)
            for idx_b, row_b in df_banco.iterrows():
                bar.progress((idx_b+1)/len(df_banco))
                vb = row_b[col_valor_b]; fb = row_b['Fecha_Dt']
                cands = df_libro[(df_libro[col_valor_l] == vb) & (~df_libro['Conciliado']) & (df_libro['Fecha_Dt'].between(fb-timedelta(days=3), fb+timedelta(days=3)))]
                if not cands.empty:
                    df_banco.at[idx_b, 'Conciliado']=True; df_libro.at[cands.index[0], 'Conciliado']=True
                    matches.append({"Fecha": row_b[col_fecha_b], "Desc": row_b[col_desc_b], "Valor": vb, "Estado": "✅ OK"})
            
            st.success(f"Proceso finalizado. {len(matches)} partidas conciliadas automáticamente.")
            t1, t2, t3 = st.tabs(["✅ Partidas Cruzadas", "⚠️ Pendientes en Banco", "⚠️ Pendientes en Libros"])
            with t1: st.dataframe(pd.DataFrame(matches), use_container_width=True)
            with t2: st.dataframe(df_banco[~df_banco['Conciliado']], use_container_width=True)
            with t3: st.dataframe(df_libro[~df_libro['Conciliado']], use_container_width=True)

# ------------------------------------------------------------------------------
# 3. AUDITORÍA GASTOS
# ------------------------------------------------------------------------------
elif menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal Masiva")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Escudo Fiscal (Art. 771-5)</h4>
        <p>Analiza miles de filas de tu auxiliar de gastos. Detecta automáticamente pagos en efectivo que superan los topes y operaciones sin retención en la fuente.</p>
    </div>
    """, unsafe_allow_html=True)
    
    ar = st.file_uploader("Cargar Auxiliar de Gastos (.xlsx)", type=['xlsx'])
    if ar:
        df = pd.read_excel(ar)
        c1, c2, c3, c4 = st.columns(4)
        cf, ct, cc, cv = c1.selectbox("Fecha", df.columns), c2.selectbox("Tercero", df.columns), c3.selectbox("Concepto", df.columns), c4.selectbox("Valor", df.columns)
        cm = st.selectbox("Método de Pago", ["No disponible"]+list(df.columns))
        if st.button("🔍 AUDITAR AHORA"):
            res = []
            for r in df.to_dict('records'):
                met = r[cm] if cm != "No disponible" else "Efectivo"
                h, rs = analizar_gasto_fila(r, cv, cf, cc)
                v = float(r[cv]) if pd.notnull(r[cv]) else 0
                txt, rv = [], "BAJO"
                if "efectivo" in str(met).lower() and v > TOPE_EFECTIVO: txt.append("RECHAZO 771-5"); rv="ALTO"
                if v >= BASE_RET_SERVICIOS: txt.append("Posible Omisión Retención"); rv="MEDIO" if rv=="BAJO" else rv
                res.append({"Fila": r[cf], "Tercero": r[ct], "Valor": v, "Nivel Riesgo": rv, "Hallazgos": " ".join(txt)})
            st.dataframe(pd.DataFrame(res), use_container_width=True)

# ------------------------------------------------------------------------------
# 4. ESCÁNER NÓMINA UGPP
# ------------------------------------------------------------------------------
elif menu == "👥 Escáner de Nómina (UGPP)":
    st.header("👥 Escáner de Riesgo UGPP")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Ley 1393: Regla del 40%</h4>
        <p>Evita sanciones millonarias. Este módulo verifica empleado por empleado si los pagos no salariales exceden el límite permitido y calcula el ajuste exacto para la PILA.</p>
    </div>
    """, unsafe_allow_html=True)
    
    an = st.file_uploader("Cargar Nómina (.xlsx)", type=['xlsx'])
    if an:
        dn = pd.read_excel(an)
        c1, c2, c3 = st.columns(3)
        cn, cs, cns = c1.selectbox("Nombre Empleado", dn.columns), c2.selectbox("Salario Básico", dn.columns), c3.selectbox("Pagos No Salariales", dn.columns)
        if st.button("👮‍♀️ INICIAR INSPECCIÓN"):
            res = []
            for r in dn.to_dict('records'):
                ibc, exc, est, msg = calcular_ugpp_fila(r, cs, cns)
                res.append({"Empleado": r[cn], "Exceso a Cotizar": exc, "Estado": est})
            st.dataframe(pd.DataFrame(res), use_container_width=True)

# ------------------------------------------------------------------------------
# 5. TESORERÍA
# ------------------------------------------------------------------------------
elif menu == "💰 Tesorería & Flujo de Caja":
    st.header("💰 Radar de Liquidez 360°")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Proyección Financiera</h4>
        <p>Cruza tus cuentas por cobrar vs. cuentas por pagar y visualiza el futuro de tu caja. Detecta brechas de liquidez antes de que ocurran.</p>
    </div>
    """, unsafe_allow_html=True)
    
    saldo_hoy = st.number_input("💵 Saldo Disponible Hoy ($):", min_value=0.0, format="%.2f")
    c1, c2 = st.columns(2)
    fcxc = c1.file_uploader("Cartera (CxC)", type=['xlsx'])
    fcxp = c2.file_uploader("Proveedores (CxP)", type=['xlsx'])
    if fcxc and fcxp:
        dcxc = pd.read_excel(fcxc); dcxp = pd.read_excel(fcxp)
        c1, c2, c3, c4 = st.columns(4)
        cfc = c1.selectbox("Fecha Vencimiento CxC:", dcxc.columns); cvc = c2.selectbox("Valor CxC:", dcxc.columns)
        cfp = c3.selectbox("Fecha Vencimiento CxP:", dcxp.columns); cvp = c4.selectbox("Valor CxP:", dcxp.columns)
        if st.button("📈 GENERAR PROYECCIÓN"):
            try:
                dcxc['Fecha'] = pd.to_datetime(dcxc[cfc]); dcxp['Fecha'] = pd.to_datetime(dcxp[cfp])
                fi = dcxc.groupby('Fecha')[cvc].sum().reset_index(); fe = dcxp.groupby('Fecha')[cvp].sum().reset_index()
                cal = pd.merge(fi, fe, on='Fecha', how='outer').fillna(0)
                cal.columns = ['Fecha', 'Ingresos', 'Egresos']; cal = cal.sort_values('Fecha')
                cal['Saldo Proyectado'] = saldo_hoy + (cal['Ingresos'] - cal['Egresos']).cumsum()
                st.area_chart(cal.set_index('Fecha')['Saldo Proyectado'])
                st.dataframe(cal, use_container_width=True)
                if api_key:
                    with st.spinner("🤖 La IA está analizando tu flujo de caja..."):
                        st.markdown(consultar_ia_gemini(f"Analiza este flujo de caja. Saldo inicial: {saldo_hoy}. Datos: {cal.head(10).to_string()}"))
            except: st.error("Error en el formato de fechas. Asegúrate que sean columnas de fecha válidas.")

# ------------------------------------------------------------------------------
# 6. CALCULADORA COSTOS
# ------------------------------------------------------------------------------
elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Costeo Real de Nómina")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Presupuesto Laboral</h4>
        <p>Calcula el <strong>costo real empresa</strong> (Carga prestacional + Seguridad Social + Parafiscales) de toda tu planta de personal en un clic.</p>
    </div>
    """, unsafe_allow_html=True)
    
    ac = st.file_uploader("Cargar Listado Personal (.xlsx)", type=['xlsx'])
    if ac:
        dc = pd.read_excel(ac)
        c1, c2, c3, c4 = st.columns(4)
        cn, cs, ca, car = c1.selectbox("Nombre", dc.columns), c2.selectbox("Salario", dc.columns), c3.selectbox("Aux Trans (SI/NO)", dc.columns), c4.selectbox("Riesgo ARL (1-5)", dc.columns)
        ce = st.selectbox("Empresa Exonerada (SI/NO)", dc.columns)
        if st.button("🧮 CALCULAR COSTOS"):
            rc = []
            for r in dc.to_dict('records'):
                c, cr = calcular_costo_empresa_fila(r, cs, ca, car, ce)
                rc.append({"Empleado": r[cn], "Costo Total Mensual": c})
            st.dataframe(pd.DataFrame(rc), use_container_width=True)

# ------------------------------------------------------------------------------
# 7. ANALÍTICA
# ------------------------------------------------------------------------------
elif menu == "📊 Analítica Financiera":
    st.header("📊 Inteligencia Financiera IA")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Diagnóstico Automático</h4>
        <p>Sube un Balance de Comprobación o Libro Diario. La IA analizará patrones, tendencias y posibles riesgos financieros o tributarios.</p>
    </div>
    """, unsafe_allow_html=True)
    
    fi = st.file_uploader("Cargar Datos Financieros", type=['xlsx', 'csv'])
    if fi and api_key:
        df = pd.read_csv(fi) if fi.name.endswith('.csv') else pd.read_excel(fi)
        cd, cv = st.selectbox("Columna Descripción", df.columns), st.selectbox("Columna Valor", df.columns)
        if st.button("🤖 ANALIZAR CON IA"):
            res = df.groupby(cd)[cv].sum().sort_values(ascending=False).head(10)
            st.bar_chart(res)
            st.markdown(consultar_ia_gemini(f"Actúa como auditor financiero. Analiza estos saldos: {res.to_string()}"))

# ------------------------------------------------------------------------------
# 8. VALIDADOR RUT
# ------------------------------------------------------------------------------
elif menu == "🔍 Validador de RUT (Real)":
    st.header("🔍 Validador Oficial RUT")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Herramienta de Verificación</h4>
        <p>Calcula el Dígito de Verificación (DV) exacto usando el algoritmo oficial. Incluye acceso directo a la DIAN para verificar el estado del RUT.</p>
    </div>
    """, unsafe_allow_html=True)
    
    nit = st.text_input("Ingrese NIT o Cédula (Sin DV):", max_chars=15)
    if st.button("🔢 CALCULAR DV") and nit:
        dv = calcular_dv_colombia(nit)
        st.markdown(f"<div class='rut-card'><h2>NIT: {nit} - {dv}</h2><p>Dígito de Verificación Correcto</p></div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.link_button("🔗 Verificar Estado en Muisca (DIAN)", "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces")

# ------------------------------------------------------------------------------
# 9. OCR FACTURAS
# ------------------------------------------------------------------------------
elif menu == "📸 Digitalización (OCR)":
    st.header("📸 Digitalización de Facturas Físicas")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Del Papel al Excel</h4>
        <p>Utiliza visión artificial para extraer datos clave (NIT, Fecha, Total) de fotos o escaneos de facturas físicas.</p>
    </div>
    """, unsafe_allow_html=True)
    
    af = st.file_uploader("Cargar Imágenes", type=["jpg", "png"], accept_multiple_files=True)
    if af and st.button("🧠 PROCESAR IMÁGENES") and api_key:
        do = []
        bar = st.progress(0)
        for i, f in enumerate(af):
            bar.progress((i+1)/len(af)); info = ocr_factura(Image.open(f))
            if info: do.append(info)
        st.dataframe(pd.DataFrame(do), use_container_width=True)

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown("<center><strong>Asistente Contable Pro</strong> | Desarrollado para Contadores 4.0 | Bucaramanga, Colombia</center>", unsafe_allow_html=True)
