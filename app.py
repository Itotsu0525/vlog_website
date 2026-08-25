from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
from datetime import datetime
import click
from dotenv import load_dotenv

import os

load_dotenv()  # .envファイルを読み込む

app = Flask(__name__)

#①Writting for set up login setting
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

#②system for login management
login_manager = LoginManager()
login_manager.init_app(app)
#login_manager.login_view = 'login'  これは後で確認する

#許可する拡張子
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
#写真fileの確認
def allowed_file(filename):
    #ファイル名に「.」が含まれているか確認（拡張子がない場合を除外）
    if '.' not in filename:
        return False

    #拡張子部分だけを取り出して、小文字にして比較
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


#ここは覚える必要ない。調べれば出てくる
db = SQLAlchemy()
DB_INFO = {
    'user': os.environ.get("DB_USER"),
    'password': os.environ.get("DB_PASSWORD"),
    'host': os.environ.get("DB_HOST"),
    'name': os.environ.get("DB_NAME"),
} 
SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://{user}:{password}@{host}/{name}'.format(**DB_INFO)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
db.init_app(app)

#migrateを使用するためのコード
migrate = Migrate(app, db)

#③現在のユーザーを識別するための関数
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#tableの定義
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    pytz_timezone = pytz.timezone('Asia/Tokyo')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(pytz_timezone))
    #画像を付け足すために追加したもの、migration
    img_name = db.Column(db.String(100), nullable=True)

#ログイン設定,　ユーザーのデーターベース
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True) #uniqueは同じユーザー名が被らないようにするために書く
    password = db.Column(db.String(200), nullable=False)

@app.route('/admin')
@login_required
def admin():
    #titles = ['タイトル1', 'タイトル2', 'タイトル3', 'タイトル4']

    #データベースから引っ張り出す,これは新しい記事から古い記事の順に出してくれる
    posts = Post.query.order_by(Post.created_at.desc()).all()

    return render_template('admin.html',posts=posts)

#使用者が変更できないページ
@app.route('/')
def index():

    #データベースから全記事を取得（admin関数と同じ）
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('index.html',posts=posts)

#記事をより見れるようにするコード
@app.route('/<int:post_id>/read_more')
def read_more(post_id):

    #URLのpost_idを使って、該当する記事だけを取得
    post = Post.query.get(post_id)
    return render_template('read_more.html', post=post)

#データ作成
@app.route("/create", methods=['GET','POST'])
@login_required
def create():
    #リクエストのメソッド判別、ここは新しいpostを制作する
    if request.method == 'POST':

         #リクエストできた情報の処理
        title = request.form.get('title')
        body = request.form.get('body')

        #画像情報の習得
        file = request.files['img']

        #画像ファイル名の習得
        filename = file.filename

        #拡張子チェック
        if not allowed_file(filename):
            return "画像ファイル(jpg, jpeg, png, gif)のみアップロードできます", 400


        #データベースにファイル名を保存
        post = Post(title=title, body=body, img_name=filename)

        #画像を保存
        save_path = os.path.join(app.static_folder, 'img', filename)
        file.save(save_path)

        #情報の保存
        db.session.add(post)
        db.session.commit()
        return redirect('/admin')
    elif request.method == 'GET':
        return render_template('create.html',method='GET')

#データ更新
@app.route("/<int:post_id>/update", methods=['GET','POST'])
@login_required
def update(post_id):

    #編集した内容, よくqueryを投げ出すと言ったりする
    post = Post.query.get(post_id)   

    #リクエストのメソッド判別
    if request.method == 'POST':
        #更新するときの書き方
        post.title = request.form.get('title')
        post.body = request.form.get('body')
        db.session.commit()
        return redirect('/admin')
    elif request.method == 'GET':
        return render_template('update.html',post=post)

#データ削除
@app.route("/<int:post_id>/delete", methods=['GET','POST'])
@login_required
def delete(post_id):

    post = Post.query.get(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect('/admin')


@app.route("/login", methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        #ユーザー名とパスワードの受け取り
        username = request.form.get('username')
        password = request.form.get('password')
             
        #ユーザー名をもとにデータベースから情報を取得
        user = User.query.filter_by(username=username).first()
        
        #入力パスワードとデータベースのパスワードが一致しているか確認
        # userが存在し、かつパスワードが一致する場合のみログイン
        if user and check_password_hash(user.password, password):
    
            #一致していれば、ログインさせて、管理画面へリダイレクトさせる
            login_user(user)
            return redirect('/admin')
        else:
        
             #間違っている場合、エラー文と共にログイン画面へリダイレクトさせる
            return redirect('/login', msg='ユーザー名/パスワードが違います')   

    elif request.method == 'GET':
        return render_template('login.html') 

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

#僕だけがアカウント作成できるようにするコード
@app.cli.command("create-admin")
@click.argument("username")
#To hide the password
@click.password_option()
def create_admin(username, password):
    """管理者アカウントを作成する(ターミナル専用、Web経由では作れない)"""
    existing = User.query.filter_by(username=username).first()
    if existing:
        print(f"エラー: ユーザー名 '{username}' はすでに存在します。")
        return

    hashed_pass = generate_password_hash(password)
    user = User(username=username, password=hashed_pass)
    db.session.add(user)
    db.session.commit()
    print(f"管理者アカウント '{username}' を作成しました。")