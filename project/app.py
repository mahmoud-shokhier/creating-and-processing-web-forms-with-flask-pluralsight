from curses import meta
from distutils.command.upload import upload
from email import message
from email.mime import image
from re import sub
from sys import flags
from turtle import title
from flask import Flask, send_from_directory, render_template, request, redirect, url_for, g, flash
import pdb
import sqlite3
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired
from wtforms import FileField, StringField, TextAreaField, SubmitField, SelectField, DecimalField
from wtforms.validators import InputRequired, DataRequired, Length
import os
import datetime
from secrets import token_hex
from werkzeug.utils import secure_filename

baseDir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'
app.config['ALLOWED_IMAGE_EXTENSIONS'] = ['jpeg', 'jpg', 'png']
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['IMAGE_UPLOADS'] = os.path.join(baseDir, 'uploads')

class ItemForm(FlaskForm):
    title = StringField('Title', validators=[InputRequired('Input is required'), DataRequired('Data is required'), Length(min=5, max=100, message="dtaa is not valid")])
    price = DecimalField('Price')
    description = TextAreaField('Description')
    image = FileField('Image', validators=[FileRequired(), FileAllowed(app.config['ALLOWED_IMAGE_EXTENSIONS'], 'File extension is not supported')])
    
class NewItemForm(ItemForm):
    category = SelectField('Category', coerce=int)
    subcategory = SelectField('Subcategory', coerce=int) 
    submit = SubmitField('Submit')

class EditItemForm(ItemForm):
    submit = SubmitField('Edit')
    
class DeleteItemForm(FlaskForm):
    submit = SubmitField('Delete')

class FilterForm(FlaskForm):
    title = StringField('Title')
    price = SelectField('Price', coerce=int, choices=[(0, "---"), (1, "Max to min"),(2,"Min to max")])
    category = SelectField('Category', coerce=int)
    subcategory = SelectField('Subcategory', coerce=int)
    submit = SubmitField('filter')
    

@app.route('/item/<int:item_id>/delete', methods=['POST'])
def delete(item_id):
    conn = get_db()
    c=conn.cursor()
    
    item_from_db = c.execute(
        "select * from items where id = ?",(item_id,))
    row = c.fetchone()
    try:
        item={
            "id":row[0],
            "title":row[1],
        }
    except:
        item={}
    if item:
        c.execute('delete from items where id=?', (item_id,))
        conn.commit()
        flash("Item {} delete successfully".format(item["title"]), 'success')
    else:
        flash("This item not exist", 'danger')
    return redirect(url_for("home"))

@app.route('/item/<int:item_id>/edit', methods=['GET','POST'])
def edit(item_id):
    conn = get_db()
    c=conn.cursor()
    
    item_from_db = c.execute(
        """select * from items where id=?""",(item_id,))
    row = c.fetchone()
    try:
        item={
            "id":row[0],
            "title":row[1],
            "description":row[2],
            "price":row[3],
            "image":row[4],
        }
    except:
        item={}
    if item:
        form = EditItemForm()
        
        if form.validate_on_submit():
            c.execute(""" update items set 
                      title = ?, description = ?, price = ?
                      where id = ?
                      """, (
                          form.title.data, 
                          form.description.data,
                          float(form.price.data),
                          item_id
                      ))
            conn.commit()
            flash("Item {} has been send successfully".format(item['title']), "success")
            return redirect(url_for("item", item_id=item_id))
       
        form.title.data = item['title']
        form.description.data = item['description']
        form.price.data = item['price']
        
        return render_template('edit_item.html', item=item, form=form) 
    return redirect(url_for("home"))


@app.route('/item/<int:item_id>', methods=['GET'])
def item(item_id):
    conn = get_db()
    c= conn.cursor()
    item_from_db = c.execute(""" 
                            select i.id, i.title, i.description, i.price, i.image, c.name, s.name
                            from items as i inner join categories as c on i.category_id=c.id inner join subcategories as s on s.id=i.subcategory_id
                            where i.id=?
                            """, (item_id,)
                        )
    row = c.fetchone()
    try:
        item  = {
            'id' : row[0], 
            'title' : row[1], 
            'description' : row[2], 
            'price' : row[3], 
            'image' : row[4], 
            'category' : row[5], 
            'subcategory' : row[6], 
        }
    except:
        item = {}
    if item :
        deleteItemForm = DeleteItemForm()
        
        return render_template('item.html', item=item, deleteItemForm=deleteItemForm)
    return redirect(url_for('home'))

@app.route('/')
def home():
    conn = get_db()
    cursor = conn.cursor()
    
    form = FilterForm(request.args, meta={"csrf":False})
    cursor.execute("Select id, name from categories")
    categories = cursor.fetchall()
    form.category.choices = categories
    
    cursor.execute("Select id, name from subcategories")
    subcategories = cursor.fetchall()
    form.subcategory.choices = subcategories
    query = """ select i.id, i.title, i.description, i.price, i.image, c.name, s.name from items as i 
                inner join categories as c on i.category_id=c.id 
                inner join subcategories as s on i.category_id=s.id
            """
    filter_queries = []
    parameters = []
    if form.validate():    
        if form.title.data.strip():
            filter_queries.append("i.title LIKE ?")
            parameters.append("%"+form.title.data+"%")
        
        if form.category.data:
            filter_queries.append('i.category_id=?')
            parameters.append(form.category.data)
        
        if form.subcategory.data:
            filter_queries.append('i.subcategory_id=?')
            parameters.append(form.subcategory.data)
            
        if filter_queries:
            query += " where "
            query += " AND ".join(filter_queries)
        
        if form.price.data:
            if form.price.data == 1:
                query += "ORDER BY price DESC"
            else:
                query += "ORDER BY price"
        else:
            query += "ORDER BY i.id DESC"
    else:
        data = cursor.execute(query + "ORDER BY i.id desc")
    
    data = cursor.execute(query, tuple(parameters))
    
    items = []
    for row in data:
        item = {
            'id': row[0], 
            'title': row[1],
            'description': row[2],
            'image':row[4],
            'price':row[3],
            'category': row[5],
            'subcategory':row[6]
        }
        items.append(item)
    # pdb.set_trace()
    return render_template('home.html', items=items, form=form)

@app.route('/uploads/<filename>')
def upload(filename):
    return send_from_directory(app.config['IMAGE_UPLOADS'], filename)

@app.route('/item/new', methods=['GET', 'POST'])
def new_item():
    # pdb.set_trace()
    
    conn = get_db()
    c= conn.cursor()
    form = NewItemForm()
    c.execute("Select id, name from categories")
    categories = c.fetchall()
    form.category.choices = categories
    
    c.execute("Select id, name from subcategories where category_id=1 ")
    subcategories = c.fetchall()
    form.subcategory.choices = subcategories
    
    if form.validate_on_submit():
        format = "%Y%m%dT%H%M%S"
        now = datetime.datetime.utcnow().strftime(format)
        random_string = token_hex(2)
        filename = random_string + "_"+now+"_"+form.image.data.filename
        filename = secure_filename(filename)
        form.image.data.save(os.path.join(app.config["IMAGE_UPLOADS"], filename))
         
        c.execute("""
                    insert into items 
                    (title, description, price, image, category_id, subcategory_id)
                    values(?,?,?,?,?,?)""", (
                        form.title.data, 
                        form.description.data, 
                        float(form.price.data), 
                        filename, 
                        form.category.data, 
                        form.subcategory.data
                    )
                  )
        
        conn.commit()
        flash('item {} createed successfully'.format(request.form.get('title')), 'success')
        return redirect(url_for('home'))
    if form.errors:
        flash('{}'.format(form.errors), "danger")
    return render_template('new_item.html', form=form)

def get_db():
    db = getattr(g, '_database ', None) 
    if db is None:
        db = g._database = sqlite3.connect('db/globomantics.db')
    return db
 
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# You put your app.run() call too early:
if __name__== '__main__':
    app.run()