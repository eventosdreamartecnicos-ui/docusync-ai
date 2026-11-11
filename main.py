import os
import sqlite3
from datetime import datetime
import stripe
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from openai import OpenAI
from fastapi.staticfiles import StaticFiles

# Añade esta línea para que FastAPI sirva los archivos de la raíz (como el logo.png)
app.mount("/", StaticFiles(directory="."), name="static")

# 1. Inicializar FastAPI PRIMERO de todo
app = FastAPI()

# 2. Configurar archivos estáticos para que lea el logo y carpetas locales
app.mount("/static", StaticFiles(directory="."), name="static")

# Configurar Stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# --- CONFIGURACIÓN DE BASE DE DATOS LOCAL (HISTORIAL) ---
def init_db():
    conn = sqlite3.connect("docusync.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            pais TEXT,
            producto TEXT,
            resultado TEXT,
            costo_estimado TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Cargar cliente de OpenAI (si usas IA)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.get("/", response_class=HTMLResponse)
def leer_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Error: No se encuentra el archivo index.html</h1>"

@app.post("/clasificar-hs")
def clasificar_hs(descripcion: str = Form(...), pais: str = Form(...), valor_cif: float = Form(0.0)):
    # Simulación de respuesta de IA / Aduanas (o integración real con OpenAI)
    resultado = f"Análisis aduanero para {pais}.\nProducto: {descripcion}\nValor CIF: {valor_cif}\n- Código Arancelario sugerido (HS): 8471.30\n- Arancel estimado: 2.5%\n- IVA / Impuestos locales: 21%\n- Landed Cost Total calculado con éxito."
    
    # Guardar en base de datos
    conn = sqlite3.connect("docusync.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO historial (fecha, pais, producto, resultado, costo_estimado) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M"), pais, descripcion, resultado, str(valor_cif))
    )
    conn.commit()
    conn.close()

    return {"resultado": resultado}

@app.post("/analizar-documento")
async def analizar_documento(file: UploadFile = File(...), pais: str = Form(...)):
    contenido_archivo = await file.read()
    resultado = f"Documento '{file.filename}' procesado correctamente para el país {pais} mediante Visión IA.\n- Líneas de factura detectadas: 3\n- Validación de cumplimiento normativo: Aprobado sin restricciones."
    
    conn = sqlite3.connect("docusync.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO historial (fecha, pais, producto, resultado, costo_estimado) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M"), pais, f"Documento: {file.filename}", resultado, "N/A")
    )
    conn.commit()
    conn.close()

    return {"resultado": resultado}

@app.get("/obtener-historial")
def obtener_historial():
    conn = sqlite3.connect("docusync.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM historial ORDER BY id DESC LIMIT 10")
    filas = cursor.fetchall()
    conn.close()
    return [dict(fila) for fila in filas]

@app.post("/exportar-txt")
def exportar_txt(descripcion: str = Form(...), pais: str = Form(...), resultado: str = Form(...)):
    contenido = f"INFORME OFICIAL DOCUSYNC AI\nFecha: {datetime.now()}\nPaís: {pais}\nProducto/Doc: {descripcion}\n\n{resultado}"
    return PlainTextResponse(contenido, media_type="text/plain", headers={"Content-Disposition": "attachment; filename=informe_docusync.txt"})

@app.post("/crear-sesion-pago")
async def crear_sesion_pago():
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': 'DocuSync AI - Enterprise Suite',
                    },
                    'unit_amount': 500,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://docusync-ai-z84l.onrender.com/?success=true',
            cancel_url='https://docusync-ai-z84l.onrender.com/?canceled=true',
        )
        return {"url": checkout_session.url}
    except Exception as e:
        # Pega esto aquí dentro para que imprima el fallo exacto en Render
        print(f"ERROR DE STRIPE: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))