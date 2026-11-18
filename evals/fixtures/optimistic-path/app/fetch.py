import requests


def first_item(url):
    response = requests.get(url)
    return response.json()["items"][0]


def read_config(path):
    handle = open(path)
    return handle.read()
