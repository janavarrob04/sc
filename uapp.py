import time
import random
import pandas as pd
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
from difflib import SequenceMatcher
import unicodedata
from urllib.parse import quote
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import logging
import os

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# Función para normalizar las cadenas
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

# Función para quitar tildes de los caracteres
def quitar_tildes(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn'
    )

# Función para codificar modelos manteniendo ciertos caracteres
def codificar_modelo(model):
    return quote(model, safe="+")

# Configuración de Selenium para Chrome


def configurar_driverb():
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-browser-side-navigation")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")


    google_chrome_bin = os.getenv('GOOGLE_CHROME_BIN', None)
    if google_chrome_bin:
        options.binary_location = google_chrome_bin

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def configurar_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)
    return driver
    

def obtener_urls_productos(df_for_search):
    urls_productos = {"nombre": [], "url": []}

    driver = configurar_driverb()

    for model in df_for_search.head(5):  # Solo toma los primeros 5 productos como ejemplo
        encoded_model = codificar_modelo(model)
        base_url = "https://www.backmarket.es/es-es/search?q="
        enlace = f"{base_url}{encoded_model}"

        for intento in range(2):  # Intentar abrir la URL dos veces
            try:
                driver.execute_script(f"window.open('{enlace}', '_blank')")
                time.sleep(5)
                driver.switch_to.window(driver.window_handles[-1])

                aceptar_cookies_btn = WebDriverWait(driver, 2).until(
                    EC.visibility_of_element_located((By.XPATH, '//*[@id="__nuxt"]/div/div[3]/div/div[2]/section/div/div/div[2]/button[3]/div/span'))
                )
                aceptar_cookies_btn.click()
                break  # Si se abre correctamente, romper el bucle de reintentos
            except Exception as e:
                logging.warning(f"Error al intentar abrir la URL {enlace}: {e}")
                if intento == 1:  # Si es el último intento, registrar el error
                    logging.error(f"No se pudo abrir la URL {enlace} tras dos intentos")

        try:
            WebDriverWait(driver, 2).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href^='/es-es/p/']"))
            )
            primer_producto = driver.find_element(By.CSS_SELECTOR, "a[href^='/es-es/p/']")
            url = primer_producto.get_attribute("href")

            urls_productos["nombre"].append(model)
            urls_productos["url"].append(url)
        except Exception as e:
            logging.warning(f"No se encontraron productos para el modelo {model}. Error: {e}")

        driver.close()
        driver.switch_to.window(driver.window_handles[0])

    driver.quit()
    return 


# Función para calcular la mediana por modelo
def calcular_mediana_por_modelo(df):
    medianas = []
    for index, row in df.iterrows():
        modelo = row['MODELO']
        for columna in ['Cex A', 'Cex B', 'Cex C', 'Cex Sin Categoria', 'Bueno', 'Usado', 'Perfecto']:
            if columna in row:  # Verificar si la columna existe
                valores = row[columna]
                if isinstance(valores, list):
                    valores = pd.Series(valores).astype(float)
                    mediana = valores.median()
                    medianas.append({
                        'Modelo': modelo,
                        'Categoría': columna,
                        'Mediana': mediana
                    })
    df_medianas = pd.DataFrame(medianas)
    df_medianas = df_medianas.groupby(['Modelo', 'Categoría'], as_index=False).agg({'Mediana': 'median'})
    df_medianas_pivot = df_medianas.pivot(index='Modelo', columns='Categoría', values='Mediana').reset_index()
    return df_medianas_pivot

# Interfaz de Streamlit
st.title("Scraping y Extracción de Precios")

# Selección de scraping a ejecutar
scraping_options = st.multiselect(
    "Selecciona los scraping que deseas ejecutar:",
    options=["CeX", "Cash Converters", "Back Market"],
    default=["CeX", "Cash Converters", "Back Market"]
)

# Slider para ajustar el umbral de similitud
umbral_similitud = st.slider(
    "Selecciona el umbral de similitud", 
    0.0, 1.0, 0.6, 0.01
)

st.write(f"Umbral de similitud seleccionado: {umbral_similitud}")

# Subir archivo CSV
uploaded_file = st.file_uploader("Cargar archivo CSV con la columna 'Modelo'", type="csv")

# Botón para iniciar el scraping
if st.button('Comenzar Scraping'):

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.write("Datos cargados:")
        if 'Modelo' not in df.columns:
            st.error("El archivo CSV no contiene la columna 'Modelo'.")
            st.stop()
        st.dataframe(df.head())
        if "CeX" in scraping_options:
            # Proceso de scraping para CeX
            # Proceso de scraping para CeX
            cex2 = []
            progress_bar = st.progress(0)

            for idx, row in df.head().iterrows():
                item = row['Modelo']
                st.write(f'Procesando {idx + 1}/{len(df)}: {item}')
                url = f'https://es.webuy.com/search?stext={item}'

                for intento in range(2):  # Intentar abrir la URL dos veces
                    try:
                        driver = configurar_driver()
                        driver.get(url)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.search-product-card'))
                        )
                        break  # Si se abre correctamente, romper el bucle de reintentos
                    except Exception as e:
                        logging.warning(f"Error al intentar abrir la URL {url}: {e}")
                        if intento == 1:  # Si es el último intento, registrar el error
                            logging.error(f"No se pudo abrir la URL {url} tras dos intentos")
                            cex2.append({'MODELO': item, 'PRECIOS por CATEGORIA': {}})
                            continue

                productos = driver.find_elements(By.CSS_SELECTOR, '.search-product-card')
                precios_por_categoria = {}

                for producto_element in productos:
                    try:
                        nombre_producto = producto_element.find_element(By.CSS_SELECTOR, ".card-title").text
                        if comparar_nombres(nombre_producto, item, umbral_similitud):
                            precio = producto_element.find_element(By.CSS_SELECTOR, ".product-prices > div.price-wrapper > p.product-main-price").text
                            categoria = re.search(r'\b[A-Z]$', nombre_producto)
                            categoria = categoria.group() if categoria else "Sin Categoría"

                            precio_texto = precio.replace('€', '').strip()
                            precio_texto = precio_texto.replace(',', '')
                            try:
                                precio_numero = float(precio_texto)
                                if categoria not in precios_por_categoria:
                                    precios_por_categoria[categoria] = []
                                precios_por_categoria[categoria].append(precio_numero)
                            except ValueError:
                                st.warning(f"Error al convertir el precio: {precio_texto}")
                    except Exception as e:
                        st.warning(f"Error al procesar un producto: {e}")

                if precios_por_categoria:
                    cex2.append({'MODELO': item, 'PRECIOS por CATEGORIA': precios_por_categoria})
                else:
                    st.warning(f"No se encontraron productos similares para el modelo {item}.")
                driver.quit()

                time.sleep(random.uniform(1, 3))

                progress_bar.progress((idx + 1) / len(df))

            cex2_df = pd.DataFrame(cex2)
            data = []
            for index, row in cex2_df.iterrows():
                modelo = row['MODELO']
                precios_categoria = row['PRECIOS por CATEGORIA']
                row_data = {'MODELO': modelo}
                for categoria, precios in precios_categoria.items():
                    row_data[categoria] = precios
                data.append(row_data)
            cex2_organizado_df = pd.DataFrame(data)
            cex2_organizado_df.rename(columns={
                'A': 'Cex A',
                'B': 'Cex B',
                'C': 'Cex C',
                'Sin Categoria': 'Cex Sin Categoria'
            }, inplace=True)
            #st.write("Datos Organizados de CeX:")
            #st.dataframe(cex2_organizado_df)

        if "Cash Converters" in scraping_options:
            # Proceso de scraping para Cash Converters
            cashconverters = []
            progress_bar = st.progress(0)

            for idx, row in df.head().iterrows():
                item = row['Modelo']
                st.write(f'Procesando {idx + 1}/{len(df)}: {item}')
                url = f'https://www.cashconverters.es/es/es/search/?q={item}'
                precios_por_estado = {}

                try:
                    driver = configurar_driver()
                    driver.get(url)
                    try:
                        aceptar_cookies = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "button#cookies-accept"))
                        )
                        aceptar_cookies.click()
                    except Exception as e:
                        logging.warning(f"No se pudo aceptar las cookies: {e}")

                    WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".tile-body.available"))
                    )
                    productos = driver.find_elements(By.CSS_SELECTOR, ".tile-body.available")
                    for producto in productos:
                        try:
                            nombre_producto = producto.find_element(By.CSS_SELECTOR, ".pdp-link > a").get_attribute("title")
                            if not comparar_nombres(nombre_producto, item, umbral_similitud):
                                continue
                            precio = float(producto.find_element(By.CSS_SELECTOR, "div.principal").get_attribute("data-price"))
                            estado = producto.find_element(By.CSS_SELECTOR, "div.status").text.strip()
                            if estado not in precios_por_estado:
                                precios_por_estado[estado] = []
                            precios_por_estado[estado].append(precio)
                        except Exception as e:
                            st.warning(f"Error al procesar un producto: {e}")

                    if precios_por_estado:
                        cashconverters.append({'MODELO': item, 'PRECIOS por ESTADO': precios_por_estado})
                    else:
                        st.warning(f"No se encontraron productos similares para el modelo {item}.")
                    driver.quit()
                except Exception as e:
                    st.warning(f"Error al obtener la página para {item}: {e}")
                    cashconverters.append({'MODELO': item, 'PRECIOS por ESTADO': {}})

                progress_bar.progress((idx +1)/ len(df))

            cashconvertersdf = pd.DataFrame(cashconverters)
            data = []
            for index, row in cashconvertersdf.iterrows():
                modelo = row['MODELO']
                precios_categoria = row['PRECIOS por ESTADO']
                row_data = {'MODELO': modelo}
                for categoria, precios in precios_categoria.items():
                    row_data[categoria] = precios
                data.append(row_data)
            cash_organizado_df = pd.DataFrame(data)

            #st.write("Datos Organizados de Cash Converters:")
            #st.dataframe(cash_organizado_df)
        # Proceso de scraping para Back Market
        if "Back Market" in scraping_options:
            df_for_search = df['Modelo'].str.replace(" ", "+", regex=False)
            df_for_search = df_for_search.apply(quitar_tildes)
            
            with st.spinner('Extrayendo URLs de Back Market...'):
                urls_df = obtener_urls_productos(df_for_search)

            urls_productos = pd.DataFrame(urls_df)

            urls_productos["nombre"] = urls_productos["nombre"].str.replace("+", " ")
            urls_productos["nombre"] = urls_productos["nombre"].astype(str) 
            urls_productos["nombre"] = urls_productos["nombre"].str.replace("+", " ")

            resultados = pd.DataFrame()
            cookies_aceptadas = False

            driver = configurar_driverb()
            progress_bar = st.progress(0)

            for index, row in urls_productos.iterrows():
                url = row["url"]
                nombre = row["nombre"]

                for intento in range(2):  # Intentar abrir la URL dos veces
                    try:
                        driver.execute_script(f"window.open('{url}', '_blank')")
                        time.sleep(5)
                        driver.switch_to.window(driver.window_handles[1])

                        if not cookies_aceptadas:
                            aceptar_cookies_btn = WebDriverWait(driver, 5).until(
                                EC.visibility_of_element_located((By.XPATH, '//*[@id="__nuxt"]/div/div[3]/div/div[2]/section/div/div/div[2]/button[3]/div/span'))
                            )
                            aceptar_cookies_btn.click()
                            cookies_aceptadas = True
                            logging.info(f"Cookies aceptadas para {url}")
                        break  # Si se abre correctamente, romper el bucle de reintentos
                    except Exception as e:
                        logging.warning(f"Error al intentar abrir la URL {url}: {e}")
                        if intento == 1:  # Si es el último intento, registrar el error
                            logging.error(f"No se pudo abrir la URL {url} tras dos intentos")

                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class, 'body-2') or contains(@class, 'mr-8')]"))
                )

                html_content = driver.page_source
                soup = BeautifulSoup(html_content, 'html.parser')

                nombrebackmarket = soup.find('h1', class_='heading-1').get_text(strip=True) if soup.find('h1', class_='heading-1') else "Desconocido"
                precios = soup.find_all('span', class_=re.compile(r'^body-2'))
                precios_texto = [precio.get_text(strip=True).replace('€', '').replace(',', '.').replace('\xa0', '') for precio in precios]

                precios_numeros = []
                for precio in precios_texto:
                    if "¡agotado!" in precio.lower():
                        precios_numeros.append("¡Agotado!")
                    else:
                        try:
                            precios_numeros.append(float(precio))
                        except ValueError:
                            continue

                caracteristicas = soup.find_all('span', class_=re.compile(r'mr-8'))
                caracteristicas_texto = [caracteristica.get_text(strip=True) for caracteristica in caracteristicas]

                max_len = max(len(caracteristicas_texto), len(precios_numeros))
                caracteristicas_texto.extend(['No disponible'] * (max_len - len(caracteristicas_texto)))
                precios_numeros.extend(['No disponible'] * (max_len - len(precios_numeros)))

                data = {'nombre': [nombre], 'nombrebackmarket': [nombrebackmarket]}
                for i, caracteristica in enumerate(caracteristicas_texto):
                    data[caracteristica] = [precios_numeros[i]]

                df_producto = pd.DataFrame(data)
                df_producto = df_producto.loc[:, ~df_producto.columns.isin(["No", "Me hago un renove"])]

                resultados = pd.concat([resultados, df_producto], ignore_index=True)
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

                progress_bar.progress((index + 1) / len(urls_productos))

            driver.quit()


            # Eliminar columnas si existen
            columnas_a_eliminar = ["nombrebackmarket", "Sin renove", "+2", "+3"]
            for columna in columnas_a_eliminar:
                if columna in resultados.columns:
                    resultados = resultados.drop(columns=[columna])

            # Filtrar resultados por las columnas especificadas si existen
            columnas_filtrado = ["nombre", "Correcto", "Muy bueno", "Excelente", "Prémium", "Batería estándar", "Batería nueva"]
            columnas_filtrado_existen = [columna for columna in columnas_filtrado if columna in resultados.columns]
            
            
            if columnas_filtrado_existen:
                resultadosbm = resultados[columnas_filtrado_existen]
                resultadosbm.rename(columns={"nombre": "Modelo"}, inplace=True)
                

        # Calcular medianas y combinar dataframes
        cex2_medianas = calcular_mediana_por_modelo(cex2_organizado_df) if "CeX" in scraping_options else pd.DataFrame()
        cash_medianas = calcular_mediana_por_modelo(cash_organizado_df) if "Cash Converters" in scraping_options else pd.DataFrame()
        resultados = resultadosbm if "Back Market" in scraping_options else pd.DataFrame()

        if not cex2_medianas.empty:
            df = df.merge(cex2_medianas, on='Modelo', how='left')
        if not cash_medianas.empty:
            df = df.merge(cash_medianas, on='Modelo', how='left')
        if not resultados.empty:
            df = df.merge(resultados, on='Modelo', how='left')

        # Mostrar DataFrames combinados
        st.write("DataFrame:")
        st.dataframe(df)



        # Botón para descargar DataFrame combinado
        csv_combinado = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar DataFrame como CSV",
            data=csv_combinado,
            file_name='df_combinado.csv',
            mime='text/csv'
        )
