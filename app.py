from flask import Flask, request, render_template, jsonify
import joblib
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
import os
import requests
import threading
import time
from pymongo import MongoClient
import pandas as pd
import plotly.express as px
import dash
from dash import dcc, html
from dash.dependencies import Input, Output

# Carregar variável
load_dotenv()
mongoURI = os.getenv("mongoURI")

# Configuração do Flask
app = Flask(__name__)

# Carrega o modelo
modelo = joblib.load('modelo.joblib')

# Criar cliente e conectar ao MongoDB
client = MongoClient(mongoURI)
db = client["deteccaoDeOcupacao"]
collection = db["ambiente"]

try:
    client.admin.command('ping')
    print("Conectado ao MongoDB!")
except Exception as e:
    print(e)

# Rota principal para previsão via formulário
@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == "POST":
        temperature = float(request.form.get("temperature"))
        humidity = float(request.form.get("humidity"))
        light = float(request.form.get("light"))
        co2 = float(request.form.get("co2"))
        humidity_ratio = float(request.form.get("humidity_ratio"))

        data_hora = datetime.now().strftime('%d/%m/%y %H:%M')

        features = np.array([[temperature, humidity, light, co2, humidity_ratio]])

        try:
            previsao = modelo.predict(features)
        except Exception as e:
            return f"Erro na previsão: {e}", 500

        # Salvar no MongoDB
        documento = {
            "data_hora": data_hora,
            "temperature": temperature,
            "humidity": humidity,
            "light": light,
            "co2": co2,
            "humidity_ratio": humidity_ratio,
            "occupancy": int(previsao[0])
        }
        try:
            collection.insert_one(documento)
            print("Documento salvo no MongoDB com sucesso!")
        except Exception as e:
            print(f"Erro ao salvar no MongoDB: {e}")

        return render_template("index.html", Occupancy=previsao[0], data=data_hora)

    return render_template("index.html")

# Executar a aplicação
if __name__ == '__main__':
    app.run(debug=True)