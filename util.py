
import os
import sys
import random
import math
import numpy as np
import pandas as pd
import scipy

def chunker(top_books):
    # chunk into groups of 4 to display better in web app
    chunks = []
    current_chunk = []
    for i in range(len(top_books)):
        if len(current_chunk) < 4:
            current_chunk.append(top_books[i])
        else:
            chunks.append(current_chunk)
            current_chunk = [top_books[i]]

    chunks.append(current_chunk)
    return chunks


def find_book(book_id, books):
    book = []
    book_item = books.iloc[book_id]
    book.append(book_item)
    return book 
