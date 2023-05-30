import os, io
from google.cloud import vision
from google.cloud import vision_v1
from google.cloud.vision_v1 import types
import zipfile
import telebot
import sqlite3 as sql

TOKEN_DIR = 'TKN'
SQL_DIR = 'SQL'
PICTURES_DIR = 'PICTURES'

def getTokenFromFile(name):
    with open(f'{TOKEN_DIR}/{name}.tkn', 'r') as f:
        return f.readline()

TG_BOT_TKN = getTokenFromFile('tgbot')
DB_NAME = 's10_dips_lab2.db'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = f'{TOKEN_DIR}/gcloud.json'

def initDb():
    con = sql.connect(f'{SQL_DIR}/{DB_NAME}')
    cur = con.cursor()
    
    with open(f'{SQL_DIR}/initPictures.sql', 'r') as f:
        cur.execute(f.read())
    
    with open(f'{SQL_DIR}/initLabels.sql', 'r') as f:
        cur.execute(f.read())
    
    con.commit()
    con.close()
initDb()

def savePicture(user_id, extension):
    con = sql.connect(f'{SQL_DIR}/{DB_NAME}')
    cur = con.cursor()
    
    cur.execute(f'INSERT INTO pictures (user_id, ext) VALUES (\'{user_id}\', \'{extension}\');')
    id = cur.lastrowid
    
    con.commit()
    con.close()
    
    return id

def saveLabel(pictureId, name, prob):
    con = sql.connect(f'{SQL_DIR}/{DB_NAME}')
    cur = con.cursor()
    
    cur.execute(f'INSERT INTO labels (picture_id, name, prob) VALUES (\'{pictureId}\', \'{name}\', \'{prob}\');')
    id = cur.lastrowid
    
    con.commit()
    con.close()
    
    return id

def getPicturesByLabels(user_id, labels):
    con = sql.connect(f'{SQL_DIR}/{DB_NAME}')
    cur = con.cursor()
    
    tmp = [f"l.name LIKE '%{l}%'" for l in labels]
    nameCheck = f'({" OR ".join(tmp)})'
    cur.execute(f'SELECT DISTINCT p.id, p.ext FROM pictures p INNER JOIN labels l ON p.id = l.picture_id WHERE p.user_id = {user_id} AND {nameCheck}')
    result = cur.fetchall()
    
    con.close()
    
    return result
    

client = vision.ImageAnnotatorClient()
bot = telebot.TeleBot(TG_BOT_TKN)

def getLabels(bytes, minCount = 5, minScore = 0.75):
    img = types.Image(content = bytes)
    response = client.label_detection(image = img).label_annotations
    result = response[:minCount]
    
    index = minCount
    while index < len(response) and response[index].score > minScore:
        result.append(response[index])
        index += 1
    
    return result

@bot.message_handler(commands=['start'])
def start(msg: telebot.types.Message):
    bot.send_message(msg.chat.id, 'Hello ✋ Type /info for details')

@bot.message_handler(commands=['info'])
def info(msg: telebot.types.Message):
    bot.send_message(msg.chat.id,
                     'This is bot for Dirivated Information Processing Systems (DIPS) lab2.\n\n' +
                     'This bot receives pictures, and create labels for it with Google Vision API. ' +
                     'You can find pictures by this labels.\n\n' +
                     'Made by Eugene Vasyliev')

def saveFile(fileId, user_id, extension):
    pictureId = savePicture(user_id, extension)
    file_info = bot.get_file(fileId)
    downloaded_file = bot.download_file(file_info.file_path)

    with open(f'{PICTURES_DIR}/{pictureId}.{extension}', 'wb') as new_file:
        new_file.write(downloaded_file)
    
    labels = getLabels(downloaded_file)
    for l in labels:
        saveLabel(pictureId, l.description, l.score)
    
    return labels

def ganareteAnswer(msg: telebot.types.Message, labels, maxWrite=5):
    answer = f'Generated {len(labels)} labels: '
    for l in labels[:maxWrite]:
        answer += f'\n*{l.description}*'
    if len(labels) > maxWrite:
        answer += '\n...'
    bot.reply_to(msg, answer, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'])
def proccessPhoto(msg: telebot.types.Message):
    labels = saveFile(msg.photo[-1].file_id, msg.from_user.id, 'jpg')
    ganareteAnswer(msg, labels)

@bot.message_handler(content_types=['document'])
def proccessDoc(msg: telebot.types.Message):
    if msg.document.mime_type == 'image/jpeg':
        labels = saveFile(msg.document.file_id, msg.from_user.id, 'jpg')
    elif msg.document.mime_type == 'image/png':
        labels = saveFile(msg.document.file_id, msg.from_user.id, 'png')
    ganareteAnswer(msg, labels)
        

@bot.message_handler(content_types=['text'])
def echo_all(msg: telebot.types.Message):
    kws = msg.text.split()
    ids = getPicturesByLabels(msg.from_user.id, kws)
    
    if len(ids) > 0:    
        buff = io.BytesIO()
        with zipfile.ZipFile(buff, 'w') as zip:
            for id, ext in ids:
                fName = f'{id}.{ext}'
                with open(f'{PICTURES_DIR}/{fName}', 'rb') as pic:
                    zip.writestr(fName, pic.read())
        bot.send_document(chat_id=msg.chat.id, reply_to_message_id=msg.id, document=buff.getvalue(),
                          visible_file_name='result.zip', caption=f'{len(ids)} results found')
    else:
        bot.reply_to(msg, 'No images found')

bot.infinity_polling()

# text = response.text_annotations
# print(text)

# con = sql.connect(f'{SQL_DIR}/{DB_NAME}')
# print(con.cursor().execute("select * from pictures").fetchall())
# con.close()