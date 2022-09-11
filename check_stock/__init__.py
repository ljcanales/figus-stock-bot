import os
import datetime
import logging

import pymongo
import requests
import tweepy
from lxml import html
from lxml.html import HtmlElement
import azure.functions as func

URL = "https://www.zonakids.com/productos/pack-x-25-sobres-de-figuritas-fifa-world-cup-qatar-2022/"
DOCUMENT_ID = "static-id-434d8917-bcf7-44a6-aa30-7cd84159b39a"


def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
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
                    new_fields["last_tweet_id"] = tweet_status(value)
                collection.update_one({"_id": DOCUMENT_ID}, new_fields)
                logging.info({'level': 'INFO', 'message': 'Status updated.', 'name': 'check_stock_function'})
            else:
                last_tweet_id = tweet_status(value)
                collection.insert_one({
                    "_id": DOCUMENT_ID,
                    "status": value,
                    "last_update": utc_timestamp,
                    "last_tweet_id": last_tweet_id
                })
        else:
            logging.error({'level': 'ERROR', 'message': 'Cannot read value.', 'name': 'check_stock_function'})

    except Exception as e:
        logging.error({'level': 'ERROR', 'message': 'Error checking stock.', 'exception': str(e), 'name': 'check_stock_function'})


def tweet_status(value: str) -> str:
    try:
        auth = tweepy.OAuthHandler(os.environ['api_key'], os.environ['api_secret'])
        auth.set_access_token(os.environ['access_key'], os.environ['access_secret'])
        twitter_conn = tweepy.API(auth, wait_on_rate_limit=True)

        if value.upper() == "SIN STOCK":
            tweet_text = "🔴 Stock agotado 🔴"
        else:
            tweet_text = "🟢 Hay Stock 🟢"
        tweet_text += "\nSeguime y activá notificaciones para estar informado/a."

        tweet_id = twitter_conn.update_status(status=tweet_text).id_str
        logging.info({'level': 'INFO', 'message': 'Status tweeted.', 'name': 'check_stock_function'})
        return tweet_id
    except Exception as e:
        logging.error({'level': 'ERROR', 'message': 'Error tweeting.', 'exception': str(e), 'name': 'check_stock_function'})
        return None



