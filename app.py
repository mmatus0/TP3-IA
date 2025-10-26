import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request

# --- Configuración Inicial ---
app = Flask(__name__)
REGLAS = [] # Base de Conocimiento (Reglas cargadas desde JSON)
DB_NAME = "diagnosticos_riesgo.db" # Nombre del archivo SQLite

# --- Funciones de Gestión de Reglas y Motor de Inferencia ---

def cargar_reglas():
    """Cargo la base de conocimiento (Reglas) desde el archivo JSON."""
    global REGLAS
    try:
        with open('reglas_incendios.json', 'r', encoding='utf-8') as f:
            REGLAS = json.load(f)
    except FileNotFoundError:
        print("Error: El archivo reglas_incendios.json no fue encontrado.")
        REGLAS = []

def evaluar_condicion(valor_hecho, operador, valor_regla):
    """Función auxiliar para evaluar si un hecho cumple una condición."""
    if operador == '>=':
        return valor_hecho >= valor_regla
    elif operador == '>':
        return valor_hecho > valor_regla
    elif operador == '<=':
        return valor_hecho <= valor_regla
    elif operador == '<':
        return valor_hecho < valor_regla
    elif operador == '==':
        return valor_hecho == valor_regla
    return False

def inferir_riesgo(datos_entrada):
    """
    Evaluo las reglas cargadas contra los datos de entrada.
    """
    hechos = {
        'temperatura': float(datos_entrada.get('temperatura', 0)),
        'humedad': float(datos_entrada.get('humedad', 0)),
        'viento': float(datos_entrada.get('viento', 0)),
    }
    
    # Recorre las reglas en orden de prioridad (del JSON)
    for regla in REGLAS:
        condiciones_cumplidas = 0
        total_condiciones = len(regla['condiciones'])
        
        # Evaluo cada condición de la regla
        for variable, condicion in regla['condiciones'].items():
            if variable in hechos:
                if evaluar_condicion(hechos[variable], condicion['operador'], condicion['valor']):
                    condiciones_cumplidas += 1
        
        if condiciones_cumplidas == total_condiciones:
            # Devuelve el primer nivel de riesgo que se cumpla
            return {
                "nivel": regla["resultado"],
                "accion": regla["accion"],
                "justificacion": f"Se activó la regla ID {regla['id']}: {regla['nombre']}."
            }
            
    # Por defecto
    return {
        "nivel": "NO CLASIFICADO",
        "accion": "El nivel de riesgo no se ajusta a las reglas existentes. Mantener monitoreo.",
        "justificacion": "Ninguna regla de la Base de Conocimiento cumplió todas las condiciones."
    }

# --- Ejecución del Servidor ---
if __name__ == "__main__":
    cargar_reglas()
    init_db() # Inicializa la Base de Datos antes de ejecutar la aplicación
    app.run(debug=True)