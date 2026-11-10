import os
import sqlite3
from datetime import datetime
import stripe
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from openai import OpenAI

app = FastAPI()

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

@app.get("/", response_class=HTMLResponse)
def leer_index():
    return open("index.html", "r", encoding="utf-8").read()

@app.post("/clasificar-hs")
def clasificar(
    descripcion: str = Form(...), 
    pais: str = Form("España / UE"),
    valor_cif: float = Form(0.0)
):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    prompt_sistema = (
        "Eres un agente de aduanas experto, analista de comercio exterior y regulaciones arancelarias. "
        "Responde estrictamente estructurado en formato limpio:\n\n"
        "📦 **Código HS (6-10 dígitos):** [Código]\n"
        "💰 **Arancel Estimado:** [Porcentaje % y cálculo aproximado según el valor CIF proporcionado]\n"
        "🧾 **Desglose Landed Cost (Estimado):** [Cálculo del arancel, IVA de importación aplicable al país destino y costo total aproximado]\n"
        "⚠️ **Restricciones y Licencias:** [Indica si requiere marcado CE, licencias previas, certificaciones sanitarias o si hay aranceles antidumping]\n"
        "📋 **Observaciones Aduaneras:** [Notas clave de importación]"
    )

    respuesta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Clasifica y calcula costos para el producto: '{descripcion}', con destino a '{pais}' y un valor CIF de {valor_cif} EUR."}
        ]
    )
    
    resultado_texto = respuesta.choices[0].message.content

    # Guardar automáticamente en el historial de la base de datos
    try:
        conn = sqlite3.connect("docusync.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO historial (fecha, pais, producto, resultado, costo_estimado) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), pais, descripcion, resultado_texto, f"CIF: {valor_cif}")
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return {"resultado": resultado_texto}

# --- GESTOR DE DOCUMENTOS (FACTURAS Y PACKING LIST) ---
@app.post("/analizar-documento")
async def analizar_documento(file: UploadFile = File(...), pais: str = Form("España / UE")):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    contents = await file.read()
    # Si es imagen o PDF procesable por visión/texto
    base64_file = f"data:{file.content_type};base64," + __import__("base64").b64encode(contents).decode("utf-8")

    respuesta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system", 
                "content": "Eres un agente de aduanas. Analiza el documento comercial aportado (Factura o Packing List), extrae todos los productos listados y devuelve para cada uno su descripción comercial, su código HS sugerido, arancel estimado y si requiere restricciones o licencias de importación."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Analiza este documento para importación a {pais}:"},
                    {"type": "image_url", "image_url": {"url": base64_file}}
                ]
            }
        ],
        max_tokens=1000
    )
    return {"resultado": respuesta.choices[0].message.content}

# --- OBTENER HISTORIAL DE CONSULTAS ---
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
def exportar_txt(descripcion: str = Form(...), pais: str = Form("España / UE"), resultado: str = Form(...)):
    contenido = (
        "========================================\n"
        "          DOCUSYNC AI - INFORME ADUANERO\n"
        "========================================\n\n"
        f"País de Destino: {pais}\n"
        f"Descripción / Inventario:\n{descripcion}\n\n"
        "----------------------------------------\n"
        "RESULTADO DE CLASIFICACIÓN E IA:\n"
        "----------------------------------------\n"
        f"{resultado}\n\n"
        "========================================\n"
        "Informe generado automáticamente por DocuSync AI\n"
    )
    return PlainTextResponse(
        content=contenido,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=informe_docusync.txt"}
    )

@app.post("/crear-sesion-pago")
def crear_sesion_pago():
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': 'Crédito de Consultas - DocuSync AI'},
                    'unit_amount': 500,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url="https://docusync-ai-z84l.onrender.com/?exito=true",
            cancel_url="https://docusync-ai-z84l.onrender.com/?cancelado=true",
        )
        return {"url": session.url}
    except Exception as e:
        return {"error": str(e)}