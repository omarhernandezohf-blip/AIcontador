import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import io
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# ==============================================================================
# 1. CONFIGURACIÓN VISUAL (FONDO UNIFICADO Y TEXTO VISIBLE)
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    /* 1. FORZAR FONDO CLARO Y TEXTO OSCURO EN TODA LA APP */
    .stApp {
        background-color: #f4f6f9 !important; /* Fondo gris muy suave profesional */
        color: #212529 !important; /* Texto Gris Oscuro (Casi negro) */
    }
    
    /* 2. FUENTE UNIFICADA */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
    }

    /* 3. TÍTULOS (AZUL ORIGINAL) */
    h1 { color: #0d6efd !important; font-weight: 800; }
    h2, h3 { color: #343a40 !important; font-weight: 700; }
    
    /* 4. CAJA DE INSTRUCCIONES (CORREGIDA: MISMO FONDO DE PÁGINA) */
    .instruccion-box {
        background-color: transparent !important; /* Fondo transparente (igual a la página) */
        color: #212529 !important; /* Texto oscuro */
        border-left: 5px solid #0d6efd; /* Solo una línea azul al lado para decorar */
        padding: 15px;
        margin-bottom: 25px;
    }
    
    /* Asegurar que los títulos y textos dentro de la caja sean visibles */
    .instruccion-box h4 {
        color: #0d6efd !important; /* Título de la instrucción en azul */
        margin-top: 0;
        font-weight: bold;
    }
    .instruccion-box p, .instruccion-box li {
        color: #212529 !important; /* Texto del cuerpo oscuro */
        font-size: 16px;
    }

    /* 5. TARJETAS DE RESULTADOS (RUT, ETC) */
    .rut-card, .reporte-box {
        background-color: #ffffff !important; /* Estas sí blancas para resaltar el resultado */
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border-left: 5px solid #28a745; /* Verde éxito */
        margin-bottom: 20px;
    }
    .rut-card h2, .rut-card h3, .rut-card p {
        color: #212529 !important;
    }

    /* 6. BOTONES (AZUL ORIGINAL) */
    .stButton>button {
        background-color: #0d6efd !important;
        color: white !important;
        border-radius: 8px;
        font-weight: bold;
        border: none;
        height: 3em;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #0b5ed7 !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }

    /* 7. ALERTA ROJA/VERDE (TEXTO VISIBLE) */
    .metric-box-red { 
        background-color: #f8d7da !important; 
        color: #721c24 !important; 
        padding: 10px; border-radius: 5px; text-align: center; border: 1px solid #f5c6cb;
    }
    .metric-box-green { 
        background-color: #d1e7dd !important; 
        color: #0f5132 !important; 
        padding: 10px; border-radius: 5px; text-align: center; border: 1px solid #c3e6cb;
    }
    
    /* 8. LINKS */
    a { color: #0d6efd !important; text-decoration: none; font-weight: bold; }
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
# 3. LÓGICA DE NEGOCIO (FUNCIONES)
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
# 4. BARRA LATERAL (MENÚ ORGANIZADO)
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    st.title("Suite Contable IA")
    st.markdown("---")
    
    opciones_menu = [
        "🏠 Inicio / Quiénes Somos",
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
    
    menu = st.radio("Menú Principal:", opciones_menu)
    
    st.markdown("---")
    with st.expander("🔑 Configuración IA"):
        st.info("Pega aquí tu llave para activar las funciones inteligentes:")
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)

# ==============================================================================
# 5. DESARROLLO DE PESTAÑAS
# ==============================================================================

# ------------------------------------------------------------------------------
# 0. INICIO / QUIÉNES SOMOS
# ------------------------------------------------------------------------------
if menu == "🏠 Inicio / Quiénes Somos":
    st.header("👋 Bienvenido a tu Asistente Contable 4.0")
    
    col_intro1, col_intro2 = st.columns([1.5, 1])
    
    with col_intro1:
        st.markdown("""
        ### 🚀 ¿Quiénes Somos?
        Somos una herramienta creada **por contadores, para contadores**. Entendemos que nuestra profesión ha cambiado: ya no somos digitadores, somos analistas y asesores estratégicos.
        
        Nuestra misión es eliminar el "trabajo de carpintería" (digitar, puntear, revisar manualmente) usando la potencia de la **Inteligencia Artificial** y la automatización.
        
        ### 🛠️ ¿Qué hace esta aplicación?
        Esta Suite integra herramientas especializadas para:
        * **Automatizar:** Lectura de Facturas Electrónicas (XML) y Conciliación Bancaria.
        * **Auditar:** Revisión masiva de gastos (Art 771-5) y Nómina (UGPP).
        * **Prevenir:** Alertas de liquidez y validación de terceros (RUT).
        """)
        
    with col_intro2:
        st.markdown("""
        <div class='instruccion-box'>
            <h4>💡 ¿Cómo funciona?</h4>
            <p>La mayoría de módulos funcionan con <strong>cargas masivas de Excel</strong>.</p>
            <ol>
                <li>Descargas el reporte de tu software (Siigo, World Office, etc.).</li>
                <li>Lo subes al módulo correspondiente.</li>
                <li>La IA analiza y te entrega un reporte de auditoría listo.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    st.subheader("🔑 Tutorial: ¿Cómo obtener tu API Key GRATIS?")
    st.write("Para que la Inteligencia Artificial (Gemini) funcione y pueda 'leer' tus documentos o darte consejos, necesitas una llave gratuita de Google. Es muy fácil:")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("**Paso 1:** Ingresa a Google AI Studio con tu Gmail.\n\n[🔗 Ir a Google AI Studio](https://aistudio.google.com/app/apikey)")
    
    with c2:
        st.info("**Paso 2:** Haz clic en el botón azul grande que dice **'Create API Key'**.")
        
    with c3:
        st.info("**Paso 3:** Copia el código largo (AIza...) y pégalo en el menú izquierdo de esta app.")

# ------------------------------------------------------------------------------
# 1. LECTOR XML
# ------------------------------------------------------------------------------
elif menu == "📧 Lector XML (Facturación)":
    st.header("📧 Extractor Masivo XML")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve?</h4>
        <p>Extrae datos de Facturación Electrónica (XML) a Excel en segundos. La verdad legal está en el XML, no en el PDF.</p>
    </div>
    """, unsafe_allow_html=True)
    
    archivos_xml = st.file_uploader("Arrastra XMLs (Máx 5GB)", type=['xml'], accept_multiple_files=True)
    if archivos_xml and st.button("🚀 PROCESAR"):
        datos_xml = []
        bar = st.progress(0)
        for i, f in enumerate(archivos_xml):
            bar.progress((i+1)/len(archivos_xml))
            datos_xml.append(parsear_xml_dian(f))
        df_xml = pd.DataFrame(datos_xml)
        st.dataframe(df_xml)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as w: df_xml.to_excel(w, index=False)
        st.download_button("📥 Descargar Excel", out.getvalue(), "Resumen_XML.xlsx")

# ------------------------------------------------------------------------------
# 2. CONCILIADOR BANCARIO
# ------------------------------------------------------------------------------
elif menu == "🤝 Conciliador Bancario (IA)":
    st.header("🤝 Conciliador Bancario Automático")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve?</h4>
        <p>Cruza automáticamente tu Extracto Bancario vs. Contabilidad y detecta partidas pendientes.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_banco, col_libro = st.columns(2)
    with col_banco:
        st.subheader("🏦 Extracto")
        file_banco = st.file_uploader("Subir Extracto (.xlsx)", type=['xlsx'])
    with col_libro:
        st.subheader("📒 Contabilidad")
        file_libro = st.file_uploader("Subir Auxiliar (.xlsx)", type=['xlsx'])
    if file_banco and file_libro:
        df_banco = pd.read_excel(file_banco); df_libro = pd.read_excel(file_libro)
        c1, c2, c3, c4 = st.columns(4)
        col_fecha_b = c1.selectbox("Fecha Banco:", df_banco.columns, key="fb")
        col_valor_b = c2.selectbox("Valor Banco:", df_banco.columns, key="vb")
        col_fecha_l = c3.selectbox("Fecha Conta:", df_libro.columns, key="fl")
        col_valor_l = c4.selectbox("Valor Conta:", df_libro.columns, key="vl")
        col_desc_b = st.selectbox("Descripción Banco:", df_banco.columns, key="db")
        
        if st.button("🔄 CONCILIAR"):
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
            
            st.success(f"Cruzados: {len(matches)}")
            t1, t2, t3 = st.tabs(["✅ Cruzados", "⚠️ Pendiente Banco", "⚠️ Pendiente Libro"])
            with t1: st.dataframe(pd.DataFrame(matches))
            with t2: st.dataframe(df_banco[~df_banco['Conciliado']])
            with t3: st.dataframe(df_libro[~df_libro['Conciliado']])

# ------------------------------------------------------------------------------
# 3. AUDITORÍA GASTOS
# ------------------------------------------------------------------------------
elif menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal Masiva")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve?</h4>
        <p>Detecta errores 771-5 (Efectivo) y retenciones en tu auxiliar de gastos.</p>
    </div>
    """, unsafe_allow_html=True)
    
    ar = st.file_uploader("Auxiliar (.xlsx)", type=['xlsx'])
    if ar:
        df = pd.read_excel(ar)
        c1, c2, c3, c4 = st.columns(4)
        cf, ct, cc, cv = c1.selectbox("Fecha", df.columns), c2.selectbox("Tercero", df.columns), c3.selectbox("Concepto", df.columns), c4.selectbox("Valor", df.columns)
        cm = st.selectbox("Método Pago", ["No"]+list(df.columns))
        if st.button("AUDITAR"):
            res = []
            for r in df.to_dict('records'):
                met = r[cm] if cm != "No" else "Efectivo"
                h, rs = analizar_gasto_fila(r, cv, cf, cc)
                v = float(r[cv]) if pd.notnull(r[cv]) else 0
                txt, rv = [], "BAJO"
                if "efectivo" in str(met).lower() and v > TOPE_EFECTIVO: txt.append("RECHAZO 771-5"); rv="ALTO"
                if v >= BASE_RET_SERVICIOS: txt.append("Verif. Retención"); rv="MEDIO" if rv=="BAJO" else rv
                res.append({"Fila": r[cf], "Val": v, "Riesgo": rv, "Nota": " ".join(txt)})
            st.dataframe(pd.DataFrame(res))

# ------------------------------------------------------------------------------
# 4. ESCÁNER NÓMINA UGPP
# ------------------------------------------------------------------------------
elif menu == "👥 Escáner de Nómina (UGPP)":
    st.header("👥 Escáner UGPP")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve?</h4>
        <p>Detecta excesos del 40% en pagos no salariales (Ley 1393) para evitar sanciones.</p>
    </div>
    """, unsafe_allow_html=True)
    
    an = st.file_uploader("Nómina (.xlsx)", type=['xlsx'])
    if an:
        dn = pd.read_excel(an)
        c1, c2, c3 = st.columns(3)
        cn, cs, cns = c1.selectbox("Nombre", dn.columns), c2.selectbox("Salario", dn.columns), c3.selectbox("No Salarial", dn.columns)
        if st.button("AUDITAR"):
            res = []
            for r in dn.to_dict('records'):
                ibc, exc, est, msg = calcular_ugpp_fila(r, cs, cns)
                res.append({"Emp": r[cn], "Exc": exc, "Est": est})
            st.dataframe(pd.DataFrame(res))

# ------------------------------------------------------------------------------
# 5. TESORERÍA
# ------------------------------------------------------------------------------
elif menu == "💰 Tesorería & Flujo de Caja":
    st.header("💰 Radar de Liquidez")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve?</h4>
        <p>Proyecta tu flujo de caja cruzando CxC vs CxP para evitar iliquidez.</p>
    </div>
    """, unsafe_allow_html=True)
    
    saldo_hoy = st.number_input("💵 Saldo Hoy:", min_value=0.0, format="%.2f")
    c1, c2 = st.columns(2)
    fcxc = c1.file_uploader("CxC (.xlsx)", type=['xlsx'])
    fcxp = c2.file_uploader("CxP (.xlsx)", type=['xlsx'])
    if fcxc and fcxp:
        dcxc = pd.read_excel(fcxc); dcxp = pd.read_excel(fcxp)
        c1, c2, c3, c4 = st.columns(4)
        cfc = c1.selectbox("Fecha CxC:", dcxc.columns); cvc = c2.selectbox("Valor CxC:", dcxc.columns)
        cfp = c3.selectbox("Fecha CxP:", dcxp.columns); cvp = c4.selectbox("Valor CxP:", dcxp.columns)
        if st.button("PROYECTAR"):
            try:
                dcxc['Fecha'] = pd.to_datetime(dcxc[cfc]); dcxp['Fecha'] = pd.to_datetime(dcxp[cfp])
                fi = dcxc.groupby('Fecha')[cvc].sum().reset_index(); fe = dcxp.groupby('Fecha')[cvp].sum().reset_index()
                cal = pd.merge(fi, fe, on='Fecha', how='outer').fillna(0)
                cal.columns = ['Fecha', 'Ing', 'Egr']; cal = cal.sort_values('Fecha')
                cal['Saldo'] = saldo_hoy + (cal['Ing'] - cal['Egr']).cumsum()
                st.line_chart(cal.set_index('Fecha')['Saldo'])
                st.dataframe(cal)
                if api_key:
                    with st.spinner("IA Analizando..."):
                        st.markdown(consultar_ia_gemini(f"Analiza flujo caja. Saldo ini: {saldo_hoy}. Datos: {cal.head(10).to_string()}"))
            except: st.error("Error en fechas")

# ------------------------------------------------------------------------------
# 6. CALCULADORA COSTOS
# ------------------------------------------------------------------------------
elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Costos Nómina")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve?</h4>
        <p>Calcula costo real empresa (Prestaciones + Seg. Social + Parafiscales).</p>
    </div>
    """, unsafe_allow_html=True)
    
    ac = st.file_uploader("Personal (.xlsx)", type=['xlsx'])
    if ac:
        dc = pd.read_excel(ac)
        c1, c2, c3, c4 = st.columns(4)
        cn, cs, ca, car = c1.selectbox("Nombre", dc.columns), c2.selectbox("Salario", dc.columns), c3.selectbox("Aux Trans", dc.columns), c4.selectbox("ARL", dc.columns)
        ce = st.selectbox("Exonerado", dc.columns)
        if st.button("CALCULAR"):
            rc = []
            for r in dc.to_dict('records'):
                c, cr = calcular_costo_empresa_fila(r, cs, ca, car, ce)
                rc.append({"Emp": r[cn], "Tot": c})
            st.dataframe(pd.DataFrame(rc))

# ------------------------------------------------------------------------------
# 7. ANALÍTICA
# ------------------------------------------------------------------------------
elif menu == "📊 Analítica Financiera":
    st.header("📊 Analítica IA")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve?</h4>
        <p>Diagnóstico financiero automático con IA sobre Balances o Diarios.</p>
    </div>
    """, unsafe_allow_html=True)
    
    fi = st.file_uploader("Financieros", type=['xlsx', 'csv'])
    if fi and api_key:
        df = pd.read_csv(fi) if fi.name.endswith('.csv') else pd.read_excel(fi)
        cd, cv = st.selectbox("Descripción", df.columns), st.selectbox("Valor", df.columns)
        if st.button("ANALIZAR"):
            res = df.groupby(cd)[cv].sum().sort_values(ascending=False).head(10)
            st.bar_chart(res)
            st.markdown(consultar_ia_gemini(f"Analiza: {res.to_string()}"))

# ------------------------------------------------------------------------------
# 8. VALIDADOR RUT
# ------------------------------------------------------------------------------
elif menu == "🔍 Validador de RUT (Real)":
    st.header("🔍 Validación de RUT")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Herramienta Profesional</h4>
        <p>Calcula el DV Real y te lleva a la DIAN para verificar estado.</p>
    </div>
    """, unsafe_allow_html=True)
    
    nit = st.text_input("NIT (Sin DV):", max_chars=15)
    if st.button("CALCULAR") and nit:
        dv = calcular_dv_colombia(nit)
        st.markdown(f"<div class='rut-card'><h2>NIT: {nit}-{dv}</h2></div>", unsafe_allow_html=True)
        st.link_button("🔗 Verificar en DIAN", "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces")

# ------------------------------------------------------------------------------
# 9. OCR FACTURAS
# ------------------------------------------------------------------------------
elif menu == "📸 Digitalización (OCR)":
    st.header("📸 OCR Facturas")
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve?</h4>
        <p>Extrae datos de fotos de facturas a Excel usando Visión Artificial.</p>
    </div>
    """, unsafe_allow_html=True)
    
    af = st.file_uploader("Fotos", type=["jpg", "png"], accept_multiple_files=True)
    if af and st.button("PROCESAR") and api_key:
        do = []
        bar = st.progress(0)
        for i, f in enumerate(af):
            bar.progress((i+1)/len(af)); info = ocr_factura(Image.open(f))
            if info: do.append(info)
        st.dataframe(pd.DataFrame(do))

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown("<center>Desarrollado para Contadores 4.0 | Bucaramanga, Colombia</center>", unsafe_allow_html=True)
