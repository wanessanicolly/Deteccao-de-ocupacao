from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

# Caminho completo para o chromedriver extraído
service = Service("C:\\Users\\Aluno\\Downloads\\chromedriver-win64\\chromedriver-win64\\chromedriver.exe")


driver = webdriver.Chrome(service=service)
driver.get("http://127.0.0.1:5000")

time.sleep(3)

element = driver.find_element(By.TAG_NAME, "body")
assert "Realizar Predição" in element.text

driver.quit()
