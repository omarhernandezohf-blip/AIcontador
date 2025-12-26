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
# 1. CONFIGURACIÓN VISUAL (OBLIGATORIO AL PRINCIPIO)
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="💼", layout="wide")

# ==============================================================================
# 2. CONEXIÓN A GOOGLE SHEETS (OPCIONAL/SEGURO)
# ==============================================================================
# Intentamos conectar solo si existen las credenciales en Secrets
gc = None
try:
    if "gcp_service_account" in st.secrets:
        credentials_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials_dict)
except Exception as e:
    pass # Si falla, la app sigue funcionando sin Sheets

# ==============================================================================
# 3. ESTILOS CSS PROFESIONALES (NUEVO DISEÑO)
# ==============================================================================
hora_actual = datetime.now().hour
if 5 <= hora_actual < 12:
    saludo = "Buenos días"
elif 12 <= hora_actual < 18:
    saludo = "Buenas tardes"
else:
    saludo = "Buenas noches"

st.markdown("""
    <style>
    /* --- FONDO Y TIPOGRAFÍA GLOBAL --- */
    .stApp {
        background-color: #0a0c10 !important; /* Fondo ligeramente más oscuro para contraste */
        color: #e0e0e0 !important;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* --- HERO HEADER (TÍTULO PRINCIPAL SOBREPUESTO) --- */
    .hero-header {
        /* Imagen de fondo abstracta financiera/tecnológica */
        background-image: linear-gradient(rgba(10, 12, 16, 0.8), rgba(10, 12, 16, 0.9)), url('https://img.freepik.com/free-photo/abstract-textured-backgound_1258-30550.jpg?w=1380&t=st=1703543355~exp=1703543955~hmac=c9d3179479704344876380490622400407340016315578003435033101545829');
        background-size: cover;
        background-position: center;
        padding: 60px 20px;
        border-radius: 15px;
        margin-bottom: 30px;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .hero-title {
        font-size: 3.5rem;
        font-weight: 900;
        color: #ffffff;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.7); /* Sombra para que el texto resalte */
        background: -webkit-linear-gradient(45deg, #ffffff, #a6c1ee); /* Degradado sutil en el texto blanco */
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-subtitle {
        font-size: 1.2rem;
        color: #b0b8c4;
        font-weight: 400;
    }

    /* --- ENCABEZADOS DE SECCIÓN CON ICONOS --- */
    .section-header-container {
        display: flex;
        align-items: center;
        margin-bottom: 20px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        padding-bottom: 10px;
    }
    .section-icon {
        width: 45px;
        height: 45px;
        margin-right: 15px;
        filter: drop-shadow(0px 4px 4px rgba(0,0,0,0.3)); /* Sombra realista al icono */
    }
    .section-title {
        font-size: 2rem;
        font-weight: 700;
        color: #f0f2f6;
        margin: 0;
    }

    /* --- TARJETAS (GLASSMORPHISM MEJORADO) --- */
    .instruccion-box, .rut-card, .reporte-box, .tutorial-step {
        background: rgba(30, 34, 45, 0.6) !important; /* Más transparente y oscuro */
        backdrop-filter: blur(15px); /* Mayor desenfoque */
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px; /* Bordes más redondeados */
        padding: 25px;
        margin-bottom: 25px;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); /* Transición más suave */
    }

    .instruccion-box:hover, .rut-card:hover, .reporte-box:hover, .tutorial-step:hover {
        transform: translateY(-8px);
        box-shadow: 0 15px 30px rgba(0,0,0,0.5);
        border-color: #3b82f6; /* Azul más corporativo */
    }

    .instruccion-box { border-left: 4px solid #3b82f6; }
    .instruccion-box h4, .reporte-box h4, .tutorial-step h4 { color: #ffffff !important; margin-top: 0; font-weight: 800; font-size: 1.1rem; }
    .instruccion-box p, .instruccion-box li, .reporte-box p { color: #a0aab8 !important; line-height: 1.6; }
    
    /* --- SIDEBAR --- */
    [data-testid="stSidebar"] {
        background-color: #0e1117;
        border-right: 1px solid rgba(255,255,255,0.05);
    }
    /* Personalizar los radio buttons del menú para que sean más limpios */
    .stRadio > div[role="radiogroup"] > label {
        background-color: transparent !important;
        border: none !important;
        padding-left: 10px !important;
        color: #a0aab8 !important;
        font-weight: 500 !important;
        transition: color 0.3s ease !important;
    }
    .stRadio > div[role="radiogroup"] > label:hover {
        color: #ffffff !important;
    }
    /* El elemento seleccionado en el menú */
    .stRadio > div[role="radiogroup"] > label[data-checked="true"] {
        color: #3b82f6 !important; /* Azul corporativo */
        font-weight: 700 !important;
    }


    /* --- BOTONES --- */
    .stButton>button {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important; /* Degradado diagonal más moderno */
        color: white !important;
        border-radius: 10px;
        font-weight: 700;
        border: none;
        height: 3.8em;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #60a5fa 0%, #2563eb 100%) !important;
        box-shadow: 0 8px 20px rgba(59, 130, 246, 0.5);
        transform: translateY(-2px);
    }

    /* --- ALERTAS Y MÉTRICAS --- */
    .metric-box-red { 
        background: linear-gradient(135deg, rgba(220, 38, 38, 0.2), rgba(153, 27, 27, 0.2)) !important;
        color: #fca5a5 !important; 
        padding: 20px; border-radius: 12px; text-align: center; border: 1px solid rgba(220, 38, 38, 0.3);
    }
    .metric-box-green { 
        background: linear-gradient(135deg, rgba(5, 150, 105, 0.2), rgba(4, 120, 87, 0.2)) !important;
        color: #6ee7b7 !important; 
        padding: 20px; border-radius: 12px; text-align: center; border: 1px solid rgba(5, 150, 105, 0.3);
    }
    
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0a0c10; }
    ::-webkit-scrollbar-thumb { background: #262b38; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #3b82f6; }
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
# 4. FUNCIONES DE LÓGICA DE NEGOCIO
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
# 5. INTERFAZ DE USUARIO (SIDEBAR & MENÚ PROFESIONAL)
# ==============================================================================
with st.sidebar:
    # Logo principal más serio (un maletín/escudo abstracto)
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830303.png", width=80)
    
    st.markdown("### 💼 Suite Financiera")
    st.markdown("---")
    
    # MENÚ LIMPIO SIN EMOJIS (TIPOGRAFÍA PROFESIONAL)
    opciones_menu = [
        "Inicio / Quiénes Somos",
        "Cruce DIAN vs Contabilidad",
        "Lector XML (Facturación)",
        "Conciliador Bancario (IA)",
        "Auditoría Masiva de Gastos",
        "Escáner de Nómina (UGPP)",
        "Tesorería & Flujo de Caja",
        "Calculadora Costos (Masiva)",
        "Analítica Financiera",
        "Reportes Gerenciales & Notas NIIF",
        "Validador de RUT (Real)",
        "Digitalización (OCR)"
    ]
    
    # El estilo CSS se encarga de que este menú se vea limpio y corporativo
    menu = st.radio("Módulos Operativos:", opciones_menu)
    
    st.markdown("---")
    with st.expander("🔐 Configuración & Seguridad"):
        st.info("Pega aquí tu llave para activar el modo 'Cerebro IA':")
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)
    
    st.markdown("<br><center><small style='color: #6b7280;'>v9.0 Enterprise | Build 2025</small></center>", unsafe_allow_html=True)

# ==============================================================================
# 6. DESARROLLO DE PESTAÑAS (PÁGINAS CON NUEVOS ENCABEZADOS REALISTAS)
# ==============================================================================

# ------------------------------------------------------------------------------
# 0. INICIO / QUIÉNES SOMOS (HERO HEADER)
# ------------------------------------------------------------------------------
if menu == "Inicio / Quiénes Somos":
    # HERO HEADER SOBREPUESTO Y VISIBLE
    st.markdown(f"""
    <div class='hero-header'>
        <h1 class='hero-title'>Asistente Contable Pro 2025</h1>
        <p class='hero-subtitle'>{saludo}. Tu Centro de Comando Financiero Inteligente.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_intro1, col_intro2 = st.columns([1.5, 1])
    
    with col_intro1:
        st.markdown("""
        <div class='instruccion-box' style='border-left: 4px solid #3b82f6;'>
            <h4>🚀 La Nueva Era Contable</h4>
            <p>Olvídate de la "carpintería". Esta suite Enterprise ha sido diseñada para automatizar lo operativo y dejarte tiempo para lo estratégico.</p>
            <p><strong>Nuestra Filosofía:</strong> Precisión, velocidad y análisis profundo.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 🛠️ Herramientas de Alto Impacto:")
        c_tool1, c_tool2 = st.columns(2)
        with c_tool1:
            st.info("⚖️ **Auditoría Fiscal:** Cruces automáticos DIAN.")
            st.info("📧 **Minería XML:** Extracción masiva de datos.")
        with c_tool2:
            st.info("🤝 **Conciliación IA:** Matching bancario inteligente.")
            st.info("📈 **Reportes NIIF:** Redacción automática experta.")
        
    with col_intro2:
        st.markdown("""
        <div class='reporte-box'>
            <h4>💡 Workflow Recomendado</h4>
            <ol>
                <li>Descarga auxiliares de tu ERP (Siigo, World Office).</li>
                <li>Descarga el reporte de terceros de la DIAN.</li>
                <li>Ejecuta el "Cruce DIAN" para detectar inconsistencias.</li>
                <li>Genera "Reportes NIIF" para el cierre final.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    st.subheader("🔑 Activación del Núcleo IA (Tutorial)")
    
    # Video Tutorial (Se mantiene)
    st.video("https://www.youtube.com/watch?v=dHn3d66Qppw")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>1. Acceso Seguro</h4>
        <p>Entra a Google AI Studio con tu cuenta corporativa.</p>
        <p><a href='https://aistudio.google.com/app/apikey' target='_blank'>🔗 Ir al sitio oficial</a></p>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>2. Generación de Llave</h4>
        <p>Haz clic en el botón azul <strong>"Get API Key"</strong> y luego en "Create Key".</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>3. Conexión Segura</h4>
        <p>Copia el código (AIza...) y pégalo en el menú lateral izquierdo.</p>
        </div>
        """, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 1. CRUCE DIAN VS CONTABILIDAD
# ------------------------------------------------------------------------------
elif menu == "Cruce DIAN vs Contabilidad":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/2942/2942883.png' class='section-icon'>
        <h2 class='section-title'>Auditor de Exógena (Cruce DIAN)</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 El "Detector de Mentiras" Fiscal</h4>
        <p>Herramienta vital para el cierre. Compara la información reportada por terceros a la DIAN contra tu Contabilidad Interna para detectar omisiones o inconsistencias.</p>
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
            dian_grouped = df_dian.groupby(nit_dian)[val_dian].sum().reset_index()
            dian_grouped.columns = ['NIT', 'Valor_DIAN']
            
            conta_grouped = df_conta.groupby(nit_conta)[val_conta].sum().reset_index()
            conta_grouped.columns = ['NIT', 'Valor_Conta']
            
            cruce = pd.merge(dian_grouped, conta_grouped, on='NIT', how='outer').fillna(0)
            cruce['Diferencia'] = cruce['Valor_DIAN'] - cruce['Valor_Conta']
            
            diferencias = cruce[abs(cruce['Diferencia']) > 1000] # Umbral de $1.000 pesos
            
            st.success("Cruce Finalizado.")
            
            m1, m2 = st.columns(2)
            m1.metric("Total Reportado DIAN", f"${cruce['Valor_DIAN'].sum():,.0f}")
            m2.metric("Total Tu Contabilidad", f"${cruce['Valor_Conta'].sum():,.0f}")
            
            if not diferencias.empty:
                st.error(f"⚠️ Se encontraron {len(diferencias)} terceros con diferencias significativas.")
                st.dataframe(diferencias.style.format("{:,.0f}"), use_container_width=True)
                
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as w:
                    diferencias.to_excel(w, index=False)
                st.download_button("📥 Descargar Reporte de Diferencias", out.getvalue(), "Auditoria_Exogena.xlsx")
            else:
                st.balloons()
                st.success("✅ ¡Increíble! Tu contabilidad cuadra perfectamente con la DIAN.")

# ------------------------------------------------------------------------------
# 2. LECTOR XML
# ------------------------------------------------------------------------------
elif menu == "Lector XML (Facturación)":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/8050/8050934.png' class='section-icon'>
        <h2 class='section-title'>Minería de Datos XML (Facturación)</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Auditoría desde la Fuente Legal</h4>
        <p>La verdad fiscal está en el XML, no en el PDF. Procesa masivamente tus archivos de Facturación Electrónica para generar un reporte contable exacto en segundos.</p>
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
# 3. CONCILIADOR BANCARIO
# ------------------------------------------------------------------------------
elif menu == "Conciliador Bancario (IA)":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/2168/2168678.png' class='section-icon'>
        <h2 class='section-title'>Conciliación Bancaria Inteligente</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Cruce Automático Asistido</h4>
        <p>Sube tu extracto y tu libro auxiliar. El algoritmo buscará coincidencias por valor y fechas aproximadas, identificando automáticamente las partidas pendientes.</p>
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
# 4. AUDITORÍA GASTOS
# ------------------------------------------------------------------------------
elif menu == "Auditoría Masiva de Gastos":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/9689/9689029.png' class='section-icon'>
        <h2 class='section-title'>Auditoría Fiscal Masiva (Art. 771-5)</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Escudo Fiscal Automatizado</h4>
        <p>Analiza miles de filas de tu auxiliar de gastos. Detecta automáticamente pagos en efectivo que superan los topes legales y operaciones con riesgo de no deducibilidad.</p>
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
# 5. ESCÁNER NÓMINA UGPP
# ------------------------------------------------------------------------------
elif menu == "Escáner de Nómina (UGPP)":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/3135/3135707.png' class='section-icon'>
        <h2 class='section-title'>Escáner de Riesgo UGPP</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Ley 1393: Control del 40%</h4>
        <p>Evita sanciones onerosas. Este módulo verifica empleado por empleado si los pagos no salariales exceden el límite permitido y calcula el ajuste exacto para la PILA.</p>
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
# 6. TESORERÍA
# ------------------------------------------------------------------------------
elif menu == "Tesorería & Flujo de Caja":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/781/781831.png' class='section-icon'>
        <h2 class='section-title'>Radar de Liquidez & Tesorería</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Proyección Financiera 360°</h4>
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
# 7. CALCULADORA COSTOS
# ------------------------------------------------------------------------------
elif menu == "Calculadora Costos (Masiva)":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/1553/1553075.png' class='section-icon'>
        <h2 class='section-title'>Calculadora de Costo Real de Nómina</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Presupuesto Laboral Exacto</h4>
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
# 8. ANALÍTICA
# ------------------------------------------------------------------------------
elif menu == "Analítica Financiera":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/9815/9815644.png' class='section-icon'>
        <h2 class='section-title'>Inteligencia Financiera (IA)</h2>
    </div>
    """, unsafe_allow_html=True)

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
# 9. NARRADOR FINANCIERO & NOTAS NIIF (IA)
# ------------------------------------------------------------------------------
elif menu == "Reportes Gerenciales & Notas NIIF":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/3004/3004543.png' class='section-icon'>
        <h2 class='section-title'>Narrador Financiero & Notas NIIF</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='instruccion-box' style='border-left: 4px solid #ad00ff;'>
        <h4>💡 Financial Storytelling Automatizado</h4>
        <p>No entregues solo números. Esta herramienta analiza tus Estados Financieros comparativos, detecta las variaciones más críticas y <strong>redacta automáticamente</strong> el informe para la Gerencia y las Notas de Revelación bajo NIIF.</p>
    </div>
    """, unsafe_allow_html=True)

    # Carga de archivos comparativos
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📅 Año Actual (2025)")
        file_actual = st.file_uploader("Cargar Balance/P&G Año Actual", type=['xlsx'])
    with col2:
        st.subheader("📅 Año Anterior (2024)")
        file_anterior = st.file_uploader("Cargar Balance/P&G Año Anterior", type=['xlsx'])

    if file_actual and file_anterior:
        try:
            df_act = pd.read_excel(file_actual)
            df_ant = pd.read_excel(file_anterior)
            
            st.write("---")
            st.subheader("⚙️ Configuración del Análisis")
            c1, c2, c3 = st.columns(3)
            # Asumimos que el usuario selecciona la cuenta y el valor
            col_cuenta = c1.selectbox("Columna 'Cuenta Contable':", df_act.columns)
            col_valor_act = c2.selectbox("Valor Año Actual:", df_act.columns)
            col_valor_ant = c3.selectbox("Valor Año Anterior:", df_ant.columns)

            if st.button("✨ GENERAR INFORME INTELIGENTE") and api_key:
                # 1. Preparación de Datos (Programación)
                # Unimos los dos dataframes por la cuenta contable
                df_act = df_act.groupby(col_cuenta)[col_valor_act].sum().reset_index()
                df_ant = df_ant.groupby(col_cuenta)[col_valor_ant].sum().reset_index()
                
                merged = pd.merge(df_act, df_ant, on=col_cuenta, how='inner').fillna(0)
                merged['Variacion_Abs'] = merged[col_valor_act] - merged[col_valor_ant]
                merged['Variacion_Rel'] = (merged['Variacion_Abs'] / merged[col_valor_ant]).replace([float('inf'), -float('inf')], 0) * 100
                
                # Filtramos las variaciones más significativas (Top 5 subidas y bajadas) para no saturar a la IA
                top_variaciones = merged.reindex(merged.Variacion_Abs.abs().sort_values(ascending=False).index).head(10)

                # 2. Visualización de Alto Impacto (Diseño)
                st.markdown("### 📊 Tablero de Control Gerencial")
                
                # KPIs Principales
                # Intentamos identificar ingresos y gastos por convención contable (Clase 4 y 5)
                # Convertimos a string para buscar el prefijo
                ingresos_act = merged[merged[col_cuenta].astype(str).str.startswith('4', na=False)][col_valor_act].sum()
                gastos_act = merged[merged[col_cuenta].astype(str).str.startswith('5', na=False)][col_valor_act].sum()
                utilidad = ingresos_act - gastos_act # Simplificado
                
                k1, k2, k3 = st.columns(3)
                k1.markdown(f"<div class='metric-box-green'><h3>Ingresos</h3><p>${ingresos_act:,.0f}</p></div>", unsafe_allow_html=True)
                k2.markdown(f"<div class='metric-box-red'><h3>Gastos</h3><p>${gastos_act:,.0f}</p></div>", unsafe_allow_html=True)
                k3.markdown(f"<div class='rut-card' style='text-align:center'><h3>Utilidad Aprox</h3><p>${utilidad:,.0f}</p></div>", unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Gráfica de Variaciones
                st.subheader("📉 Variaciones Significativas (Análisis Horizontal)")
                st.bar_chart(top_variaciones.set_index(col_cuenta)['Variacion_Abs'])

                # 3. Inteligencia Artificial (Contabilidad Experta)
                st.subheader("🧠 Análisis Cualitativo & Notas NIIF")
                
                with st.spinner("🤖 El Consultor IA está redactando el informe..."):
                    # Prompt de Ingeniería Avanzada
                    prompt = f"""
                    Actúa como un Contador Senior experto en NIIF y Análisis Financiero.
                    Analiza la siguiente tabla de variaciones contables entre el año anterior y el actual:
                    {top_variaciones.to_string()}

                    GENERA DOS SALIDAS:
                    1. UN INFORME GERENCIAL: Explicando en lenguaje de negocios (claro y directo para el dueño de la empresa) qué pasó con el dinero. Usa tono profesional pero empático. Enfócate en las causas probables de las variaciones grandes.
                    2. BORRADOR DE NOTAS A LOS ESTADOS FINANCIEROS: Redacta la nota de revelación técnica bajo norma NIIF PYMES para las 3 cuentas con mayor variación, justificando la materialidad.
                    
                    Usa formato Markdown profesional.
                    """
                    
                    respuesta_ia = consultar_ia_gemini(prompt)
                    st.markdown(respuesta_ia)
                    
                    # Botón de descarga del texto
                    st.download_button("📥 Descargar Informe (.txt)", respuesta_ia, "Informe_Gerencial_NIIF.txt")

        except Exception as e:
            st.error(f"Error procesando los archivos: {e}. Asegúrate de que las columnas tengan nombres similares y códigos contables.")

# ------------------------------------------------------------------------------
# 10. VALIDADOR RUT
# ------------------------------------------------------------------------------
elif menu == "Validador de RUT (Real)":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/3588/3588337.png' class='section-icon'>
        <h2 class='section-title'>Validador Oficial de RUT</h2>
    </div>
    """, unsafe_allow_html=True)

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
# 11. OCR FACTURAS
# ------------------------------------------------------------------------------
elif menu == "Digitalización (OCR)":
    # ENCABEZADO REALISTA 3D
    st.markdown("""
    <div class='section-header-container'>
        <img src='https://cdn-icons-png.flaticon.com/512/6840/6840264.png' class='section-icon'>
        <h2 class='section-title'>Digitalización Inteligente (OCR)</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Del Papel al Excel con IA</h4>
        <p>Utiliza visión artificial de última generación para extraer datos clave (NIT, Fecha, Total) de fotos o escaneos de facturas físicas.</p>
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
st.markdown("<center><strong>Asistente Contable Pro Enterprise</strong> | Bucaramanga, Colombia | © 2025</center>", unsafe_allow_html=True)
