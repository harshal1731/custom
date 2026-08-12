import requests
for url in ["https://paddle-model-ecology.bj.bcebos.com", "https://huggingface.co"]:
    try:
        r = requests.head(url, timeout=30)
        print(url, r.status_code, r.ok)
    except Exception as e:
        print(url, "FAIL", e)
