from flask import Flask,render_template,request,url_for,redirect,session
import smtplib
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import  DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float
import stripe
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
import random
from datetime import datetime
from sensitive import *
stripe.api_key = stripe_api_key
app = Flask(__name__)
app.secret_key = app_secret_key
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///products.db'
app.config['SQLALCHEMY_BINDS'] = {'bag':'sqlite:///bag.db'}
db = SQLAlchemy(model_class=Base)
db.init_app(app)

class Products(db.Model):
    __tablename__ = "products"
    name: Mapped[str] = mapped_column(String(250), primary_key=True)
    description: Mapped[str] = mapped_column(String(250))
    photo_url: Mapped[str] = mapped_column(String(250))
    quantity_left: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Float)



with app.app_context():
    db.create_all()

@app.route('/')
def index():  # put application's code here

    return render_template("updated_index.html")
@app.route('/contact_us')
def contact_us():
    return render_template("contact_us.html")

@app.route('/contact_us/done',methods=['POST'])
def send_mail():
    if request.method == 'POST':
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']

        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            connection.starttls()
            connection.login(user=my_email, password=gmail_password)
            connection.sendmail(from_addr=my_email, to_addrs="proreflex@abv.bg",
                                msg=f"Subject:{subject}\n\n Hey, admin of site. You've got mail from {email}.\n The message is:\n {message}")

    return "Done"
@app.route('/products')
def products():
    result = db.session.execute(db.select(Products))
    products=result.scalars().all()
    basket = session.get('user_basket', {})
    return render_template("products.html",products=products,basket=basket)


@app.route('/add_to_basket/<string:name>',methods=['POST','GET'])
def add_to_database(name):  # put application's code here
    quantity_selected=int(request.form['quantity'])
    post = db.get_or_404(Products, name)
    basket = session.get('user_basket', {})
    value = session.get('user_basket', None)
    if value is None:
        session['user_basket']={}
    if not post.name in basket:
        session['user_basket'][post.name]={'name':post.name,"photo_url":post.photo_url,"description":post.description,'price':post.price,'quantity_selected':int(quantity_selected)}
        session.modified=True
    else:
        session['user_basket'][post.name]['quantity_selected']+=quantity_selected
        session.modified=True




    return redirect(url_for("products"))

YOUR_DOMAIN = 'http://localhost:5000'


@app.route('/checkout',methods=['POST','GET'])
def checkout():
    basket = session.get('user_basket', {})
    print(basket)
    bag=[]
    for key in basket:
        bag.append(basket[key])
    print(bag)
    prices=[float(i['price'])*int(i['quantity_selected']) for i in bag]
    total=sum(prices)
    names=[]
    for i in bag:
        names.append(i['name'])
    return render_template('checkout.html',items=bag,names=names,total=total,redeem=0,discount=0)

@app.route('/checkout_with_code',methods=['POST','GET'])
def redeem_code():
    basket = session.get('user_basket', {})
    print(basket)
    bag = []
    for key in basket:
        bag.append(basket[key])
    prices = [float(i['price']) * int(i['quantity_selected']) for i in bag]
    total = sum(prices)
    names = []
    for i in bag:
        names.append(i['name'])
    if request.method == 'POST':
        discount=total*0.2
        code = request.form['code']
        if code in codes:
            return render_template('checkout.html',items=bag,names=names,total=total,redeem=1,discount=discount)
        else:
            return render_template('checkout.html',items=bag,names=names,total=total,redeem=1,discount=0,wrong_code=1)

@app.route('/remove/<string:item>',methods=['POST','GET'])
def remove_item_from_bag(item):
    basket = session.get('user_basket', {})
    if item in basket:
        to_remove = basket[item]
        session['user_basket'].pop(item)
        session.modified = True


    return redirect(url_for('checkout'))



@app.route('/remove_selected/<item_name>/<selected_quantity>')
def redirect_to_somewhere(item_name, selected_quantity):
    basket = session.get('user_basket', {})
    print(basket)
    if item_name in basket:
        to_edit = basket[item_name]
        session['user_basket'][item_name]['quantity_selected'] = int(selected_quantity)
        session.modified = True
        db.session.commit()
    return redirect(url_for('checkout'))

@app.route('/create-checkout-session/<items>/<discount>/<total_price>', methods=['POST', 'GET'])
def create_checkout_session(items,discount,total_price):

    items = items.strip('[]')
    items1 = [item.strip() for item in items.split(',')]
    print(items1)
    cash='off'
    if request.method == 'POST':
        cash = request.form.get('cash', None)
        session['customer_info'] = {
            'first_name': request.form['first_name'],
            'last_name': request.form['last_name'],
            'email': request.form['email'],
            'phone_number': request.form['phone_num'],
            'address': request.form['address'],
            'address2': request.form['address2'],
            'zip': request.form['zip'],
            'country': request.form['country'],
            'city': request.form['city'],
            'total_price':total_price,
            'cash':'off',
            'message':request.form['message']
        }

    line_items = []
    products_ordered = {}
    for item_name in items1:
        basket = session.get('user_basket', {})
        object = basket[f'{item_name[1:-1]}']
        quantity = object['quantity_selected']
        if item_name == "'gerdan'":
            products_ordered['gerdan'] = quantity
            line_items.append({'price': prices['gerdan'], 'quantity': quantity})
        elif item_name == "'surce'":
            products_ordered['surce'] = quantity
            line_items.append({'price': prices['surce'], 'quantity': quantity})
    session['customer_info']["customer_order"] = products_ordered
    print(session)

    for key in products_ordered:
        product = db.get_or_404(Products, key)
        if product.quantity_left < int(products_ordered[key]):
            return render_template('no_availability.html')
        db.session.commit()
    if cash == 'on':
        session['customer_info']['cash']='on'
        return redirect(url_for('verification'))
    else:
        try:

            if int(discount) == 0:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],  # Specify payment method types
                    line_items=line_items,
                    mode='payment',
                    success_url=YOUR_DOMAIN + '/success',
                    cancel_url=YOUR_DOMAIN + '/cancel',
                )
            else:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],  # Specify payment method types
                    line_items=line_items,
                    mode='payment',
                    success_url=YOUR_DOMAIN + '/success',
                    cancel_url=YOUR_DOMAIN + '/cancel',
                    discounts=[{'coupon': '5docHHVm'}]
                )
        except Exception as e:
            return str(e)

        return redirect(checkout_session.url, code=303)



@app.route('/cancel',methods=['POST','GET'])
def cancel():

    return render_template('cancel.html')

@app.route('/success',methods=['POST','GET'])
def success():
    customer_info = session.get('customer_info', {})
    message = MIMEMultipart()
    message['From'] = my_email
    message['To'] = "proreflex@abv.bg"
    message['Subject'] = "NEW ORDER"

    # Construct email body
    body = f"Hey, admin of site. You've got new order.\n" \
           f"name: {customer_info['first_name']} {customer_info['last_name']}\n" \
           f"phone number: {customer_info['phone_number']}\n" \
           f"email: {customer_info['email']}\n" \
           f"address: {customer_info['country']}, {customer_info['city']}, {customer_info['address']}, {customer_info['address2']}, ZIP {customer_info['zip']}\n" \
           f"order: {customer_info['customer_order']}\n" \
           f"total price: {customer_info['total_price']}\n" \
           f"cash: {customer_info['cash']}\n" \
           f"message: {customer_info['message']}."
    body_utf8 = body.encode('utf-8')

    message.attach(MIMEText(body_utf8, 'plain', 'utf-8'))

    # Connect to SMTP server and send email
    with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
        connection.starttls()
        connection.login(user=my_email, password=gmail_password)
        connection.sendmail(from_addr=my_email, to_addrs=my_email, msg=message.as_string())

    basket = session.get('user_basket', {})

    for key in basket:
        product = db.get_or_404(Products, key)
        product.quantity_left -= int(basket[key]['quantity_selected'])
        db.session.commit()

    session.pop('customer_order', None)
    session.pop('customer_info', None)
    session.pop('user_basket', None)

    return render_template('success.html')




@app.route('/verification',methods=['POST','GET'])
def verification():
    info = session.get('customer_info', {})
    return render_template('verify.html',phone_num=info['phone_number'],sent=0)


@app.route('/send_sms',methods=['POST','GET'])
def send_sms():
    if request.method == 'POST':
        number=request.form["phone"]
        session['potential_num']=number

    code=random.randint(a=100000,b=999999)
    potential_num = session.get('potential_num')
    client = Client(twilio_sid, twilio_token)
    message = client.messages \
        .create(
        body=f"Your code is {code} .",
        from_=twilio_num, to=potential_num)
    current_moment = datetime.now()
    print(message.status)
    return render_template('verify.html',sent=1,code=code,moment_sent=current_moment)

@app.route('/validate_sms/<code>/<time>',methods=['POST','GET'])
def validate_sms(code,time):
    potential_code=""
    if request.method == 'POST':
        potential_code=request.form["written_code"]

    current_moment = datetime.now()
    print(f'current_moment is - {current_moment}')
    print(f'old moment is - {time}')
    old_time = datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
    subtraction=(current_moment - old_time).total_seconds()
    max = 10*60
    if code == potential_code and subtraction <= max:
        potential_num = session.get('potential_num')
        session['customer_info']['phone_number']= potential_num
        session.pop('potential_num')
        return redirect(url_for('success'))
    else:
        session.pop('potential_num')
        return redirect(url_for('verification'))


if __name__ == '__main__':
    app.run(debug=True,host="0.0.0.0")



