import os
import datetime
import logging

import pymongo
import requests
from requests_oauthlib import OAuth1
from lxml import html
from lxml.html import HtmlElement
import azure.functions as func

URL = "https://www.zonakids.com/productos/pack-x-25-sobres-de-figuritas-fifa-world-cup-qatar-2022/"
DOCUMENT_ID = "static-id-434d8917-bcf7-44a6-aa30-7cd84159b39a"


def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().isoformat()
    logging.info('Python timer trigger function ran at %s', utc_timestamp)

    try:
        res = requests.get(URL)
        data: HtmlElement = html.fromstring(res.content)
        value = data.xpath("//form[@id='product_form']//input[@type='submit']/@value")[0]

        if isinstance(value, str):
            uri = os.environ["database_uri"]
            client = pymongo.MongoClient(uri)
            database = client[os.environ["database_name"]]
            collection = database["Figus-Stock"]

            doc = collection.find_one({"_id": DOCUMENT_ID})
            if doc:
                new_fields = {"last_update": utc_timestamp}
                if doc.get("status").upper() != value.upper():
                    new_fields["status"] = value
                    new_fields["last_status_change"] = utc_timestamp
                    new_fields["last_tweet_id"] = tweet_status(value)
                elif doc.get("status").upper() != "SIN STOCK":
                    last_update = datetime.datetime.fromisoformat(doc.get("last_update"))
                    last_status_change = datetime.datetime.fromisoformat(doc.get("last_status_change"))
                    actual_date = datetime.datetime.fromisoformat(utc_timestamp)
                    if (last_update - last_status_change).days < (actual_date - last_status_change).days:
                        post_tweet(f"🔴 STOCK AGOTADO 🔴\nEl pack x25 sobres de figuritas del mundial se encuentra SIN STOCK hace {(actual_date - last_status_change).days} día/s.")
                collection.update_one({"_id": DOCUMENT_ID}, {'$set': new_fields})
                logging.info({'level': 'INFO', 'message': f'Status UPDATED with status [{value}].', 'name': 'check_stock_function'})
            else:
                last_tweet_id = tweet_status(value)
                collection.insert_one({
                    "_id": DOCUMENT_ID,
                    "status": value,
                    "last_update": utc_timestamp,
                    "last_status_change": utc_timestamp,
                    "last_tweet_id": last_tweet_id
                })
                logging.info({'level': 'INFO', 'message': f'Status CREATED with status [{value}].', 'name': 'check_stock_function'})
        else:
            logging.error({'level': 'ERROR', 'message': 'Cannot read value.', 'name': 'check_stock_function'})

    except Exception as e:
        logging.error({'level': 'ERROR', 'message': 'Error checking stock.', 'exception': str(e), 'name': 'check_stock_function'})


def tweet_status(value: str) -> str:
    try:
        if value.upper() == "SIN STOCK":
            tweet_text = "🔴 STOCK AGOTADO 🔴\nEl pack x25 sobres de figuritas del mundial se encuentra agotado."
        else:
            tweet_text = f"🟢 HAY STOCK 🟢\nEl pack x25 sobres de figuritas del mundial se encuentra con stock disponible.\n Conseguilo en {URL}"
        tweet_text += "\n\nSeguime y activá notificaciones para estar informado/a."

        return post_tweet(tweet_text)
    except Exception as e:
        logging.error({'level': 'ERROR', 'message': 'Error tweeting.', 'exception': str(e), 'name': 'check_stock_function'})
        return None


def post_tweet(tweet_text: str) -> str:
    twitter_response = requests.post(
        'https://api.twitter.com/2/tweets',
        json={"text": tweet_text},
        auth=OAuth1(os.environ['api_key'], os.environ['api_secret'], os.environ['access_key'],
                    os.environ['access_secret'])
    )
    logging.info({'level': 'INFO', 'message': 'Status tweeted.', 'name': 'check_stock_function'})
    return twitter_response.json()['data']['id']
