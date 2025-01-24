import time
import random
import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from difflib import SequenceMatcher
import unicodedata
from urllib.parse import quote
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# Función para normalizar cadenas
def normalizar_cadena(cadena):
    cadena = cadena.lower()
    cadena = re.sub(r'[^a-záéíóú0-9\s]', '', cadena)  # Eliminar caracteres especiales
    return cadena.strip()

# Función para calcular la similitud entre dos cadenas usando SequenceMatcher
def calcular_similitud(cadena1, cadena2):
    return SequenceMatcher(None, cadena1, cadena2).ratio()

# Función para verificar si los nombres son similares
def comparar_nombres(nombre_producto, item, umbral_similitud=0.8):
    nombre_producto_normalizado = normalizar_cadena(nombre_producto)
    item_normalizado = normalizar_cadena(item)
    similitud = calcular_similitud(nombre_producto_normalizado, item_normalizado)
    return similitud >= umbral_similitud

# Función para realizar scraping en CeX
def scrape_cex(model, umbral_similitud):
    url = f"https://es.webuy.com/search?stext={quote(model)}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        productos = soup.select('.search-product-card')
        precios_por_categoria = {}

        for producto in productos:
            try:
                nombre_producto = producto.select_one(".card-title").text.strip()
                if comparar_nombres(nombre_producto, model, umbral_similitud):
                    precio = producto.select_one(".product-main-price").text.strip().replace('€', '').replace(',', '')
                    categoria = re.search(r'\b[A-Z]$', nombre_producto)
                    categoria = categoria.group() if categoria else "Sin Categoría"
                    
                    try:
                        precio_numero = float(precio)
                        if categoria not in precios_por_categoria:
                            precios_por_categoria[categoria] = []
                        precios_por_categoria[categoria].append(precio_numero)
                    except ValueError:
                        logging.warning(f"Error al convertir el precio: {precio}")
            except Exception as e:
                logging.warning(f"Error al procesar un producto: {e}")

        return {'MODELO': model, 'PRECIOS por CATEGORIA': precios_por_categoria}
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener la página de CeX para {model}: {e}")
        return {'MODELO': model, 'PRECIOS por CATEGORIA': {}}

# Función para realizar scraping en Back Market
def scrape_back_market(model, umbral_similitud):
    url = f"https://www.backmarket.es/es-es/search?q={quote(model)}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        productos = soup.select("a[href^='/es-es/p/']")
        precios_por_categoria = {}

        for producto in productos:
            try:
                nombre_producto = producto.get_text(strip=True)
                if comparar_nombres(nombre_producto, model, umbral_similitud):
                    # Aquí necesitarás un mecanismo para obtener precios, si están disponibles en el HTML
                    precios_por_categoria["General"] = ["Precio no encontrado (HTML dinámico)"]
            except Exception as e:
                logging.warning(f"Error al procesar un producto en Back Market: {e}")

        return {'MODELO': model, 'PRECIOS por CATEGORIA': precios_por_categoria}
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener la página de Back Market para {model}: {e}")
        return {'MODELO': model, 'PRECIOS por CATEGORIA': {}}

# Interfaz de Streamlit
st.title("Scraping y Extracción de Precios")

# Subir archivo CSV
uploaded_file = st.file_uploader("Cargar archivo CSV con la columna 'Modelo'", type="csv")

# Slider para ajustar el umbral de similitud
umbral_similitud = st.slider(
    "Selecciona el umbral de similitud", 
    0.0, 1.0, 0.6, 0.01
)

st.write(f"Umbral de similitud seleccionado: {umbral_similitud}")

# Botón para iniciar el scraping
if st.button('Comenzar Scraping'):
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.write("Datos cargados:")
        if 'Modelo' not in df.columns:
            st.error("El archivo CSV no contiene la columna 'Modelo'.")
            st.stop()
        st.dataframe(df.head())

        cex_results = []
        for _, row in df.iterrows():
            model = row['Modelo']
            result = scrape_cex(model, umbral_similitud)
            cex_results.append(result)
            time.sleep(random.uniform(1, 3))  # Pausa entre solicitudes

        cex_df = pd.DataFrame(cex_results)
        st.write("Resultados de CeX:")
        st.dataframe(cex_df)

        back_market_results = []
        for _, row in df.iterrows():
            model = row['Modelo']
            result = scrape_back_market(model, umbral_similitud)
            back_market_results.append(result)
            time.sleep(random.uniform(1, 3))  # Pausa entre solicitudes

        back_market_df = pd.DataFrame(back_market_results)
        st.write("Resultados de Back Market:")
        st.dataframe(back_market_df)
