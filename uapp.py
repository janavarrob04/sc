import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from difflib import SequenceMatcher
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# Función para normalizar cadenas
def normalizar_cadena(cadena):
    cadena = cadena.lower()
    cadena = re.sub(r'[^a-záéíóú0-9\s]', '', cadena)  # Eliminar caracteres especiales
    return cadena.strip()

# Función para calcular la similitud entre cadenas
def calcular_similitud(cadena1, cadena2):
    return SequenceMatcher(None, cadena1, cadena2).ratio()

# Función para comparar nombres de productos
def comparar_nombres(nombre_producto, item, umbral_similitud=0.8):
    nombre_producto_normalizado = normalizar_cadena(nombre_producto)
    item_normalizado = normalizar_cadena(item)
    similitud = calcular_similitud(nombre_producto_normalizado, item_normalizado)
    return similitud >= umbral_similitud

# Función para scraping de CeX
def scraping_cex(modelo):
    url = f"https://es.webuy.com/search?stext={modelo}"
    response = requests.get(url)
    if response.status_code != 200:
        return {"error": f"Error al acceder a {url}"}
    
    soup = BeautifulSoup(response.text, "html.parser")
    productos = soup.select(".search-product-card")
    precios_por_categoria = {}

    for producto in productos:
        try:
            nombre_producto = producto.select_one(".card-title").text.strip()
            if comparar_nombres(nombre_producto, modelo):
                precio = producto.select_one(".product-main-price").text.strip().replace("€", "").replace(",", "")
                categoria = re.search(r"\b[A-Z]$", nombre_producto)
                categoria = categoria.group() if categoria else "Sin Categoría"
                
                precio_numero = float(precio)
                if categoria not in precios_por_categoria:
                    precios_por_categoria[categoria] = []
                precios_por_categoria[categoria].append(precio_numero)
        except Exception as e:
            logging.warning(f"Error procesando producto: {e}")
    
    return precios_por_categoria

# Interfaz de Streamlit
st.title("Scraping y Extracción de Precios")

# Subir archivo CSV
uploaded_file = st.file_uploader("Sube un archivo CSV con la columna 'Modelo'", type="csv")

# Botón para iniciar scraping
if st.button("Iniciar Scraping"):
    if uploaded_file:
        # Leer el archivo subido
        df = pd.read_csv(uploaded_file)
        st.write("Datos cargados:")
        st.dataframe(df.head())

        if "Modelo" not in df.columns:
            st.error("El archivo CSV debe contener la columna 'Modelo'.")
        else:
            resultados = []
            for modelo in df["Modelo"].head(5):  # Limitar a 5 modelos para pruebas
                st.write(f"Scraping para el modelo: {modelo}")
                precios = scraping_cex(modelo)
                resultados.append({"Modelo": modelo, "Precios": precios})
            
            # Mostrar resultados
            resultados_df = pd.DataFrame(resultados)
            st.write("Resultados del scraping:")
            st.dataframe(resultados_df)
    else:
        st.error("Por favor, sube un archivo CSV.")

