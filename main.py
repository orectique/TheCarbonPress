import tweepy

from newsapi import NewsApiClient
import datetime
from datetime import datetime as dt

import os

import bitly_api

#import nltk

#nltk.download('averaged_perceptron_tagger')
#nltk.download('stopwords')
#nltk.download('punkt')

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk import pos_tag

import string
import pandas as pd

from rake_nltk import Rake

import random

import time
import re

from dotenv import load_dotenv

load_dotenv()

import plotly.express as px

from pymongo import MongoClient

rake = Rake()

stop_words = set(stopwords.words('english'))

consumer_key = os.environ.get('CONSUMER_KEY')
consumer_secret = os.environ.get('CONSUMER_SECRET')

access_key = os.environ.get('ACCESS_KEY')
access_secret = os.environ.get('ACCESS_SECRET')

news_api = os.environ.get('NEWS_API')

bitly_token = os.environ.get('BITLY_TOKEN')

sources = 'al-jazeera-english, associated-press, bloomberg, business-insider, cbs-news, cnn, fortune, google-news, msnbc, nbc-news, reuter, the-huffington-post, the-verge, the-wall-street-journal, the-washington-post, the-washington-times, time'
#query = 'carbon AND (emissions OR climate OR gas OR coal OR energy OR green OR oil OR fuel OR fuels OR power) AND (decarbonize OR decarbonization OR decarbonise OR decarbonisation OR decarboniznig OR decarbonising)'

query = 'carbon AND (emissions OR climate OR gas OR coal OR energy OR green OR oil OR fuel OR fuels OR power) AND (tax OR tariff OR pricing OR inflation OR decarbonize OR decarbonization OR decarbonise OR decarbonisation OR decarboniznig OR decarbonising)'

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
    print('raking')
    text = text.translate(str.maketrans('', '', string.punctuation))

    rake.extract_keywords_from_text(text)
    phrases = rake.get_ranked_phrases()

    rake.extract_keywords_from_text(' '.join(phrases))
    phrases = rake.get_ranked_phrases()

    return [token for token in word_tokenize(''.join(phrases)) if ((not token.lower() in stop_words) and (len(token) > 1) and (not pos_tag([token])[0][1] in ['JJ', 'JJR', 'JJS', 'DT', 'PDT', 'PRP', 'RB', 'RBR', 'RBS', 'RP', 'WRB', 'VBZ', 'VBP', 'VBN', 'VBG', 'VBD', 'VB']))]

def generateHashtags(keywords, source):
    print('generating hashtags')
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
    print('payload')
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

    #today = datetime.datetime.today()

    today = datetime.datetime(2022, 8, request)

    yday = today - datetime.timedelta(days=1)

    articles = newsapi.get_everything(
        q = query,
        sources = sources,
        from_param = yday, 
        to = yday,
        language = 'en',
        sort_by = 'popularity'
    )

    count = articles['totalResults']

    print(yday, count)

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)

    auth.set_access_token(access_key, access_secret)

    api = tweepy.API(auth)

    print(api)

    client = MongoClient(f"mongodb+srv://orectique:{os.getenv('DB_P')}@orectique.ixj7l.mongodb.net/?retryWrites=true&w=majority")

    db = client['decarbNews']   

    table = db['carbonArchive']

    sourcesDB = [article['source']['name'] for article in articles['articles']]

    table.update_one({'date': yday}, { '$set' : {'count' : count, 'source': sourcesDB}}, upsert=True)

    if today.weekday() == 6:
        frameDict = {
    'dates' : [],
    'counts' : []
    }  

        downRange = yday - datetime.timedelta(days=31)

        dateCur = table.find({'date' : { '$gt': downRange }})
        frameDict['dates'] = [doc['date'] for doc in dateCur]
        
        countCur = table.find({'date' : { '$gt': downRange }})
        frameDict['counts'] = [doc['count'] for doc in countCur]

        frame = pd.DataFrame(frameDict)
        frame = frame.sort_values(by='dates', ascending=True)

        figLine = px.line(
                x = frame['dates'], 
                y = frame['counts'], 
                template='plotly_dark',
                labels = {
                    'x': 'Date',
                    'y': 'Number of flagged artcles'
                }, 
                title=f'Publication Trends - Last {len(frame)} Days')
       
        figLine.write_image('./dump/plotLine.png')

        api.update_status_with_media(status=f"In the last {len(frame)} days there were {sum(frame['counts'])} articles that our filter flagged.", filename='./dump/plotLine.png')
                
        os.remove('./dump/plotLine.png')

        sourceCur = table.find({'date' : { '$gt': downRange }})

        sourcesPie = []

        for doc in sourceCur:
            for source in doc['source']:
                sourcesPie.append(source)

        sourcesPie = pd.DataFrame(sourcesPie, columns=['Source'])
        sourcesPie = sourcesPie.value_counts()
        sourcesPie = sourcesPie.reset_index()
        sourcesPie.columns = ['Source', 'Count']

        figPie = px.pie(sourcesPie, values = 'Count', names = 'Source', template = 'plotly_dark', title = f'Distribution of Sources (last {len(frame)} days)', hole = 0.5, color_discrete_sequence=px.colors.diverging.Fall)

        figPie.write_image('./dump/plotPie.png')

        api.update_status_with_media(status=f"In the last {len(frame)} days, there were {sum(frame['counts'])} articles that our filter flagged. Here is a breakdown of the sources that were used.", filename='./dump/plotPie.png')
        
        os.remove('./dump/plotPie.png')

    if count != 0:
        bitly = bitly_api.Connection(access_token=bitly_token)
        
        for i in range(1, count + 1):
            article = articles['articles'][i - 1]

            keywords = raking(article['description'])
            
            bitURL = bitly.shorten(article['url'])['url']

            source = article['source']['name']

            hashtags = generateHashtags(keywords, source)
        
            outText = payload(i, count, hashtags, bitURL, source, yday)

            api.update_status(status = outText)
            print('tweeted')

            time.sleep(10)

    print('done')

    return 'OK'

for i in range(14, 21):
    runBot(i)