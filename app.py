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
# 1. CONFIGURACIÓN VISUAL
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="💼", layout="wide")

# ==============================================================================
# 2. CONEXIÓN A GOOGLE SHEETS (OPCIONAL)
# ==============================================================================
gc = None
try:
    if "gcp_service_account" in st.secrets:
        credentials_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials_dict)
except Exception:
    pass

# ==============================================================================
# 3. ESTILOS Y CONSTANTES (MODIFICADO PARA IMÁGENES REALISTAS)
# ==============================================================================
hora_actual = datetime.now().hour
# Seleccionamos imágenes profesionales y realistas según la hora
if 5 <= hora_actual < 12:
    saludo_texto = "Buenos días"
    # Imagen de oficina luminosa por la mañana
    banner_img = "https://images.unsplash.com/photo-1497366754035-48c702a7cec3?ixlib=rb-4.0.3&auto=format&fit=crop&w=1470&q=80"
elif 12 <= hora_actual < 18:
    saludo_texto = "Buenas tardes"
    # Imagen de distrito financiero activo
    banner_img = "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?ixlib=rb-4.0.3&auto=format&fit=crop&w=1470&q=80"
else:
    saludo_texto = "Buenas noches"
    # Imagen de ciudad y oficina de noche
    banner_img = "https://images.unsplash.com/photo-1497215728101-856f4ea42174?ixlib=rb-4.0.3&auto=format&fit=crop&w=1470&q=80"

st.markdown("""
    <style>
    /* --- FONDO Y TIPOGRAFÍA --- */
    .stApp {
        background-color: #0e1117 !important;
        color: #e0e0e0 !important;
    }
    html, body, [class*="css"] {
        font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    }

    /* --- NUEVO: BANNERS REALISTAS CON TEXTO SUPERPUESTO --- */
    .banner-container {
        position: relative;
        text-align: center;
        color: white;
        margin-bottom: 30px;
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 15px 30px rgba(0,0,0,0.5);
    }
    .banner-image {
        width: 100%;
        height: 280px; /* Altura fija para el banner */
        object-fit: cover;
        filter: brightness(50%); /* Oscurecer la imagen para que el texto resalte */
    }
    .banner-text {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 95%;
    }
    .banner-text h1 {
        font-size: 3.8rem;
        font-weight: 900;
        letter-spacing: -1px;
        text-shadow: 2px 2px 10px rgba(0,0,0,0.9); /* Sombra fuerte para visibilidad */
        margin: 0;
        color: white !important;
        background: none !important; /* Quitamos el degradado anterior en el banner */
        -webkit-text-fill-color: white !important;
    }
    .banner-text p {
        font-size: 1.6rem;
        font-weight: 500;
        text-shadow: 1px 1px 5px rgba(0,0,0,0.9);
        margin-top: 10px;
        color: #e0e0e0;
    }

    /* --- TÍTULOS ESTÁNDAR (Fuera del banner) --- */
    h2, h3 { color: #f0f2f6 !important; font-weight: 700; }
    
    /* --- TARJETAS (GLASSMORPHISM) --- */
    .instruccion-box, .rut-card, .reporte-box, .tutorial-step {
        background: rgba(38, 39, 48, 0.8) !important; /* Un poco más opaco para seriedad */
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 25px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }

    .instruccion-box:hover, .rut-card:hover, .reporte-box:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 25px rgba(0,0,0,0.5);
        border-color: #0d6efd;
    }

    .instruccion-box { border-left: 4px solid #0d6efd; }
    .instruccion-box h4 { color: #0d6efd !important; margin-top: 0; font-weight: bold; font-size: 1.2rem;}
    
    /* --- BOTONES --- */
    .stButton>button {
        background: linear-gradient(90deg, #0d6efd 0%, #004494 100%) !important; /* Degradado más serio */
        color: white !important;
        border-radius: 6px; /* Bordes menos redondeados */
        font-weight: 600;
        border: none;
        height: 3.5em;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        text-transform: uppercase; /* Texto en mayúsculas para seriedad */
        letter-spacing: 1px;
    }
    
    .stButton>button:hover {
        background: linear-gradient(90deg, #0b5ed7 0%, #003370 100%) !important;
        box-shadow: 0 6px 12px rgba(13, 110, 253, 0.5);
        transform: scale(1.01);
    }

    /* --- ALERTAS --- */
    .metric-box-red { background: rgba(62, 18, 22, 0.9) !important; color: #ffaeb6 !important; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #842029; }
    .metric-box-green { background: rgba(15, 41, 30, 0.9) !important; color: #a3cfbb !important; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #0f5132; }
    
    ::-webkit-scrollbar { width: 10px; }
    ::-webkit-scrollbar-track { background: #0e1117; }
    ::-webkit-scrollbar-thumb { background: #303030; border-radius: 5px; }
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
# 5. INTERFAZ DE USUARIO (SIDEBAR & MENÚ)
# ==============================================================================
with st.sidebar:
    # Icono más profesional y realista (estilo 3D/empresarial)
    st.image("https://cdn-icons-png.flaticon.com/512/5360/5360938.png", width=85)
    
    st.markdown("### 💼 Suite Financiera Pro")
    st.markdown("---")
    
    opciones_menu = [
        "🏠 Inicio / Dashboard",
        "⚖️ Cruce DIAN vs Contabilidad",
        "📧 Lector XML (Facturación)",
        "🤝 Conciliador Bancario (IA)",
        "📂 Auditoría Masiva de Gastos",
        "👥 Escáner de Nómina (UGPP)",
        "💰 Tesorería & Flujo de Caja",
        "💰 Calculadora Costos (Masiva)",
        "📊 Analítica Financiera",
        "📈 Reportes Gerenciales & Notas NIIF (IA)",
        "🔍 Validador de RUT (Real)",
        "📸 Digitalización (OCR)"
    ]
    
    menu = st.radio("Módulos Operativos:", opciones_menu)
    
    st.markdown("---")
    with st.expander("🔐 Configuración & Seguridad"):
        st.info("Introduce tu API Key para activar el análisis avanzado con IA:")
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)
    
    st.markdown("<br><center><small>v8.2 | Enterprise Edition 2025</small></center>", unsafe_allow_html=True)

# ==============================================================================
# 6. DESARROLLO DE PESTAÑAS (PÁGINAS)
# ==============================================================================

# ------------------------------------------------------------------------------
# 0. INICIO / DASHBOARD (NUEVO BANNER REALISTA)
# ------------------------------------------------------------------------------
if menu == "🏠 Inicio / Dashboard":
    # Inserción del Banner Realista con Texto Superpuesto
    st.markdown(f"""
        <div class="banner-container">
            <img src="{banner_img}" class="banner-image">
            <div class="banner-text">
                <h1>{saludo_texto}, Colega.</h1>
                <p>Bienvenido a tu Centro de Comando Contable Profesional</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col_intro1, col_intro2 = st.columns([1.5, 1])
    
    with col_intro1:
        st.markdown("""
        <div class='instruccion-box' style='border-left: 4px solid #0d6efd;'>
            <h4>🚀 Eficiencia Estratégica</h4>
            <p>Esta suite ha sido diseñada para automatizar la carga operativa y permitir un enfoque en el análisis financiero estratégico.</p>
            <p><strong>Filosofía:</strong> Precisión, automatización y análisis profundo.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 🛠️ Herramientas Clave:")
        c_tool1, c_tool2 = st.columns(2)
        with c_tool1:
            st.info("**Cruce DIAN:** Auditoría fiscal comparativa.")
            st.info("**XML Miner:** Extracción masiva de datos.")
        with c_tool2:
            st.info("**Bank Match IA:** Conciliación inteligente.")
            st.info("**Notas NIIF:** Redacción automática de reportes.")
        
    with col_intro2:
        st.markdown("""
        <div class='reporte-box'>
            <h4>💡 Flujo de Trabajo Recomendado</h4>
            <ol>
                <li>Carga de auxiliares ERP.</li>
                <li>Descarga de información exógena DIAN.</li>
                <li>Ejecución de Cruce y Auditoría de Gastos.</li>
                <li>Generación de Reportes y Notas NIIF.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    st.subheader("🔑 Activación del Núcleo IA")
    
    # Video Tutorial
    st.video("https://www.youtube.com/watch?v=dHn3d66Qppw")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>1. Acceso Seguro</h4>
        <p>Ingresa a Google AI Studio.</p>
        <p><a href='https://aistudio.google.com/app/apikey' target='_blank'>🔗 Sitio Oficial</a></p>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>2. Generación de Llave</h4>
        <p>Crea una nueva API Key en el panel.</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>3. Conexión</h4>
        <p>Ingresa el código en el panel lateral de seguridad.</p>
        </div>
        """, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 1. CRUCE DIAN VS CONTABILIDAD
# ------------------------------------------------------------------------------
elif menu == "⚖️ Cruce DIAN vs Contabilidad":
    st.header("⚖️ Auditor de Exógena (Cruce DIAN)")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Auditoría Fiscal Comparativa</h4>
        <p>Compara la información reportada por terceros a la DIAN contra la contabilidad interna para detectar inconsistencias, pasivos omitidos o ingresos no declarados.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_dian, col_conta = st.columns(2)
    with col_dian:
        st.subheader("🏛️ 1. Archivo DIAN (XLSX)")
        file_dian = st.file_uploader("Cargar Reporte Terceros", type=['xlsx'])
    with col_conta:
        st.subheader("📒 2. Contabilidad Interna (XLSX)")
        file_conta = st.file_uploader("Cargar Auxiliar por Tercero", type=['xlsx'])
        
    if file_dian and file_conta:
        df_dian = pd.read_excel(file_dian)
        df_conta = pd.read_excel(file_conta)
        
        st.write("---")
        st.subheader("⚙️ Mapeo de Datos")
        c1, c2, c3, c4 = st.columns(4)
        nit_dian = c1.selectbox("NIT (Archivo DIAN):", df_dian.columns)
        val_dian = c2.selectbox("Valor (Archivo DIAN):", df_dian.columns)
        nit_conta = c3.selectbox("NIT (Contabilidad):", df_conta.columns)
        val_conta = c4.selectbox("Saldo (Contabilidad):", df_conta.columns)
        
        if st.button("🔎 EJECUTAR AUDITORÍA FISCAL"):
            dian_grouped = df_dian.groupby(nit_dian)[val_dian].sum().reset_index()
            dian_grouped.columns = ['NIT', 'Valor_DIAN']
            
            conta_grouped = df_conta.groupby(nit_conta)[val_conta].sum().reset_index()
            conta_grouped.columns = ['NIT', 'Valor_Conta']
            
            cruce = pd.merge(dian_grouped, conta_grouped, on='NIT', how='outer').fillna(0)
            cruce['Diferencia'] = cruce['Valor_DIAN'] - cruce['Valor_Conta']
            
            diferencias = cruce[abs(cruce['Diferencia']) > 1000] # Umbral de materialidad
            
            st.success("Auditoría Finalizada.")
            
            m1, m2 = st.columns(2)
            m1.metric("Total Reportado DIAN", f"${cruce['Valor_DIAN'].sum():,.0f}")
            m2.metric("Total Contabilidad", f"${cruce['Valor_Conta'].sum():,.0f}")
            
            if not diferencias.empty:
                st.error(f"⚠️ Se encontraron {len(diferencias)} terceros con diferencias materiales.")
                st.dataframe(diferencias.style.format("{:,.0f}"), use_container_width=True)
                
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as w:
                    diferencias.to_excel(w, index=False)
                st.download_button("📥 Descargar Informe de Diferencias", out.getvalue(), "Auditoria_Exogena.xlsx")
            else:
                st.balloons()
                st.success("✅ Sin hallazgos. La contabilidad concilia con la información exógena.")

# ------------------------------------------------------------------------------
# 2. LECTOR XML
# ------------------------------------------------------------------------------
elif menu == "📧 Lector XML (Facturación)":
    st.header("📧 Minería de Datos XML (Facturación Electrónica)")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Extracción de Datos Fuente</h4>
        <p>Procesamiento masivo de archivos XML de facturación electrónica para generar reportes contables exactos directamente desde la fuente legal.</p>
    </div>
    """, unsafe_allow_html=True)
    
    archivos_xml = st.file_uploader("Cargar Archivos XML (Máx 5GB)", type=['xml'], accept_multiple_files=True)
    if archivos_xml and st.button("🚀 INICIAR PROCESAMIENTO MASIVO"):
        datos_xml = []
        barra = st.progress(0)
        for i, f in enumerate(archivos_xml):
            barra.progress((i+1)/len(archivos_xml))
            datos_xml.append(parsear_xml_dian(f))
        df_xml = pd.DataFrame(datos_xml)
        st.dataframe(df_xml, use_container_width=True)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as w: df_xml.to_excel(w, index=False)
        st.download_button("📥 Descargar Reporte Maestro (.xlsx)", out.getvalue(), "Resumen_XML_Facturacion.xlsx")

# ------------------------------------------------------------------------------
# 3. CONCILIADOR BANCARIO
# ------------------------------------------------------------------------------
elif menu == "🤝 Conciliador Bancario (IA)":
    st.header("🤝 Conciliación Bancaria Inteligente")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Automatización de Cruces</h4>
        <p>Algoritmo de emparejamiento automático entre extractos bancarios y libros auxiliares basado en valores y rangos de fechas flexibles.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_banco, col_libro = st.columns(2)
    with col_banco:
        st.subheader("🏦 Extracto Bancario (XLSX)")
        file_banco = st.file_uploader("Cargar Extracto", type=['xlsx'])
    with col_libro:
        st.subheader("📒 Libro Auxiliar Bancos (XLSX)")
        file_libro = st.file_uploader("Cargar Libro Auxiliar", type=['xlsx'])
    if file_banco and file_libro:
        df_banco = pd.read_excel(file_banco); df_libro = pd.read_excel(file_libro)
        c1, c2, c3, c4 = st.columns(4)
        col_fecha_b = c1.selectbox("Fecha Banco:", df_banco.columns, key="fb")
        col_valor_b = c2.selectbox("Valor Banco:", df_banco.columns, key="vb")
        col_fecha_l = c3.selectbox("Fecha Libro:", df_libro.columns, key="fl")
        col_valor_l = c4.selectbox("Valor Libro:", df_libro.columns, key="vl")
        col_desc_b = st.selectbox("Descripción Banco (Para detalle):", df_banco.columns, key="db")
        
        if st.button("🔄 EJECUTAR CONCILIACIÓN AUTOMÁTICA"):
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
elif menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal de Gastos (Art. 771-5)")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Verificación de Deducibilidad</h4>
        <p>Análisis masivo del auxiliar de gastos para detectar riesgos fiscales: pagos en efectivo superiores a los topes legales y operaciones sin bases de retención mínimas.</p>
    </div>
    """, unsafe_allow_html=True)
    
    ar = st.file_uploader("Cargar Auxiliar de Gastos (.xlsx)", type=['xlsx'])
    if ar:
        df = pd.read_excel(ar)
        c1, c2, c3, c4 = st.columns(4)
        cf, ct, cc, cv = c1.selectbox("Columna Fecha", df.columns), c2.selectbox("Columna Tercero", df.columns), c3.selectbox("Columna Concepto", df.columns), c4.selectbox("Columna Valor", df.columns)
        cm = st.selectbox("Columna Método de Pago (Opcional)", ["No disponible"]+list(df.columns))
        if st.button("🔍 EJECUTAR AUDITORÍA FISCAL"):
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
elif menu == "👥 Escáner de Nómina (Riesgo UGPP)":
    st.header("👥 Escáner de Riesgo UGPP (Ley 1393)")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Verificación Regla del 40%</h4>
        <p>Auditoría de nómina para validar el cumplimiento del límite de pagos no salariales y calcular los ajustes requeridos en el IBC de la PILA.</p>
    </div>
    """, unsafe_allow_html=True)
    
    an = st.file_uploader("Cargar Archivo de Nómina (.xlsx)", type=['xlsx'])
    if an:
        dn = pd.read_excel(an)
        c1, c2, c3 = st.columns(3)
        cn, cs, cns = c1.selectbox("Columna Empleado", dn.columns), c2.selectbox("Columna Salario Básico", dn.columns), c3.selectbox("Columna Total No Salarial", dn.columns)
        if st.button("👮‍♀️ INICIAR INSPECCIÓN UGPP"):
            res = []
            for r in dn.to_dict('records'):
                ibc, exc, est, msg = calcular_ugpp_fila(r, cs, cns)
                res.append({"Empleado": r[cn], "Exceso a Cotizar (Ajuste IBC)": exc, "Estado": est, "Detalle": msg})
            st.dataframe(pd.DataFrame(res), use_container_width=True)

# ------------------------------------------------------------------------------
# 6. TESORERÍA
# ------------------------------------------------------------------------------
elif menu == "💰 Tesorería & Flujo de Caja":
    st.header("💰 Proyección de Flujo de Caja")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Radar de Liquidez</h4>
        <p>Proyección financiera basada en el cruce de cuentas por cobrar y cuentas por pagar para identificar brechas de liquidez futuras.</p>
    </div>
    """, unsafe_allow_html=True)
    
    saldo_hoy = st.number_input("💵 Saldo Disponible en Bancos Hoy ($):", min_value=0.0, format="%.2f")
    c1, c2 = st.columns(2)
    fcxc = c1.file_uploader("Cargar Cartera (CxC)", type=['xlsx'])
    fcxp = c2.file_uploader("Cargar Proveedores (CxP)", type=['xlsx'])
    if fcxc and fcxp:
        dcxc = pd.read_excel(fcxc); dcxp = pd.read_excel(fcxp)
        c1, c2, c3, c4 = st.columns(4)
        cfc = c1.selectbox("Fecha Vcto CxC:", dcxc.columns); cvc = c2.selectbox("Valor CxC:", dcxc.columns)
        cfp = c3.selectbox("Fecha Vcto CxP:", dcxp.columns); cvp = c4.selectbox("Valor CxP:", dcxp.columns)
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
                    with st.spinner("🤖 La IA está analizando la proyección de liquidez..."):
                        st.markdown(consultar_ia_gemini(f"Actúa como gerente financiero. Analiza este flujo de caja proyectado y da recomendaciones. Saldo inicial: {saldo_hoy}. Datos: {cal.head(15).to_string()}"))
            except: st.error("Error en el formato de fechas. Asegúrese de seleccionar columnas de fecha válidas.")

# ------------------------------------------------------------------------------
# 7. CALCULADORA COSTOS
# ------------------------------------------------------------------------------
elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Calculadora de Costos Laborales")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Costeo Real de Nómina</h4>
        <p>Cálculo masivo del costo total empresa, incluyendo carga prestacional, seguridad social y parafiscales para toda la planta de personal.</p>
    </div>
    """, unsafe_allow_html=True)
    
    ac = st.file_uploader("Cargar Listado de Personal (.xlsx)", type=['xlsx'])
    if ac:
        dc = pd.read_excel(ac)
        c1, c2, c3, c4 = st.columns(4)
        cn, cs, ca, car = c1.selectbox("Col. Nombre", dc.columns), c2.selectbox("Col. Salario", dc.columns), c3.selectbox("Col. Aux. Trans (SI/NO)", dc.columns), c4.selectbox("Col. Riesgo ARL (1-5)", dc.columns)
        ce = st.selectbox("Col. Empresa Exonerada (SI/NO)", dc.columns)
        if st.button("🧮 CALCULAR COSTOS TOTALES"):
            rc = []
            for r in dc.to_dict('records'):
                c, cr = calcular_costo_empresa_fila(r, cs, ca, car, ce)
                rc.append({"Empleado": r[cn], "Salario Base": r[cs], "Costo Total Mensual Empresa": c, "Factor Prestacional Adicional": cr})
            st.dataframe(pd.DataFrame(rc).style.format({"Salario Base": "${:,.0f}", "Costo Total Mensual Empresa": "${:,.0f}", "Factor Prestacional Adicional": "${:,.0f}"}), use_container_width=True)

# ------------------------------------------------------------------------------
# 8. ANALÍTICA
# ------------------------------------------------------------------------------
elif menu == "📊 Analítica Financiera":
    st.header("📊 Inteligencia Financiera y Diagnóstico")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Diagnóstico Automático con IA</h4>
        <p>Análisis de Balances de Comprobación o Libros Diario para identificar patrones, tendencias y posibles riesgos financieros o tributarios mediante inteligencia artificial.</p>
    </div>
    """, unsafe_allow_html=True)
    
    fi = st.file_uploader("Cargar Datos Financieros (XLSX/CSV)", type=['xlsx', 'csv'])
    if fi and api_key:
        df = pd.read_csv(fi) if fi.name.endswith('.csv') else pd.read_excel(fi)
        cd, cv = st.selectbox("Columna Descripción/Cuenta", df.columns), st.selectbox("Columna Valor/Saldo", df.columns)
        if st.button("🤖 EJECUTAR ANÁLISIS IA"):
            res = df.groupby(cd)[cv].sum().sort_values(ascending=False).head(10)
            st.subheader("Top 10 Rubros Más Significativos")
            st.bar_chart(res)
            with st.spinner("🤖 El auditor IA está analizando los datos..."):
                st.markdown(consultar_ia_gemini(f"Actúa como auditor financiero senior. Analiza estos saldos contables y destaca puntos de atención: {res.to_string()}"))

# ------------------------------------------------------------------------------
# 9. NARRADOR FINANCIERO & NOTAS NIIF (IA)
# ------------------------------------------------------------------------------
elif menu == "📈 Reportes Gerenciales & Notas NIIF (IA)":
    st.header("📈 Narrador Financiero y Revelaciones NIIF")
    st.markdown("""
    <div class='instruccion-box' style='border-left: 4px solid #ad00ff;'>
        <h4>💡 Financial Storytelling Automatizado</h4>
        <p>Análisis comparativo de Estados Financieros con IA para detectar variaciones críticas y redactar automáticamente informes gerenciales y notas de revelación bajo norma NIIF.</p>
    </div>
    """, unsafe_allow_html=True)

    # Carga de archivos comparativos
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📅 Año Actual (Ej: 2025)")
        file_actual = st.file_uploader("Cargar Balance/P&G Actual", type=['xlsx'])
    with col2:
        st.subheader("📅 Año Anterior (Ej: 2024)")
        file_anterior = st.file_uploader("Cargar Balance/P&G Anterior", type=['xlsx'])

    if file_actual and file_anterior:
        try:
            df_act = pd.read_excel(file_actual)
            df_ant = pd.read_excel(file_anterior)
            
            st.write("---")
            st.subheader("⚙️ Configuración del Análisis Comparativo")
            c1, c2, c3 = st.columns(3)
            col_cuenta = c1.selectbox("Columna 'Cuenta Contable':", df_act.columns)
            col_valor_act = c2.selectbox("Columna Valor Año Actual:", df_act.columns)
            col_valor_ant = c3.selectbox("Columna Valor Año Anterior:", df_ant.columns)

            if st.button("✨ GENERAR INFORME INTELIGENTE") and api_key:
                # Preparación de Datos
                df_act_g = df_act.groupby(col_cuenta)[col_valor_act].sum().reset_index()
                df_ant_g = df_ant.groupby(col_cuenta)[col_valor_ant].sum().reset_index()
                
                merged = pd.merge(df_act_g, df_ant_g, on=col_cuenta, how='inner').fillna(0)
                merged['Variacion_Abs'] = merged[col_valor_act] - merged[col_valor_ant]
                
                # Filtrar Top Variaciones
                top_variaciones = merged.reindex(merged.Variacion_Abs.abs().sort_values(ascending=False).index).head(10)

                # Visualización
                st.markdown("### 📊 Tablero de Control de Variaciones")
                st.bar_chart(top_variaciones.set_index(col_cuenta)['Variacion_Abs'])

                # Inteligencia Artificial
                st.subheader("🧠 Análisis Cualitativo & Borrador de Notas NIIF")
                
                with st.spinner("🤖 El Consultor IA está redactando el informe y las notas..."):
                    prompt = f"""
                    Actúa como un Contador Senior experto en NIIF y Análisis Financiero.
                    Analiza la siguiente tabla de variaciones contables significativas:
                    {top_variaciones.to_string()}

                    GENERA DOS SECCIONES EN FORMATO MARKDOWN PROFESIONAL:
                    1. **INFORME GERENCIAL EJECUTIVO:** Explica en lenguaje de negocios claro (para la junta directiva) las principales causas y efectos de estas variaciones en la situación financiera de la empresa. Sé directo y estratégico.
                    2. **BORRADOR DE NOTAS A LOS ESTADOS FINANCIEROS (NIIF PYMES):** Redacta la nota de revelación técnica para las 3 cuentas con mayor variación absoluta, justificando la materialidad y describiendo el movimiento.
                    """
                    
                    respuesta_ia = consultar_ia_gemini(prompt)
                    st.markdown(respuesta_ia)
                    
                    st.download_button("📥 Descargar Informe Completo (.txt)", respuesta_ia, "Informe_Notas_NIIF.txt")

        except Exception as e:
            st.error(f"Error técnico en el procesamiento: {e}. Verifique que los archivos tengan la misma estructura de columnas.")

# ------------------------------------------------------------------------------
# 10. VALIDADOR RUT
# ------------------------------------------------------------------------------
elif menu == "🔍 Validador de RUT (Real)":
    st.header("🔍 Validador Oficial de RUT")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Verificación de Identificación Tributaria</h4>
        <p>Cálculo exacto del Dígito de Verificación (DV) mediante el algoritmo oficial de la DIAN y acceso directo a la consulta de estado del RUT.</p>
    </div>
    """, unsafe_allow_html=True)
    
    nit = st.text_input("Ingrese NIT o Cédula (Sin el dígito de verificación):", max_chars=15)
    if st.button("🔢 CALCULAR DV") and nit:
        dv = calcular_dv_colombia(nit)
        st.markdown(f"<div class='rut-card'><h2>NIT: {nit} - <span style='color:#0d6efd'>{dv}</span></h2><p>Dígito de Verificación Correcto</p></div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.link_button("🔗 Consultar Estado en Muisca (DIAN)", "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces")

# ------------------------------------------------------------------------------
# 11. OCR FACTURAS
# ------------------------------------------------------------------------------
elif menu == "📸 Digitalización (OCR)":
    st.header("📸 Digitalización de Documentos Físicos (OCR IA)")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Extracción de Datos de Imágenes</h4>
        <p>Utiliza inteligencia artificial visual para extraer automáticamente datos clave (NIT, Fecha, Valores) de fotografías o escaneos de facturas físicas.</p>
    </div>
    """, unsafe_allow_html=True)
    
    af = st.file_uploader("Cargar Imágenes de Facturas (JPG/PNG)", type=["jpg", "png"], accept_multiple_files=True)
    if af and st.button("🧠 EJECUTAR RECONOCIMIENTO ÓPTICO") and api_key:
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
st.markdown("<center><strong>Asistente Contable Pro - Enterprise Edition</strong> | Tecnología para Contadores 4.0 | Bucaramanga, Colombia © 2025</center>", unsafe_allow_html=True)
