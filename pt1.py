#!/usr/bin/python
# -*- coding: UTF-8 -*-
import twitter,json
from functools import partial
from sys import maxint
import sys
import time
from urllib2 import URLError
from httplib import BadStatusLine



# Função para acessar API do twitter---------------------------------------------------------------------------
def oauth_login():
	CONSUMER_KEY = 'INSERIR CONSUMER_KEY'
	CONSUMER_SECRET = 'INSERIR CONSUMER_SECRET'
	OAUTH_TOKEN = 'INSERIR OAUT_TOKEN'
	OAUTH_TOKEN_SECRET = 'INSERIR OAUTH_TOKEN_SECRET'

	auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET)

	twitter_api = twitter.Twitter(auth=auth)
	return twitter_api
#--------------------------------------------------------------------------------------------------------------




#-----------------------------------------------------------------------------------------------
#Tratamento de possíveis erros

def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw):
    
    
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):
        if wait_period > 3600: # Seconds
            print >> sys.stderr, 'Muitas tentantivas realizadas.Saindo.'
            raise e
      
        if e.e.code == 401:
            print >> sys.stderr, 'Erro 401 encontrado (Não autorizado)'
            return None
        
        elif e.e.code == 404:
            print >> sys.stderr, 'Erro 404 encontrado (Não Encontrado)'
            return None
        
        elif e.e.code == 429:
            print >> sys.stderr, 'Erro 429 encontrado (Limite Excedido)'
            if sleep_when_rate_limited:
                print >> sys.stderr, "Tentando novamente em 15 minutos ... ZzZ ..."
                sys.stderr.flush()
                time.sleep(60*15 + 5)
                print >> sys.stderr, '... ZzZ ... Acordando agora e tentando novamente.'
                return 2
            else:
                raise e # Lida com problema de limitador de taxa
                
        elif e.e.code in (500, 502, 503, 504):
            print >> sys.stderr, 'Erro %i encontrado. Tentando em %i segundos' % \
            (e.e.code, wait_period)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        
        else:
            raise e
            
    # Fim da função interna
    wait_period = 2
    error_count = 0
    
    while True:
        try:
            return twitter_api_func(*args, **kw)
        
        except twitter.api.TwitterHTTPError, e:
            error_count = 0
            wait_period = handle_twitter_http_error(e, wait_period)
            
            if wait_period is None:
                return
            
        except URLError, e:
            error_count += 1
            print >> sys.stderr, "URLError encontrado. Continuando."
            
            if error_count > max_errors:
                print >> sys.stderr, "Muitos erros consecutivos..Saindo."
                raise
                
        except BadStatusLine, e:
            error_count += 1
            print >> sys.stderr, "BadStatusLine encontrado. Continuando."
            if error_count > max_errors:
                print >> sys.stderr, "Muitos Erros consecutivos...Saindo."
                raise
#----------------------------------------------------------------------------------------------


# Pesquisar Tweets-----------------------------------------------------------------------------
def harvest_user_timeline(twitter_api, screen_name=None, user_id=None, max_results=1000):
    assert (screen_name != None) != (user_id != None), \
    "Deve ter screen_name ou user_id, mas não ambos"
    kw = { # Palavra-chave para a chamada API do Twitter
    'count': 200,
    'trim_user': 'true',
    'include_rts' : 'true',
    'since_id' : 1
    }
    
    if screen_name:
        kw['screen_name'] = screen_name
        
    else:
        kw['user_id'] = user_id
        
    max_pages = 16
    results = []
    tweets = make_twitter_request(twitter_api.statuses.user_timeline, **kw)
    
    if tweets is None: # 401 (Não autorizado) - Necessidade de tratar à entrada de loop
        tweets = []
        
    results += tweets
    print >> sys.stderr, 'Encontrado %i tweets' % len(tweets)
    page_num = 1
    
    if max_results == kw['count']:
        page_num = max_pages # Previnir entrada de loop
        
    while page_num < max_pages and len(tweets) > 0 and len(results) < max_results:
        kw['max_id'] = min([ tweet['id'] for tweet in tweets]) - 1
        
        tweets = make_twitter_request(twitter_api.statuses.user_timeline, **kw)
        results += tweets
        
        print >> sys.stderr, 'Encontrado %i tweets' % (len(tweets),)
        page_num += 1
        
    print >> sys.stderr, 'Done fetching tweets'
    return results[:max_results]



#----------------------------------------------------------------------------------------------



#----------------------------------------------------------------------------------------------
#Informações de perfil
def get_user_profile(twitter_api, screen_names=None, user_ids=None):
    # Deve ter o screen_name ou user_id (xor lógico)
    assert (screen_names != None) != (user_ids != None), \
    "Deve ter screen_names ou user_ids, mas não ambos"
    items_to_info = {}
    items = screen_names or user_ids
    
    while len(items) > 0:
        items_str = ','.join([str(item) for item in items[:100]])
        items = items[100:]
        
        if screen_names:
            response = make_twitter_request(twitter_api.users.lookup,
            screen_name=items_str)
            
        else: # user_ids
            response = make_twitter_request(twitter_api.users.lookup,
            user_id=items_str)
            
        for user_info in response:
            
            if screen_names:
                items_to_info[user_info['screen_name']] = user_info
            
            else: # user_ids
                items_to_info[user_info['id']] = user_info
            
    return items_to_info


#----------------------------------------------------------------------------------------------
#obter amigos e ids de seguidores

def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None, 
                              friends_limit=maxint, followers_limit=maxint):
    # Deve ter o screen_name ou user_id (xor lógico)
    assert (screen_name != None) != (user_id != None), \
    "Deve ter screen_names ou user_ids, mas não ambos"

    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids,
    count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids,
    count=5000)
    friends_ids, followers_ids = [], []
    for twitter_api_func, limit, ids, label in [
                                                [get_friends_ids, friends_limit, friends_ids, "friends"],
                                                [get_followers_ids, followers_limit, followers_ids, "followers"]]:
        if limit == 0: continue
        cursor = -1
        while cursor != 0:
            
            if screen_name:
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else: # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)
            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']
            print >> sys.stderr, 'Encontrado{0} total {1} ids para {2}'.format(len(ids),
            label, (user_id or screen_name))
            
            if len(ids) >= limit or response is None:
                break
       
    return friends_ids[:friends_limit], followers_ids[:followers_limit]

#----------------------------------------------------------------------------------------------

###############################################################################################
#MAIN
###############################################################################################
twitter_api = oauth_login()

#----------------------------------------------------------------------------------------------
#Para realizar pesquisa por screen name utiliza as duas linhas abaixo e comente as tres linhas
#de pesquisa por id
#screen="BarackObama"#Insira o Screen Name do usuário que você deseja realizar a pesquisa
#perfil = get_user_profile(twitter_api, screen_names=[screen])
#----------------------------------------------------------------------------------------------

#----------------------------------------------------------------------------------------------
#Para realizar pesquisa pelo id do usuario utilize as quatro linhas abaixo e comente as duas 
#de pesquisa por screen name

id_user = 813286 #Insira o ID do usuário que você deseja realizar a pesquisa
perfil = get_user_profile(twitter_api, user_ids=[id_user])
screen = id_user
screen_name = perfil[id_user]['screen_name']

#----------------------------------------------------------------------------------------------

tweets = harvest_user_timeline(twitter_api, screen_name=screen_name, \
max_results=200)#Acessa a API para pesquisa de tweets

#Acessa a API para pesquisa de amigos e seguidores
friends_ids, followers_ids = get_friends_followers_ids(twitter_api,screen_name=screen_name,friends_limit=10,followers_limit=10)



#---------------------------------------------------------
#Informações do Usuário
id = perfil[screen]['id']
username = perfil[screen]['screen_name']
name = perfil[screen]['name']
location = perfil[screen]['location']
nseguidores = perfil[screen]['followers_count']
nseguidos = perfil[screen]['friends_count']
curtidas = perfil[screen]['favourites_count']
ntweets = perfil[screen]['statuses_count']
desc = perfil[screen]['description']
create = perfil[screen]['created_at']

#---------------------------------------------------------
#Impressão na tela
print "_________________________________________________________________"
print "Programa:Obter perfil do usuário utilizando API do Twitter"
print "Aluno:Thiago Moreira de Freitas"
print "_________________________________________________________________"
print "ID:", id
print "User Name:", username
print "Nome:", name
print "Descrição",desc
print "Local:", location
print "Nro Seguidores:", nseguidores
print "Nro Seguidos:", nseguidos
print "Nro Curtidas:", curtidas
print "Nro Tweets:", ntweets
print "Criação da conta", create
print"_________________________________________________________________"
print "TWEETS\n"
i=0
for t in tweets:
    print tweets[i]['text']
    print "\n"
    i=i+1

    

print"_________________________________________________________________"
print "IDS DE AMIGOS"
print friends_ids
print"_________________________________________________________________"
print "IDS DE SEGUIDORES"
print followers_ids



#----------------------------------------------------------------------------------------------







