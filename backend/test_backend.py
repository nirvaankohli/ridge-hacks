import requests

BASE_URL = "http://127.0.0.1:8000"

def test_date_to_class_api() -> None:

    date = "2024-01-01"
    endpoint = f"{BASE_URL}/model/predict"
    date = "2024-05-07"
    latitude = 55.0

    payload = {
        "date": date,
        "latitude": latitude,
    }

    response = requests.post(endpoint, headers={"Content-Type": "application/json"}, json=payload)

    print(f"status_code={response.status_code}"
          f"response={response.text}"
    )

if __name__ == "__main__":

    test_date_to_class_api()