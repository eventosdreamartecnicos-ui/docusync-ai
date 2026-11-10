from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from openai import OpenAI
import os

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def leer_index():
    return open("index.html", "r", encoding="utf-8").read()

@app.post("/clasificar-hs")
def clasificar(descripcion: str = Form(...)):
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        respuesta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un agente de aduanas experto. Devuelve el código HS de 6 dígitos, arancel estimado y normativas clave en formato claro."},
                {"role": "user", "content": f"Clasifica este producto: {descripcion}"}
            ]
        )
        return {"resultado": respuesta.choices[0].message.content}
    except Exception as e:
        return {"resultado": f"Error detallado del servidor: {str(e)}"}