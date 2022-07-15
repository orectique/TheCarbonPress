import tweepy

from newsapi import NewsApiClient
import datetime
from datetime import datetime as dt

import os
from dotenv import load_dotenv

import bitly_api

import nltk

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk import pos_tag

import string

from rake_nltk import Rake

import random

import time
import re

rake = Rake()

stop_words = set(stopwords.words('english'))

load_dotenv()

consumer_key = os.environ.get('CONSUMER_KEY')
consumer_secret = os.environ.get('CONSUMER_SECRET')

access_key = os.environ.get('ACCESS_KEY')
access_secret = os.environ.get('ACCESS_SECRET')

news_api = os.environ.get('NEWS_API')

bitly_token = os.environ.get('BITLY_TOKEN')

sources = 'al-jazeera-english, associated-press, bloomberg, business-insider, cbs-news, cnn, fortune, google-news, msnbc, nbc-news, reuter, the-huffington-post, the-verge, the-wall-street-journal, the-washington-post, the-washington-times, time'
query = 'carbon AND (emissions OR climate OR gas OR coal OR energy OR green OR oil OR fuel OR fuels OR power) AND (decarbonize OR decarbonization OR decarbonise OR decarbonisation OR decarboniznig OR decarbonising)'

listTexts = [
    '{} {} / {} - Followed by this one from {}. {} {}',
    '{} {} / {} - And this one from {}. {} {}',
    '{} {} / {} - This article from {} should be an interesting read. {} {}',
    '{} {} / {} - Next, on to an article from {}. {} {}',
    '{} {} / {} - Next up, what does {} have to say on the topic?. {} {}',
    '{} {} / {} - {} had to say this on the subject. {} {}',
    '{} {} / {} - An article from {} is next. {} {}'
]

def raking(text):
    text = text.translate(str.maketrans('', '', string.punctuation))

    rake.extract_keywords_from_text(text)
    phrases = rake.get_ranked_phrases()

    rake.extract_keywords_from_text(' '.join(phrases))
    phrases = rake.get_ranked_phrases()

    return [token for token in word_tokenize(''.join(phrases)) if ((not token.lower() in stop_words) and (len(token) > 1) and (not pos_tag([token])[0][1] in ['JJ', 'JJR', 'JJS', 'DT', 'PDT', 'PRP', 'RB', 'RBR', 'RBS', 'RP', 'WRB', 'VBZ', 'VBP', 'VBN', 'VBG', 'VBD', 'VB']))]

def generateHashtags(keywords, source):
    pattern = re.compile(r'\s+')
    source = re.sub(pattern, '', source.lower())

    tags = f"{'#' + source} #decarbonization #decarbonisation"

    keys = ' '.join(keywords)

    if 'epa' in keys: 
        tags += ' #epa'
    if ('supreme' in keys) and ("court" in keys):
        tags += ' #scotus'

    for key in keywords[:3]:
        tags += ' #' + str(key)

    return tags

def payload(i, count, hashtags, bitURL, source, yday):
    if count != 1:
        if i == 1:
            return(f"On {yday.strftime('%A, %d %b %Y')}, there were {count} articles that discussed decarbonization. We recommend starting here at this one from {source}. {hashtags} {bitURL}")
        
        elif i in range(2, count):
           return(str(random.sample(listTexts, 1)[0]).format(yday.strftime('%A, %d %b %Y'), i, count, source, hashtags, bitURL))
        
        elif i == count:
            return(f"{yday.strftime('%A, %d %b %Y')} - And at last, this article from {source}. {hashtags} {bitURL}")
            
    
    return(f"On {yday.strftime('%A, %d %b %Y')}, there was one article that discussed decarbonization, from {source}. {hashtags} {bitURL}")

def runBot(request):

    newsapi = NewsApiClient(api_key=news_api)

    #yday = datetime.date.today() - datetime.timedelta(days=1)

    yday = dt.strptime('2022-06-28', '%Y-%m-%d')

    articles = newsapi.get_everything(
        q = query,
        sources = sources,
        from_param = yday, 
        to = yday,
        language = 'en',
        sort_by = 'popularity'
    )

    count = articles['totalResults']
    
    if count != 0:
        bitly = bitly_api.Connection(access_token=bitly_token)
        
        client = tweepy.Client(consumer_key=consumer_key, consumer_secret=consumer_secret, access_token=access_key, access_token_secret=access_secret)

        for i in range(1, count + 1):
            article = articles['articles'][i - 1]

            keywords = raking(article['description'])
            
            bitURL = bitly.shorten(article['url'])['url']

            source = article['source']['name']

            hashtags = generateHashtags(keywords, source)
        
            outText = payload(i, count, hashtags, bitURL, source, yday)

            client.create_tweet(text = outText)
            print('Tweeted')

            time.sleep(1)


    
