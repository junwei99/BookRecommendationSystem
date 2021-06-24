from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import linear_kernel, cosine_similarity
from math import sqrt

import os
import sys
import random
import math
import numpy as np
import pandas as pd
import scipy


def popular_books(books, num_of_books):
    top_books = []
    for i in range(num_of_books):
        book = books.iloc[i]
        book['rank'] = i + 1

        # Remove newlines 
        book['title'] = book['title'].strip()
        book['authors'] = book['authors']
        top_books.append(book)

    return top_books

def display_books(books, num_of_books):
    top_books = []
    for i in range(num_of_books):
        book = books.iloc[i]
        book['rank'] = i + 1
        top_books.append(book)
    
    return top_books 

def df_to_list(df):
    top_list = []
    top_list = df.values.tolist()
    return top_list



def similar_books(books, booktitle, n=100):
    count = CountVectorizer(analyzer='word',ngram_range=(1, 2),min_df=0, stop_words='english')
    count_matrix = count.fit_transform(books['soup'])
    cosine_sim = cosine_similarity(count_matrix, count_matrix)
    indices = pd.Series(books.index, index=books['title'])
    titles = books['title']
    idx = indices[booktitle]
    similar_index = list(enumerate(cosine_sim[idx]))
    similar_index = sorted(similar_index, key=lambda x: x[1], reverse=True)
    similar_index = similar_index[1:101]
    book_index = [i[0] for i in similar_index]
    df = books.iloc[book_index][['book_id','ratings_count','average_rating', 'weighted_rating']]

    v = df['ratings_count']
    m = df['ratings_count'].quantile(0.50)
    R = df['average_rating']
    C = df['average_rating'].mean()
    df['weighted_rating'] = (R*v + C*m) / (v + m)
    
    output = df[df['ratings_count'] >= m]
    output = output.sort_values('weighted_rating', ascending=False)
    # output = output.values.tolist()
    return output

def collab_filtering_recs(rec_ratings, books, ratings):
    userInput = pd.DataFrame(rec_ratings)
    inputId = books[books['title'].isin(userInput['title'].tolist())]
    userInput = pd.merge(inputId, userInput)
    userSubset = ratings[ratings['book_id'].isin(userInput['id'].tolist())]
    userSubsetGroup = userSubset.groupby(['user_id'])
    userSubsetGroup = sorted(userSubsetGroup, key=lambda x: len(x[1]), reverse=True)
    pearsonCorrelationDict = {}
    for name, group in userSubsetGroup:
        group = group.sort_values(by='book_id')
        nRatings = len(group)
        temp_df = userInput[userInput['id'].isin(group['book_id'].tolist())]
        tempRatingList = temp_df['rating'].tolist()
        tempGroupList = group['rating'].tolist()
        Sxx = sum([i**2 for i in tempRatingList]) - pow(sum(tempRatingList),2)/float(nRatings)
        Syy = sum([i**2 for i in tempGroupList]) - pow(sum(tempGroupList),2)/float(nRatings)
        Sxy = sum( i*j for i, j in zip(tempRatingList, tempGroupList)) - sum(tempRatingList)*sum(tempGroupList)/float(nRatings)
        if Sxx != 0 and Syy != 0:
            pearsonCorrelationDict[name] = Sxy/sqrt(Sxx*Syy)
        else:
            pearsonCorrelationDict[name] = 0
    pearsonDF = pd.DataFrame.from_dict(pearsonCorrelationDict, orient='index')
    pearsonDF.columns = ['similarityIndex']
    pearsonDF['user_id'] = pearsonDF.index
    pearsonDF.index = range(len(pearsonDF))
    topUsers=pearsonDF.sort_values(by='similarityIndex', ascending=False)[0:50]
    topUsersRating=topUsers.merge(ratings, left_on= 'user_id', right_on= 'user_id', how='inner')
    topUsersRating['weightedRating'] = topUsersRating['similarityIndex']*topUsersRating['rating']
    tempTopUsersRating = topUsersRating.groupby('book_id').sum()[['similarityIndex','weightedRating']]
    tempTopUsersRating.columns = ['sum_similarityIndex','sum_weightedRating']
    recommendation_df = pd.DataFrame()
    recommendation_df['weighted average recommendation score'] = tempTopUsersRating['sum_weightedRating']/tempTopUsersRating['sum_similarityIndex']
    recommendation_df['book_id'] = tempTopUsersRating.index
    recommendation_df = recommendation_df.sort_values(by='weighted average recommendation score', ascending=False)
    final_recs = books.loc[books['id'].isin(recommendation_df.head(50)['book_id'].tolist())]
    return final_recs
