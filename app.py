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

# ------------------------------------------------------------------------------
# 1. CONFIGURACIÓN INICIAL (OBLIGATORIO AL PRINCIPIO)
# ------------------------------------------------------------------------------
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="📊", layout="wide")

# ------------------------------------------------------------------------------
# 2. SISTEMA DE SEGURIDAD (LOGIN GOOGLE)
# ------------------------------------------------------------------------------
# Importamos librerías de seguridad solo si están instaladas
try:
    from google_auth_oauthlib.flow import Flow
    from google.oauth2 import id_token
    import google.auth.transport.requests
    import requests
except ImportError:
    st.error("⚠️ Error Crítico: Faltan librerías de seguridad en requirements.txt")
    st.stop()

# URL EXACTA donde vive tu app
REDIRECT_URI = "https://aicontador.streamlit.app"

def sistema_login():
    # Si ya entramos, no hacer nada
    if st.session_state.get('logged_in'):
        return True

    # Configuramos la conexión con Google usando los 'Secrets' que pegaste
    try:
        client_config = {
            "web": {
                "client_id": st.secrets["client_id"],
                "project_id": st.secrets["project_id"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": st.secrets["client_secret"],
                "redirect_uris": [REDIRECT_URI]
            }
        }
        
        # Permisos que pedimos (Email y Perfil)
        scopes = [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ]

        flow = Flow.from_client_config(client_config, scopes=scopes, redirect_uri=REDIRECT_URI)

    except Exception as e:
        st.error(f"Error de Configuración de Secretos: {e}")
        st.stop()

    # Si Google nos devuelve un código en la URL, lo procesamos
    if 'code' in st.query_params:
        try:
            code = st.query_params['code']
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Validamos que el token sea real
            request = google.auth.transport.requests.Request()
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, request, st.secrets["client_id"]
            )
            
            # ¡LOGIN EXITOSO! Guardamos los datos
            st.session_state['logged_in'] = True
            st.session_state['username'] = id_info.get('name')
            st.session_state['email'] = id_info.get('email')
            
            # Limpiamos la URL para que se vea bonita
            st.query_params.clear()
            st.rerun()
            return True
            
        except Exception as e:
            st.error(f"Error validando entrada: {e}")
            time.sleep(3)
            st.query_params.clear()
            st.rerun()

    # Si NO hay código, mostramos el botón de entrar
    else:
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.markdown(f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 70vh; flex-direction: column; background-color: #0e1117;">
                <h1 style="color: #0d6efd; font-size: 3rem;">Asistente Contable Pro</h1>
                <p style="color: #a0a0a0; margin-bottom: 30px;">Sistema Inteligente de Auditoría y Finanzas</p>
                <a href="{auth_url}" target="_self" style="
                    background-color: #4285F4; color: white; padding: 15px 40px; 
                    text-decoration: none; border-radius: 50px; font-weight: bold; 
                    font-family: sans-serif; font-size: 18px; box-shadow: 0 4px 15px rgba(66, 133, 244, 0.4);
                    transition: transform 0.2s;">
                    🇬 Iniciar Sesión con Google
                </a>
            </div>
        """, unsafe_allow_html=True)
        return False

# EJECUTAR EL PORTERO (Si devuelve False, detenemos la app aquí)
if not sistema_login():
    st.stop()

# ==============================================================================
# 3. AQUÍ EMPIEZA LA APP REAL (SOLO VISIBLE SI ESTÁS LOGUEADO)
# ==============================================================================

# Conexión a Base de Datos (Segura)
try:
    if "gcp_service_account" in st.secrets:
        credentials_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials_dict)
    else:
        gc = None
except:
    gc = None

# Constantes Fiscales 2025
SMMLV_2025, AUX_TRANS_2025 = 1430000, 175000
UVT_2025, TOPE_EFECTIVO = 49799, 100 * 49799
BASE_RET_SERVICIOS, BASE_RET_COMPRAS = 4 * 49799, 27 * 49799

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117 !important; color: #e0e0e0 !important; }
    h1 { background: -webkit-linear-gradient(45deg, #0d6efd, #00d2ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .instruccion-box { background: rgba(38, 39, 48, 0.7); backdrop-filter: blur(10px); border-radius: 12px; padding: 20px; margin-bottom: 25px; border-left: 4px solid #0d6efd; }
    .stButton>button { background: linear-gradient(90deg, #0d6efd 0%, #0056b3 100%); color: white; border-radius: 8px; border: none; height: 3.5em; width: 100%; }
    .metric-box-red { background: rgba(62, 18, 22, 0.8); color: #ffaeb6; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #842029; }
    .metric-box-green { background: rgba(15, 41, 30, 0.8); color: #a3cfbb; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #0f5132; }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES LÓGICAS ---
def calcular_dv_colombia(nit):
    try:
        nit = str(nit).strip()
        if not nit.isdigit(): return "?"
        primos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        suma = sum(int(n) * p for n, p in zip(reversed(nit), primos))
        resto = suma % 11
        return str(resto) if resto <= 1 else str(11 - resto)
    except: return "?"

def consultar_ia_gemini(prompt):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e: return f"Error IA: {str(e)}"

# --- MENÚ LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    st.write(f"Hola, **{st.session_state.get('username', 'Usuario')}**") # Saludo personalizado
    if st.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()
    st.markdown("---")
    
    opciones = [
        "🏠 Inicio", "⚖️ Cruce DIAN", "📧 Lector XML", "🤝 Conciliador Bancario",
        "📂 Auditoría Gastos", "👥 Escáner UGPP", "💰 Tesorería", "💰 Calculadora Costos",
        "📊 Analítica", "📈 Narrador Financiero (NIIF)", "🔍 Validador RUT", "📸 OCR Facturas"
    ]
    menu = st.radio("Herramientas:", opciones)
    
    with st.expander("🔐 Configuración IA"):
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)

# --- LÓGICA DE PÁGINAS (Resumida para integridad) ---

if menu == "🏠 Inicio":
    st.title("Bienvenido al Asistente Contable Pro")
    st.success("✅ Acceso Seguro Verificado.")
    st.markdown("Selecciona una herramienta del menú lateral para comenzar.")

elif menu == "📈 Narrador Financiero (NIIF)":
    st.header("📈 Narrador Financiero & Notas NIIF")
    st.info("Sube el Balance de este año y el anterior. La IA explicará qué pasó.")
    c1, c2 = st.columns(2)
    f1 = c1.file_uploader("Año Actual 2025", type=['xlsx'])
    f2 = c2.file_uploader("Año Anterior 2024", type=['xlsx'])
    
    if f1 and f2 and api_key:
        df1 = pd.read_excel(f1); df2 = pd.read_excel(f2)
        st.subheader("Configura las columnas")
        cc1, cc2, cc3 = st.columns(3)
        cta = cc1.selectbox("Columna Cuenta", df1.columns)
        v1 = cc2.selectbox("Valor 2025", df1.columns)
        v2 = cc3.selectbox("Valor 2024", df2.columns)
        
        if st.button("Generar Informe IA"):
            # Lógica simplificada de unión y cálculo
            d1 = df1.groupby(cta)[v1].sum().reset_index()
            d2 = df2.groupby(cta)[v2].sum().reset_index()
            merged = pd.merge(d1, d2, on=cta, how='inner').fillna(0)
            merged['Var'] = merged[v1] - merged[v2]
            top = merged.reindex(merged.Var.abs().sort_values(ascending=False).index).head(5)
            
            st.bar_chart(top.set_index(cta)['Var'])
            prompt = f"Analiza estas variaciones contables y redacta un informe gerencial y una nota NIIF: {top.to_string()}"
            with st.spinner("Redactando..."):
                st.markdown(consultar_ia_gemini(prompt))

# (Aquí irían el resto de elif para las otras herramientas, copiando la lógica de las respuestas anteriores)
elif menu == "🔍 Validador RUT":
    st.header("Validador RUT")
    nit = st.text_input("NIT:")
    if st.button("Calcular DV"): st.success(f"DV: {calcular_dv_colombia(nit)}")
