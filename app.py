from flask import Flask, request, render_template, redirect, url_for, session, logging, flash
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps

import numpy as np
import pandas as pd
import scipy
import logging
import pickle
import csv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pymongo

'''Routes'''
#from user import routes

'''Python algorithm'''
from book_recommendations import popular_books, similar_books, display_books, df_to_list, collab_filtering_recs
from util import chunker,find_book


app = Flask(__name__)

#Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'book_rec_system'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
#init MySQL

mysql = MySQL(app)

''' Global Variables '''
books = None
titles = None
books_edited = None
user_ratings = None
book_title = None


'''Functions '''
# Load books and book titles into a global variable 
def load_books():
    """ Loads in the books and titles from the pickled dataframe """
    global books, titles
    if books is None or titles is None:
        titles = []
        # books_df = pd.read_csv('static/data/goodbooks_10k/books.csv')
        # pd.to_pickle(books_df,"static/data/books.pk1")
        books = pd.read_pickle("static/data/final_books")

        for index, row in books.iterrows():
            titles.append(row['title'])
        titles.sort()
        print('books loaded')

# load edited books dataframe to calculate item similarity 
def load_books_edited():
    global books_edited
    if books_edited is None:
        books_edited = pd.read_pickle("static/data/final_books_edited")
        print('books_edited loaded')

#load user ratings dataframe 
def load_ratings():
    global user_ratings
    if user_ratings is None:
        user_ratings = pd.read_pickle("static/data/ratings")
        print('user_ratings_loaded')

# convert book title to id 
def title_to_id(title):
    ids = books[books['title']== title].index.values.astype(int)[0]
    return ids

#load all the necessary data
def load_data():
    global titles
    global booklists
    load_books()
    load_books_edited()
    load_ratings()
    top_books = popular_books(books, 50)
    chunks = chunker(top_books)
    return render_template('index.html',titles=titles,toPass=chunks, 
                            response='50 Most Popular Books on this site')

#load book information 
def load_book_info():
    text = request.form["books"]
    book_id = title_to_id(text)
    book = find_book(book_id, books)
    return render_template('book_info.html',titles=titles, response= book_id, book= book)

#return books dataframe with authors 
def return_books_with_author(sim_books):
    merged_df = pd.merge(books, sim_books, left_on='book_id', right_on='book_id', how='left')
    merged_df = merged_df.sort_values('weighted_rating', ascending=False)
    return merged_df

#Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please Login', 'danger')
            return redirect(url_for('login'))
    return wrap


'''Home Page'''
@app.route('/')
@is_logged_in
#Homepage 
def index():
    return load_data()

#Homepage, if a book is searched or clicked redirect user
@app.route('/', methods=['GET','POST'])
def index_post():
    if 'view_book' or 'book_clicked' in request.form:
        booktitle = request.form.get('booktitle')
        userid = session['userid']
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM ratings WHERE booktitle = %s AND userid = %s" , [booktitle,userid])
        if result > 0:
            data = cur.fetchone()
            book_rating = data['rating']
        else:
            book_rating = '0'
        cur.close()
        app.logger.info("this is the rating:" + book_rating)
        return redirect(url_for('bookinfo',booktitle=booktitle, book_rating=book_rating))

'''Book info page'''
#Redirect user to book information page
@app.route('/bookinfo')
def bookinfo():
    global book_title
    booklists = []
    userid = session['userid']
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM booklist WHERE userid = %s" , [userid])
    rows = []

    if result > 0:
        for row in cur:
            data = cur.fetchone()
            booklist_title = data['title']
            booklists.append(booklist_title)
        cur.close()

    booktitle = request.args.get('booktitle',None)
    book_rating = request.args.get('book_rating', None)
    book_title = booktitle
    book_id = title_to_id(booktitle)
    book=find_book(book_id,books)
    return render_template('book_info.html',book_rating=book_rating, booktitle= booktitle ,titles=titles, book= book, booklists = booklists)

#Redirect user to /similarbooks if user click on "view similar books "
@app.route('/bookinfo', methods=['GET','POST'])
def bookinfo_post():
    global book_title
    booktitle = request.args.get('booktitle',None)
    # book_rating = request.args.get('book_rating',None)
    app.logger.info(book_title)
    if 'similar_book' in request.form:
        return redirect(url_for('similarbooks',booktitle=booktitle))
    elif request.form['bookRating']:
        app.logger.info(request.form['bookRating'])
        rating = request.form['bookRating']
        userid = session['userid']
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM ratings WHERE booktitle = %s AND userid = %s" , [book_title,userid])
        if result > 0: 
            cur.execute("UPDATE ratings SET rating = %s WHERE booktitle = %s AND userid = %s" , (rating,book_title,userid) )
            cur.close()
        else:
            cur.execute("INSERT INTO ratings(booktitle,rating,userid) VALUES(%s, %s, %s)", (book_title,rating,userid) )
            cur.close()
            return render_template('index.html')

    

#Display similar books"
@app.route('/similarbooks')
def similarbooks():
    booktitle = request.args.get('booktitle',None)
    sim_books = similar_books(books_edited, booktitle)
    sim_books_edited = return_books_with_author(sim_books)
    top_books = display_books(sim_books_edited, 50)
    chunks = chunker(top_books)
    return render_template('index.html',titles=titles,toPass=chunks,booktitle=booktitle, response="Top Similar Books to "+booktitle)

#If user click on book or search for books in similar books page"
@app.route('/similarbooks', methods=['GET','POST'])
def similarbooks_post():
    if 'view_book' or 'book_clicked' in request.form:
        booktitle = request.form.get('booktitle')
        userid = session['userid']
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM ratings WHERE booktitle = %s AND userid = %s" , [booktitle,userid])
        if result > 0:
            data = cur.fetchone()
            book_rating = data['rating']
        else:
            book_rating = '0'
        cur.close()
        return redirect(url_for('bookinfo',booktitle=booktitle, book_rating=book_rating))

#Display recommendations based on the given user ratings"
@app.route('/recommendations', methods = ['GET','POST'])
def recommendations():
    userid = session['userid']
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM ratings WHERE userid = %s" , [userid])
    rows = []
    rec_ratings = []
    
    if result > 4:
        for row in cur:
            data = cur.fetchone()
            booktitle = data['booktitle']
            rating = data['rating']
            thisdict = {
                "title":booktitle,
                "rating":int(rating)
            }
            rec_ratings.append(thisdict)
        cur.close()
        bookrecs = collab_filtering_recs(rec_ratings, books , user_ratings)
        app.logger.info(rec_ratings)
        top_books = display_books(bookrecs, 50)
        chunks = chunker(top_books)
        return render_template('index.html',titles=titles,toPass=chunks,booktitle=booktitle, response="Recommendations for "+session["username"])
    else:
        flash('Please rate more than 5 books in order to view recommendations (more info in "User Guide" section)', 'danger')
        return redirect(url_for('index'))

#validate form
class RegisterForm(Form):
    username = StringField(u'Username', [validators.length(min=5,max=32)])
    email  = StringField(u'Email', [validators.Length(min=6,max=254)])
    password  = PasswordField(u'Password', [
        validators.Length(min=6,max=64),
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Password do not match')
    ])
    confirm = PasswordField('Confirm Password')

#validtae form
class BooklistForm(Form):
    title = StringField(u'title', [validators.length(min=2,max=32)])
    description  = StringField(u'description', [validators.Length(min=0,max=300)])

# registration
@app.route('/register', methods=['GET','POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate() :
        username = form.username.data
        email = form.email.data
        password = sha256_crypt.encrypt(str(form.password.data))
        #Create Cursor
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users(email,username,password) VALUES(%s, %s, %s)", (email,username, password) )
        #Close connnection
        cur.close()
        flash('You are now registered and can log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

#login
@app.route('/login', methods = ['GET','POST'])
def login():
    if request.method == 'POST':
        #Get Form Fields
        email = request.form['email']
        password_candidate = request.form['password']
        cur = mysql.connection.cursor()
        #Get user by email 
        result = cur.execute("SELECT * FROM users WHERE email = %s", [email])
        if result > 0:
            #Get Stored Hash
            data = cur.fetchone()
            password = data['password']
            username = data['username']
            userid = data['id']
            #Compare passwords
            if sha256_crypt.verify(password_candidate, password):
                #passed
                session['logged_in'] = True
                session['email'] = email
                session['username'] = username 
                session['userid'] = userid
                flash('Welcome back! '+username, 'success')
                return redirect(url_for('index'))
            else:
                error: 'Invalid Login'
                return render_template('login.html', error=error)
            cur.close()
        else:
            error = "Invalid Login"
            return render_template('login.html', error=error)
    return render_template('login.html')

#logout, kill session
@app.route('/logout')
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))

#view profile page
@app.route('/profile')
def profile():
    if 'username' in session:
        return render_template('profile.html', booklists = booklists, name = session['username'], email = session['email'])

if __name__ == "__main__":
    app.secret_key= 'secret123'
    app.run(debug=True)
