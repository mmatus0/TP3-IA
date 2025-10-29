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


  # ----- Base de Datos - SQLite ----- 


def init_db():
    """Inicializa la BDD para almacenar el historial de riesgos""" 
    with sqlite3.connect(DB_NAME) as connexion: 
        cursor = connexion.cursor()
        cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS diagnosticos( 
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            temperatura REAL,
            humedad REAL, 
            viento REAL, 
            nivel_riesgo TEXT,
            justificacion TEXT
        )
        ''') 
        connexion.commit()


def guardar_diagnostico(datos_entrada, resultado):
    """Almacena el riesgo y los hechos en la BDD"""
    with sqlite3.connect(DB_NAME) as connexion: 
        cursor = connexion.cursor()
        cursor.execute('''
        INSERT INTO diagnosticos
            (fecha, temperatura, humedad, viento, nivel_riesgo, justificacion)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            datos_entrada.get('temperatura'),
            datos_entrada.get('humedad'),
            datos_entrada.get('viento'),
            resultado['nivel'],
            resultado['justificacion']
        )) 
        connexion.commit()
                       
def obtener_diagnosticos():
    """Obtiene el historial de riesgos (limitado a 10 registros recientes)."""
    with sqlite3.connect(DB_NAME) as connexion:
        cursor = connexion.cursor()
        cursor.execute("SELECT fecha, temperatura, humedad, viento, nivel_riesgo FROM diagnosticos ORDER BY id DESC LIMIT 10")
        return cursor.fetchall()  



# ------ Flask -----
@app.route("/", methods=["GET", "POST"])
def index():
    cargar_reglas()
    resultado = None
    datos_entrada_display = {}
    registros = obtener_diagnosticos() # Carga el historial al abrir la página

    if request.method == "POST":
        # Recolectar hechos (datos de entrada)
        datos_entrada = {
            'temperatura': request.form.get('temperatura'),
            'humedad': request.form.get('humedad'),
            'viento': request.form.get('viento')
        }
       
        datos_entrada_display = datos_entrada
       
        # Llamar al Motor de Inferencia
        resultado = inferir_riesgo(datos_entrada)
       
        # Guardar el nuevo riesgo y recargar el historial
        guardar_diagnostico(datos_entrada, resultado)
        registros = obtener_diagnosticos()

    # Renderizar la plantilla HTML
    return render_template("index.html",
                           resultado=resultado,
                           datos_entrada=datos_entrada_display,
                           registros=registros)

    # --- Función para Pruebas de Inferencia ---

def ejecutar_pruebas_de_inferencia():
    """Define y ejecuta casos de prueba para validar el motor de inferencia (Reglas 1, 2, 3, 4)."""
    print("\n--- Ejecutando Pruebas de Inferencia ---")
    
    # Asegura que las reglas estén cargadas antes de la prueba
    cargar_reglas() 
    
    # Definición de Casos de Prueba (Hechos -> Resultado Esperado)
    # NOTA: Los casos que antes usaban la Regla 5 ahora deben caer en MEDIO o ALTO (Regla 2).
    casos_prueba = [
        # Caso 1: Extremo - Activa Regla 1
        ("EXTREMO", {'temperatura': 40.0, 'humedad': 15.0, 'viento': 25.0}), 
        
        # Caso 2: Alto - Activa Regla 2
        ("ALTO", {'temperatura': 35.0, 'humedad': 40.0, 'viento': 31.0}),
        
        # Caso 3: Medio - Activa Regla 3 (T=37.0 > 30, H=30 <= 50)
        ("MEDIO", {'temperatura': 37.0, 'humedad': 30.0, 'viento': 15.0}), 
        
        # Caso 4: Medio - Activa Regla 3
        ("MEDIO", {'temperatura': 30.1, 'humedad': 50.0, 'viento': 10.0}), 
        
        # Caso 5: Bajo - Activa Regla 4
        ("BAJO", {'temperatura': 20.0, 'humedad': 60.0, 'viento': 5.0}),
        
        # Caso 6: (Ajustado) - Activa Regla 4 - Resultado esperado cambiado a BAJO
        ("BAJO", {'temperatura': 5.0, 'humedad': 95.0, 'viento': 2.0}) 
    ]
    
    fallos = 0
    for esperado, hechos in casos_prueba:
        resultado = inferir_riesgo(hechos)
        obtenido = resultado['nivel']
        
        if obtenido == esperado:
            print(f"PASA: Caso {esperado} | Entrada: {hechos}")
        else:
            print(f"FALLA: Caso {esperado} | ESPERADO: {esperado}, OBTENIDO: {obtenido} | Regla activada: {resultado['justificacion']}")
            fallos += 1

    print(f"\n--- Resumen de Pruebas: {len(casos_prueba)} ejecutadas, {fallos} fallos. ---")
    return fallos == 0

# --- Ejecución del Servidor ---
if __name__ == "__main__":
    cargar_reglas()
    ejecutar_pruebas_de_inferencia()
    init_db() # Inicializa la Base de Datos antes de ejecutar la aplicación
    app.run(debug=True)