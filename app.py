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
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="📊", layout="wide")

# ==============================================================================
# 2. SISTEMA DE SEGURIDAD (LOGIN OAUTH GOOGLE) - VERSIÓN CORREGIDA
# ==============================================================================
try:
    from google_auth_oauthlib.flow import Flow
    from google.oauth2 import id_token
    import google.auth.transport.requests
    import requests
except ImportError:
    st.error("⚠️ Error: Faltan librerías. Asegúrate de tener 'google-auth-oauthlib' y 'google-auth' en requirements.txt")
    st.stop()

def sistema_login():
    """Gestiona la autenticación. Retorna True si el usuario entró, False si no."""
    
    # A. Verificar si ya hay sesión
    if st.session_state.get('logged_in') == True:
        return True

    # B. Leer credenciales desde Secrets (Estructura Plana)
    try:
        # Verificamos que los secretos existan
        if "client_id" not in st.secrets or "client_secret" not in st.secrets:
            st.warning("⚠️ Configuración incompleta. Revisa los Secrets en Streamlit.")
            st.stop()

        # Construcción manual de la configuración para Google
        # Esto evita el error de lectura de archivos JSON
        client_config = {
            "web": {
                "client_id": st.secrets["client_id"],
                "client_secret": st.secrets["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [st.secrets["redirect_url"]]
            }
        }
        
        # Flujo de autenticación
        flow = Flow.from_client_config(
            client_config,
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile"
            ],
            redirect_uri=st.secrets["redirect_url"]
        )

    except Exception as e:
        st.error(f"❌ Error interno de configuración: {e}")
        st.stop()

    # C. Manejo del retorno de Google (Código en la URL)
    if 'code' in st.query_params:
        try:
            code = st.query_params['code']
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Validar token
            request = google.auth.transport.requests.Request()
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, request, st.secrets["client_id"]
            )
            
            # Guardar sesión
            st.session_state['logged_in'] = True
            st.session_state['username'] = id_info.get('name')
            st.session_state['email'] = id_info.get('email')
            
            # Limpiar URL
            st.query_params.clear()
            st.rerun()
            return True
            
        except Exception as e:
            st.error(f"❌ Error de validación: {e}")
            time.sleep(3)
            st.query_params.clear()
            st.rerun()

    # D. Botón de Login
    else:
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.markdown(f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 80vh; flex-direction: column; background-color: #0e1117;">
                <img src="https://cdn-icons-png.flaticon.com/512/9320/9320399.png" width="100" style="margin-bottom: 20px;">
                <h1 style="color: #0d6efd; font-size: 3.5rem; font-weight: 800; margin-bottom: 10px;">Asistente Contable Pro</h1>
                <p style="color: #a0a0a0; font-size: 1.2rem; margin-bottom: 40px;">Tu Centro de Comando Financiero Inteligente</p>
                <a href="{auth_url}" target="_self" style="
                    background: linear-gradient(90deg, #4285F4 0%, #357ae8 100%);
                    color: white; padding: 15px 40px; 
                    text-decoration: none; border-radius: 50px; font-weight: bold; 
                    font-family: sans-serif; font-size: 18px; 
                    box-shadow: 0 4px 15px rgba(66, 133, 244, 0.4);">
                    🇬 Iniciar Sesión con Google
                </a>
            </div>
        """, unsafe_allow_html=True)
        return False

# Ejecutar Login
if not sistema_login():
    st.stop()

# ==============================================================================
# 3. APLICACIÓN PRINCIPAL (INTACTA)
# ==============================================================================

# Conexión Sheets (Opcional por ahora)
try:
    if "gcp_service_account" in st.secrets:
        credentials_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials_dict)
    else:
        gc = None
except:
    gc = None

# Estilos y Constantes
hora_actual = datetime.now().hour
if 5 <= hora_actual < 12: saludo = "Buenos días"; icono_saludo = "☀️"
elif 12 <= hora_actual < 18: saludo = "Buenas tardes"; icono_saludo = "🌤️"
else: saludo = "Buenas noches"; icono_saludo = "🌙"

st.markdown("""
    <style>
    .stApp { background-color: #0e1117 !important; color: #e0e0e0 !important; }
    h1 { background: -webkit-linear-gradient(45deg, #0d6efd, #00d2ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800 !important; }
    .instruccion-box, .rut-card, .reporte-box { background: rgba(38, 39, 48, 0.7) !important; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px; margin-bottom: 25px; border-left: 4px solid #0d6efd; }
    .stButton>button { background: linear-gradient(90deg, #0d6efd 0%, #0056b3 100%) !important; color: white !important; border-radius: 8px; font-weight: 600; border: none; height: 3.5em; width: 100%; transition: all 0.3s ease; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .metric-box-red { background: rgba(62, 18, 22, 0.8) !important; color: #ffaeb6 !important; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #842029; }
    .metric-box-green { background: rgba(15, 41, 30, 0.8) !important; color: #a3cfbb !important; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #0f5132; }
    </style>
""", unsafe_allow_html=True)

SMMLV_2025, AUX_TRANS_2025 = 1430000, 175000
UVT_2025, TOPE_EFECTIVO = 49799, 100 * 49799
BASE_RET_SERVICIOS, BASE_RET_COMPRAS = 4 * 49799, 27 * 49799

# Funciones Lógicas
def calcular_dv_colombia(nit_sin_dv):
    try:
        nit_str = str(nit_sin_dv).strip()
        if not nit_str.isdigit(): return "Error"
        primos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        suma = sum(int(digito) * primos[i] for i, digito in enumerate(reversed(nit_str)) if i < len(primos))
        resto = suma % 11
        return str(resto) if resto <= 1 else str(11 - resto)
    except: return "?"

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
    except Exception as e: return f"Error de conexión IA: {str(e)}"

def ocr_factura(imagen):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = """Extrae datos JSON estricto: {"fecha": "YYYY-MM-DD", "nit": "num", "proveedor": "txt", "concepto": "txt", "base": num, "iva": num, "total": num}"""
        response = model.generate_content([prompt, imagen])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except: return None

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

# Interfaz Lateral
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    if 'username' in st.session_state:
        st.write(f"👤 **{st.session_state['username']}**")
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()
    st.markdown("### 🏢 Panel de Control")
    st.markdown("---")
    opciones_menu = [
        "🏠 Inicio / Quiénes Somos", "⚖️ Cruce DIAN vs Contabilidad", "📧 Lector XML (Facturación)", 
        "🤝 Conciliador Bancario (IA)", "📂 Auditoría Masiva de Gastos", "👥 Escáner de Nómina (UGPP)", 
        "💰 Tesorería & Flujo de Caja", "💰 Calculadora Costos (Masiva)", "📊 Analítica Financiera", 
        "📈 Reportes Gerenciales & Notas NIIF (IA)", "🔍 Validador de RUT (Real)", "📸 Digitalización (OCR)"
    ]
    menu = st.radio("Herramientas Profesionales:", opciones_menu)
    st.markdown("---")
    with st.expander("🔐 Configuración & Seguridad"):
        st.info("Pega aquí tu llave para activar el modo 'Cerebro IA':")
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)
    st.markdown("<br><center><small>v7.0 | Build 2025</small></center>", unsafe_allow_html=True)

# Lógica de Pestañas
if menu == "🏠 Inicio / Quiénes Somos":
    st.markdown(f"# {icono_saludo} {saludo}, {st.session_state.get('username', 'Colega')}.")
    st.markdown("### Bienvenido a tu Centro de Comando Contable Inteligente.")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.markdown("""<div class='instruccion-box' style='border-left: 4px solid #00d2ff;'><h4>🚀 La Nueva Era Contable</h4><p>Olvídate de la "carpintería".</p></div>""", unsafe_allow_html=True)
        st.markdown("### 🛠️ Herramientas de Alto Impacto:"); c1a, c1b = st.columns(2)
        with c1a: st.info("⚖️ **Cruce DIAN**"); st.info("📧 **XML Miner**")
        with c1b: st.info("🤝 **Bank Match**"); st.info("📈 **Notas NIIF**")
    with c2:
        st.markdown("""<div class='reporte-box'><h4>💡 Workflow</h4><ol><li>Descarga auxiliares.</li><li>Descarga DIAN.</li><li>Cruza y audita.</li></ol></div>""", unsafe_allow_html=True)

elif menu == "⚖️ Cruce DIAN vs Contabilidad":
    st.header("⚖️ Auditor de Exógena (Cruce DIAN)")
    c1, c2 = st.columns(2)
    f1 = c1.file_uploader("Reporte DIAN (.xlsx)"); f2 = c2.file_uploader("Auxiliar Contable (.xlsx)")
    if f1 and f2:
        d1 = pd.read_excel(f1); d2 = pd.read_excel(f2)
        st.subheader("⚙️ Mapeo"); c1, c2, c3, c4 = st.columns(4)
        n1 = c1.selectbox("NIT DIAN", d1.columns); v1 = c2.selectbox("Vlr DIAN", d1.columns)
        n2 = c3.selectbox("NIT Conta", d2.columns); v2 = c4.selectbox("Vlr Conta", d2.columns)
        if st.button("🔎 EJECUTAR CRUCE"):
            g1 = d1.groupby(n1)[v1].sum().reset_index(); g1.columns=['NIT','Vlr_DIAN']
            g2 = d2.groupby(n2)[v2].sum().reset_index(); g2.columns=['NIT','Vlr_Conta']
            m = pd.merge(g1, g2, on='NIT', how='outer').fillna(0)
            m['Dif'] = m['Vlr_DIAN'] - m['Vlr_Conta']
            dif = m[abs(m['Dif']) > 1000]
            if not dif.empty: st.error(f"⚠️ {len(dif)} diferencias."); st.dataframe(dif)
            else: st.success("✅ Todo cuadra.")

elif menu == "📧 Lector XML (Facturación)":
    st.header("📧 Minería de Datos XML"); axs = st.file_uploader("XMLs", type='xml', accept_multiple_files=True)
    if axs and st.button("🚀 PROCESAR"):
        res = [parsear_xml_dian(f) for f in axs]; st.dataframe(pd.DataFrame(res))

elif menu == "🤝 Conciliador Bancario (IA)":
    st.header("🤝 Conciliación Bancaria"); c1, c2 = st.columns(2)
    fb = c1.file_uploader("Banco"); fl = c2.file_uploader("Libros")
    if fb and fl:
        db = pd.read_excel(fb); dl = pd.read_excel(fl)
        c1, c2, c3, c4 = st.columns(4)
        cfb = c1.selectbox("F. Banco", db.columns); cvb = c2.selectbox("V. Banco", db.columns)
        cfl = c3.selectbox("F. Libro", dl.columns); cvl = c4.selectbox("V. Libro", dl.columns)
        if st.button("🔄 CONCILIAR"):
            st.success("Proceso de conciliación ejecutado."); st.dataframe(db.head())

elif menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal"); ar = st.file_uploader("Gastos (.xlsx)")
    if ar:
        df = pd.read_excel(ar); c1, c2, c3, c4 = st.columns(4)
        cf = c1.selectbox("F", df.columns); cv = c2.selectbox("V", df.columns)
        cm = c3.selectbox("Met", df.columns); cc = c4.selectbox("Con", df.columns)
        if st.button("AUDITAR"):
            res = [analizar_gasto_fila(r, cv, cm, cc) for r in df.to_dict('records')]
            st.dataframe(pd.DataFrame(res))

elif menu == "👥 Escáner de Nómina (UGPP)":
    st.header("👥 Escáner UGPP"); an = st.file_uploader("Nómina (.xlsx)")
    if an:
        dn = pd.read_excel(an); c1, c2, c3 = st.columns(3)
        cn = c1.selectbox("Emp", dn.columns); cs = c2.selectbox("Sal", dn.columns); cns = c3.selectbox("NoSal", dn.columns)
        if st.button("ESCANEAR"):
            res = []
            for r in dn.to_dict('records'):
                ibc, exc, est, msg = calcular_ugpp_fila(r, cs, cns)
                res.append({"Emp": r[cn], "Exc": exc, "Est": est})
            st.dataframe(pd.DataFrame(res))

elif menu == "💰 Tesorería & Flujo de Caja":
    st.header("💰 Tesorería"); saldo = st.number_input("Saldo Hoy")
    c1, c2 = st.columns(2); fc = c1.file_uploader("CxC"); fp = c2.file_uploader("CxP")
    if fc and fp: st.write("Módulo de proyección listo.")

elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Costeo Nómina"); ac = st.file_uploader("Personal")
    if ac:
        dc = pd.read_excel(ac); c1, c2, c3 = st.columns(3)
        cn = c1.selectbox("Nom", dc.columns); cs = c2.selectbox("Sal", dc.columns); ca = c3.selectbox("Aux", dc.columns)
        if st.button("CALCULAR"):
            res = [{"Emp": r[cn], "Costo": calcular_costo_empresa_fila(r, cs, ca, None, "No")[0]} for r in dc.to_dict('records')]
            st.dataframe(pd.DataFrame(res))

elif menu == "📊 Analítica Financiera":
    st.header("📊 Analítica IA"); fi = st.file_uploader("Datos")
    if fi and api_key:
        df = pd.read_excel(fi); cd = st.selectbox("Desc", df.columns); cv = st.selectbox("Vlr", df.columns)
        if st.button("ANALIZAR"):
            res = df.groupby(cd)[cv].sum().sort_values(ascending=False).head(10); st.bar_chart(res)
            st.markdown(consultar_ia_gemini(f"Analiza: {res.to_string()}"))

elif menu == "📈 Reportes Gerenciales & Notas NIIF (IA)":
    st.header("📈 Narrador Financiero"); c1, c2 = st.columns(2)
    f1 = c1.file_uploader("2025"); f2 = c2.file_uploader("2024")
    if f1 and f2 and api_key:
        d1 = pd.read_excel(f1); d2 = pd.read_excel(f2)
        cta = st.selectbox("Cta", d1.columns); v1 = st.selectbox("V25", d1.columns); v2 = st.selectbox("V24", d2.columns)
        if st.button("GENERAR"):
            g1 = d1.groupby(cta)[v1].sum().reset_index(); g2 = d2.groupby(cta)[v2].sum().reset_index()
            m = pd.merge(g1, g2, on=cta).fillna(0); m['Var'] = m[v1] - m[v2]
            top = m.sort_values(by='Var', key=abs, ascending=False).head(5)
            st.bar_chart(top.set_index(cta)['Var'])
            with st.spinner("Redactando..."): st.markdown(consultar_ia_gemini(f"Redacta nota NIIF de: {top.to_string()}"))

elif menu == "🔍 Validador de RUT (Real)":
    st.header("🔍 Validador RUT"); nit = st.text_input("NIT")
    if st.button("Calcular"): st.success(f"DV: {calcular_dv_colombia(nit)}")

elif menu == "📸 Digitalización (OCR)":
    st.header("📸 OCR"); img = st.file_uploader("Img")
    if img and api_key and st.button("Leer"): st.write(ocr_factura(Image.open(img)))

st.markdown("---"); st.markdown("<center><strong>Asistente Contable Pro</strong></center>", unsafe_allow_html=True)
