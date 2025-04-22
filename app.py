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
from dash import Dash, dcc, html, Output, Input
import plotly.express as px
import pandas as pd
import requests

# Carregar variável
load_dotenv()
mongoURI = os.getenv("mongoURI")

# Configuração do Flask
app = Flask(__name__)

# Carregar o modelo
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

# Rota principal para previsão 
@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == "POST":
        temperature = float(request.form.get("temperature"))
        humidity = float(request.form.get("humidity"))
        light = float(request.form.get("light"))
        co2 = float(request.form.get("co2"))
        humidity_ratio = float(request.form.get("humidity_ratio"))

        dataHora = datetime.now().strftime('%d/%m/%y %H:%M')

        features = np.array([[temperature, humidity, light, co2, humidity_ratio]])

        try:
            previsao = modelo.predict(features)
        except Exception as e:
            return f"Erro na previsão: {e}", 500

        # Salvar no MongoDB
        documento = {
            "dataHora": dataHora,
            "temperature": temperature,
            "humidity": humidity,
            "light": light,
            "co2": co2,
            "humidityRatio": humidity_ratio,
            "occupancy": int(previsao[0])
        }
        try:
            collection.insert_one(documento)
            print("Documento salvo no MongoDB com sucesso!")
        except Exception as e:
            print(f"Erro ao salvar no MongoDB: {e}")

        return render_template("index.html", Occupancy=previsao[0], data=dataHora)

    return render_template("index.html")

# Endpoint para obter dados do MongoDB
@app.route('/dados', methods=['GET'])
def dados():
    try:
        dados = list(collection.find().sort("dataHora", -1)) 
        for d in dados:
            d["_id"] = str(d["_id"])
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# Dash
def initDashboard(server):
    dashApp = Dash(__name__, server=server, routes_pathname_prefix='/dashboard/')

    # Definir página
    dashApp.layout = html.Div([
        html.H1("Dashboard - Índices de ocupação dos ambientes", style={'font-size': '24px', 'color': '#2c3e50', 'text-align': 'center', 'font-weight': 'bold', 'margin-bottom' : '30px', 'font-family' : 'Segoe UI'}),
        #dcc.Link(
            #html.Button("Novo registro", n_clicks=0, style={ 'margin-top' : '20px', 'padding': '12px', 'background-color': '#4CAF50', 'color':' white', 'border': 'none', 'border-radius': '6px', 'font-size': '16px','cursor': 'pointer'}),href='/'
           # ),
        html.Div(id='metricas'),
        html.Div([
            dcc.Graph(id='graficoOcupacao', style={'width': '50%'}),
            dcc.Graph(id='graficoTurnos', style={'width': '50%'})
        ], style={'display': 'flex', 'justifyContent': 'center', 'gap': '50px'}),
        dcc.Graph(id='graficoMediaVariaveis'),
        dcc.Interval(id='intervaloAtualizacao', interval=5000, n_intervals=0) # Atualiza a cada 5s

    ], style={'font-family': 'Arial', 'padding': '10px 100px'})

    # Callback para atualizar os gráficos
    @dashApp.callback(
        Output('metricas', 'children'), 
        Output('graficoOcupacao', 'figure'), 
        Output('graficoTurnos', 'figure'),          
        Output('graficoMediaVariaveis', 'figure'),          
        Input('intervaloAtualizacao', 'n_intervals') 
    )

    def atualizarGrafico(n):
        try:
            # Requisitar dados ao endpoint local
            response = requests.get("http://localhost:5000/dados")
            dataJson = response.json()
            dados = pd.DataFrame(dataJson)
        except Exception as e:
            print(f"Erro ao buscar dados da API: {e}")
            dados = pd.DataFrame()

        # Criar métricas: total de registros, de ocupação e desocupação
        totalRegistros = len(dados)
        ocupados = dados[dados["occupancy"] == 1].shape[0]
        desocupados = dados[dados["occupancy"] == 0].shape[0] 

        # Criar o bloco de texto com as métricas
        metricas = html.Div([
            html.Div(f"Total de registros: {totalRegistros}", style={'border-radius': '7px', 'padding': '10px', 'background-color': '#E6FFE6', 'font-size': '18px', 'text-align': 'center', 'width': '20%'}),
            html.Div(f"Ambientes ocupados: {ocupados}", style={'border-radius': '7px', 'padding': '10px', 'background-color': '#E6FFE6', 'font-size': '18px', 'text-align': 'center', 'width': '20%'}),
            html.Div(f"Ambientes desocupados: {desocupados}", style={'border-radius': '7px', 'padding': '10px', 'background-color': '#E6FFE6', 'font-size': '18px', 'text-align': 'center', 'width': '20%'})
        ], style={'display': 'flex', 'justifyContent': 'center', 'gap': '50px'})

        # Criar gráfico 1 - Porcentagem de ocupação e desocupação
        agrupado = dados.groupby(['occupancy']).size().reset_index(name='quantidade') # Agrupar por turno e ocupação 
        # Calcular porcentagem
        agrupado['porcentagem'] = (agrupado['quantidade'] / agrupado['quantidade'].sum()) * 100
        # Substituir 0 = desocupado, 1 = ocupado
        agrupado['status'] = agrupado['occupancy'].replace({0: 'Desocupado', 1: 'Ocupado'})

        # Montar gráfico
        graficoOcupacao = px.pie(
            agrupado,
            names='status',
            values='porcentagem',
            title='Porcentagem de ocupação e desocupação',
            labels={'porcentagem': '%', 'status': 'Status'},
            color='status',
            color_discrete_map={'Ocupado': '#E6FFE6', 'Desocupado': '#4CAF50'}
        )

        # Criar gráfico 2 - Porcentagem de ocupação e desocupação por turno
        dados['dataHora'] = pd.to_datetime(dados['dataHora'], format="%d/%m/%y %H:%M", errors='coerce') # Converter data para datetime

        def definirTurno(hora):
            if 5 <= hora < 12:
                return 'Manhã'
            elif 12 <= hora < 18:
                return 'Tarde'
            else:
                return 'Noite'
            
        dados['turno'] = dados['dataHora'].dt.hour.apply(definirTurno)

        # Agrupar por turno e ocupação 
        agrupadoTurno = dados.groupby(['turno', 'occupancy']).size().reset_index(name='quantidade')

        # Calcular porcentagem
        totalPorTurno = agrupadoTurno.groupby('turno')['quantidade'].transform('sum')
        agrupadoTurno['porcentagem'] = (agrupadoTurno['quantidade'] / totalPorTurno) * 100

        # Substituir 0 = desocupado, 1 = ocupado
        agrupadoTurno['status'] = agrupadoTurno['occupancy'].replace({0: 'Desocupado', 1: 'Ocupado'})

        # Montar gráfico
        graficoTurnos = px.bar(
            agrupadoTurno,
            x='turno',
            y='porcentagem',
            color='status',
            color_discrete_map={'Ocupado': '#E6FFE6', 'Desocupado': '#4CAF50'},
            barmode='stack',
            title='Porcentagem de ocupação e desocupação por turno',
            labels={'turno': 'Turno', 'porcentagem': '%', 'status': 'Status'}
        )

        # Criar gráfico 3 - Média das variáveis ambientais em locais ocupados e desocupados
        # Filtrar os dados por ocupação
        desocupados = dados[dados['occupancy'] == 0]
        ocupados = dados[dados['occupancy'] == 1]
        
        # Calcular a média das variáveis por ocupação
        mediasOcupados = ocupados[['temperature', 'humidity', 'light', 'co2', 'humidityRatio']].mean()
        mediasDesocupados = desocupados[['temperature', 'humidity', 'light', 'co2', 'humidityRatio']].mean()

        # Criar um DataFrame
        mediasComparacao = pd.DataFrame({
            'Ocupados': mediasOcupados,
            'Desocupados': mediasDesocupados
        })

        # Renomear variáveis
        rename = {
            'temperature': 'Temperatura (°C)',
            'humidity': 'Umidade (%)',
            'light': 'Luminosidade',
            'co2': 'CO2 (ppm)',
            'humidityRatio': 'Razão de umidade'
        }
        mediasComparacao.rename(index=rename, inplace=True)
    
        # Montar gráfico
        graficoMediaVariaveis = px.bar(
            mediasComparacao,
            x=mediasComparacao.index,
            y=mediasComparacao.columns,
            title='Média das variáveis ambientais em locais ocupados e desocupados',
            labels={'value': 'Média', 'index': 'Variável', 'variable': 'Status'},
            barmode='group',
            color_discrete_map={'Ocupados': '#E6FFE6', 'Desocupados': '#4CAF50'}
        )
        # Começar gráfico em -100
        graficoMediaVariaveis.update_layout(
            yaxis=dict(range=[-100, None])  
        )

        return metricas, graficoOcupacao, graficoTurnos, graficoMediaVariaveis

    return dashApp

# Inicializar o Dash dentro do Flask
initDashboard(app)

# Executar a aplicação
if __name__ == '__main__':
    app.run(debug=True)