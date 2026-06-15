import requests

PRODUCCION_URL = (
    "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/"
    "resource/b5b58cdc-9e07-41f9-b392-fb9ec68b0725/download/"
    "produccin-de-pozos-de-gas-y-petrleo-no-convencional.csv"
)

response = requests.get(PRODUCCION_URL, stream=True, timeout=30)
print(response.status_code)
print(response.headers.get("content-type"))
print(response.text[:300])