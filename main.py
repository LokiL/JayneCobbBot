#!/usr/bin/python3
# coding=utf-8
import argparse
import csv
import datetime
import os
import random
import re
import signal
import sys
import time
from multiprocessing import Process, freeze_support

import telebot
from loguru import logger
from peewee import *
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import settings

parser = argparse.ArgumentParser(add_help=True, description='Cobb Bot for Telegram')
parser.add_argument('--token', action='store', help='Authentication token [required]', required=True)
parser.add_argument('--p_login', action='store', help='Proxy login [optional]', required=False)
parser.add_argument('--p_pass', action='store', help='Proxy password [optional]', required=False)
parser.add_argument('--p_adress', action='store', help='Proxy adress [optional]', required=False)
parser.add_argument('--p_port', action='store', help='Proxy port [optional]', required=False)

csv.register_dialect('localeDialect', quoting=csv.QUOTE_ALL, skipinitialspace=True, lineterminator='\n')

args = parser.parse_args()

logger.add(sys.stderr, format="{time} {level} {message}", filter="my_module", level="INFO")
logger.add("Cobb.log", rotation="10 MB", enqueue=True)

if args.p_adress is not None:
    try:
        from telebot import apihelper

        apihelper.proxy = {
            'https': 'socks5h://{proxy_login}:{proxy_password}@{proxy_adress}:{proxy_port}'.format(
                proxy_login=args.p_login,
                proxy_password=args.p_pass,
                proxy_adress=args.p_adress,
                proxy_port=args.p_port)}
        logger.info("Started with proxy: {proxy_login}:{proxy_password}@{proxy_adress}:{proxy_port}".format(
            proxy_login=args.p_login,
            proxy_password=args.p_pass,
            proxy_adress=args.p_adress,
            proxy_port=args.p_port))
    except Exception as e:
        logger.exception(e)

bot_token = args.token
Cobb = telebot.TeleBot(bot_token)
db = SqliteDatabase('JayneCobbDatabase.db', check_same_thread=False)

restart_flag = False


class Users(Model):
    user_id = CharField()
    chat_id = IntegerField()
    first_join = DateField()
    warn_count = IntegerField()
    custom_title = CharField()
    is_boss = BooleanField()
    karma = IntegerField()

    class Meta:
        database = db


class UsersNames(Model):
    user_id = CharField()
    names = TextField()


class MessageLog(Model):
    message_id = IntegerField()
    message_date = IntegerField()
    message_text = CharField()
    chat_id = IntegerField()
    chat_title = CharField()
    chat_username = CharField()
    from_user_id = IntegerField()
    from_user_is_bot = BooleanField()
    from_user_username = CharField()
    from_user_first_name = CharField()
    from_user_last_name = CharField()
    forward_from_user_id = IntegerField()
    forward_from_user_username = CharField()
    forward_user_first_name = CharField()
    forward_from_chat_id = IntegerField()
    forward_from_chat_username = CharField()
    forward_from_chat_title = CharField()
    forward_date = IntegerField()
    reply_to_message_id = IntegerField()
    reply_to_message_from_username = CharField()
    reply_to_message_text = CharField()
    message_edit_date = IntegerField()
    mod_command = CharField()
    marked_to_delete = BooleanField()

    class Meta:
        database = db


class Chats(Model):
    chat_id = IntegerField()
    chat_title = IntegerField()
    chat_link = CharField()
    rules_text = CharField()
    welcome_set = BooleanField()
    welcome_text = CharField()
    log_text = BooleanField()
    log_pics = BooleanField()
    antibot = BooleanField()
    antibot_text = CharField()
    rm_voices = BooleanField()
    anticaps = BooleanField()
    antistickerspam = BooleanField()

    class Meta:
        database = db


class Quotes(Model):
    chat_id = IntegerField()
    submited_by = CharField()
    added = DateField()
    author_id = IntegerField()
    author = CharField()
    text = CharField()

    class Meta:
        database = db


class AllowedUsers(Model):
    chat_id = IntegerField()
    user_id = CharField()

    class Meta:
        database = db


class ChatLinks(Model):
    command = CharField()
    text = CharField()

    class Meta:
        database = db


@logger.catch
def chatlinks_loader():
    available_links = {}
    for link in ChatLinks.select():
        available_links[link.command] = link.text
    return available_links


@logger.catch
def func_restarter():
    # returns True if restart was initiated and removes file-marker, False - if file is not exists and create him
    trigger_file = "/tmp/JayneCobb.tmp"
    if os.path.isfile(trigger_file):
        file = open(trigger_file, 'r')
        content = int(file.read())
        file.close()
        os.remove(trigger_file)
        return content
    else:
        return None


restart_cid = func_restarter()
if restart_cid is not None:
    Cobb.send_message(restart_cid, "Новый код принят и запущен.")
    logger.info("Bot live at %s" % datetime.datetime.now())


@logger.catch
def func_restart_writer(cid):
    file = open("/tmp/JayneCobb.tmp", 'w')
    file.write(str(cid))
    file.close()


@logger.catch
def func_clean(message, log=True):
    func_log_chat_message(message, marked_to_delete=True)
    logger.info("Message %s in chat %s (%s) marked for deleting" % (
        message.message_id, message.chat.title, message.chat.id))


@logger.catch
def func_add_new_user(message, given_uid=None):
    if given_uid is None:
        uid = message.from_user.id
    else:
        uid = given_uid
    cid = message.chat.id

    subquery = Users.select().where((Users.user_id == uid) & (Users.chat_id == cid))
    if not subquery.exists():
        is_boss = False
        if uid == settings.master_id:
            is_boss = True
        Users.insert(user_id=uid,
                     chat_id=cid,
                     first_join=datetime.datetime.now(),
                     warn_count=0,
                     custom_title='',
                     is_boss=is_boss,
                     karma=0).execute()

        logger.info("User @%s (%s) in chat %s (%s) added to db" % (
            "Not @username given" if message.from_user.username is None else message.from_user.username, uid,
            message.chat.title, cid))


@logger.catch
def func_add_or_update_name_for_user(user_id, chat_id):
    names = []
    return names
    pass


@logger.catch
def func_get_names_for_user(user_id):
    names = []
    return names
    pass


@logger.catch
def func_add_new_chat_or_change_info(message):
    try:
        cid = message.chat.id
        if message.chat.type != 'private':
            if not Chats.select().where(Chats.chat_id == cid).exists():
                try:
                    link = Cobb.export_chat_invite_link(cid)
                except Exception as e:
                    logger.exception(e)
                    link = "Chat link is unavialable"
                finally:
                    Chats.insert(chat_id=cid,
                                 chat_title=message.chat.title,
                                 chat_link=link,
                                 rules_text="",
                                 log_text=True,
                                 log_pics=False,
                                 antibot=False,
                                 antibot_text=settings.antibot_welcome_default,
                                 welcome_set=False,
                                 welcome_text=settings.welcome_default,
                                 rm_voices=True,
                                 anticaps=True,
                                 antistickerspam=True).execute()

                    logger.info("New chat %s (%s) added to database" % (message.chat.title, cid))
                    try:
                        Cobb.send_message(settings.master_id,
                                          "New chat %s (%s) added to database" % (message.chat.title, cid))
                    except Exception as e:
                        logger.exception(e)
            else:
                if Chats.select().where(Chats.chat_id == cid).get().chat_title != message.chat.title:
                    update_chat_title = Chats.update(chat_title=message.chat.title).where(Chats.chat_id == cid)
                    update_chat_title.execute()

                    logger.info("Chat %s changed name to %s" % (cid, message.chat.title))
    except Exception as e:
        logger.exception(e)


@logger.catch
def func_karma_change(cid, uid, change):
    try:
        #     change inc/dec == +/-
        if change == 1:
            updated_user = Users.update(karma=Users.karma + 1).where(Users.user_id == uid)
        else:
            updated_user = Users.update(karma=Users.karma - 1).where(Users.user_id == uid)
        updated_user.execute()
    except Exception as e:
        logger.exception(e)


@logger.catch
def func_have_privileges(message):
    try:
        query = AllowedUsers.select().where(
            (AllowedUsers.user_id == message.from_user.id) & (AllowedUsers.chat_id == message.chat.id))
        who = Users.select().where((Users.user_id == message.from_user.id) & (Users.chat_id == message.chat.id)).get()
        if who.is_boss or query.exists():
            return True
        else:
            return False
    except Exception as e:
        logger.critical(e)
        return False


def func_user_is_not_exists(message):
    func_clean(Cobb.reply_to(message,
                             "К сожалению, пользователя еще нет в моей базе данных.\n"
                             "Видимо, он еще не писал в чате с момента моего включения."))


def func_add_quote(message):
    try:
        if message.reply_to_message is None:
            func_clean(Cobb.reply_to(message,
                                     "Команду можно использовать только ответом на текстовое сообщение."))
        else:
            log_entry = {'chat_id': message.chat.id, "submited_by": message.from_user.username,
                         "added": datetime.datetime.now(),
                         "author_id": message.reply_to_message.from_user.id,
                         "author": message.reply_to_message.from_user.username,
                         "text": message.reply_to_message.text}
            for key, value in log_entry.items():
                if log_entry[key] is None:
                    log_entry[key] = ''
            if log_entry["text"] != "":
                with db.atomic():
                    Quotes.create(**log_entry)
                Cobb.reply_to(message.reply_to_message, "Сообщение успешно сохранено в цитатник.")
            else:
                func_clean(Cobb.reply_to(message.reply_to_message, "В сообщении нет текста."))
    except Exception as e:
        logger.exception(e)


def func_get_quote(message, qid=None):
    try:
        if qid is None:
            query = Quotes.select().order_by(fn.Random()).limit(1).get()
            reply_text = "*%s*:\n%s\n\n_#%s submitted by %s at %s_" % (
                query.author, query.text, query.id, query.submited_by, query.added)
            Cobb.reply_to(message, reply_text, parse_mode='Markdown')
        else:
            if Quotes.select().where(Quotes.id == qid).exists():
                query = Quotes.select().where(Quotes.id == qid).get()
                reply_text = "%s:\n%s\n\n#%s submitted by %s at %s" % (
                    query.author, query.text, query.id, query.submited_by, query.added)
                Cobb.reply_to(message, reply_text)
            else:
                Cobb.reply_to(message, "Цитаты %s не существует." % qid)
    except Exception as e:
        logger.exception(e)


def func_get_horoscope():
    try:
        query = Quotes.select().order_by(fn.Random()).limit(1).get()
        return query
    except Exception as e:
        logger.exception(e)
        return "Exception logged"


def func_get_all_quote_ids(message):
    try:
        reply_text = "Всего цитат: %s\n" \
                     "Номера доступных цитат: " % Quotes.select().count()
        for quote in Quotes.select():
            reply_text += str(quote.id) + ", "
        Cobb.reply_to(message, reply_text[:-2])
    except Exception as e:
        logger.exception(e)


def func_rm_quote(message, qid):
    try:
        if Quotes.select().where(Quotes.id == qid).exists():
            query = Quotes.delete().where(Quotes.id == qid)
            query.execute()
            Cobb.reply_to(message, "Цитата %s успешно удалена." % qid)
        else:
            Cobb.reply_to(message, "Цитаты %s не существует." % qid)
    except Exception as e:
        logger.exception(e)


def func_log_chat_message(message, marked_to_delete=False):
    try:
        mod_command = False

        log_entry = {'message_id': message.message_id, 'message_date': message.date,
                     'message_text': message.text,
                     'chat_id': message.chat.id, 'chat_title': message.chat.title,
                     'chat_username': message.chat.username, 'from_user_id': message.from_user.id,
                     'from_user_is_bot': message.from_user.is_bot, 'from_user_username': message.from_user.username,
                     'from_user_first_name': message.from_user.first_name,
                     'from_user_last_name': message.from_user.last_name,
                     'forward_from_user_id': 0, 'forward_from_user_username': '', 'forward_user_first_name': '',
                     'forward_from_chat_id': 0, 'forward_from_chat_username': '', 'forward_from_chat_title': '',
                     'forward_date': 0, 'reply_to_message_id': 0, 'reply_to_message_from_username': '',
                     'reply_to_message_text': '', 'message_edit_date': 0, 'mod_command': mod_command,
                     'marked_to_delete': marked_to_delete}

        if message.reply_to_message is not None:
            log_entry['reply_to_message_id'] = message.reply_to_message.message_id
            log_entry['reply_to_message_from_username'] = message.reply_to_message.from_user.username
            log_entry['reply_to_message_text'] = message.reply_to_message.text
        if message.forward_from_chat is not None:
            log_entry['forward_from_chat_id'] = message.forward_from_chat.id
            log_entry['forward_from_chat_username'] = message.forward_from_chat.username
            log_entry['forward_from_chat_title'] = message.forward_from_chat.title
            log_entry['forward_date'] = message.forward_date
        if message.forward_from is not None:
            log_entry['forward_from_user_id'] = message.forward_from.id
            log_entry['forward_from_user_username'] = message.forward_from.username
            log_entry['forward_user_first_name'] = message.forward_from.first_name
            log_entry['forward_date'] = message.forward_date
        if message.content_type == 'sticker':
            log_entry['message_text'] = "sticker|%s|%s" % (message.sticker.emoji, message.sticker.set_name)

        if message.edit_date is not None:
            log_entry['message_edit_date'] = message.edit_date
        for key, value in log_entry.items():
            if log_entry[key] is None:
                log_entry[key] = ''
        with db.atomic():
            MessageLog.create(**log_entry)
    except Exception as e:
        logger.critical(e)


@logger.catch
def process_garbage_collector():
    while func_restarter() is None:
        query = MessageLog.select().where(
            (MessageLog.message_date < int(time.time()) - settings.time_to_delete_garbage) & (
                    MessageLog.marked_to_delete == True))
        if query.exists():
            for row in query:
                try:
                    Cobb.delete_message(row.chat_id, row.message_id)
                    logger.info("Message %s in %s successfully deleted " % (row.message_id, row.chat_id))
                except telebot.apihelper.ApiException:
                    logger.exception(
                        "Message %s in %s deleting failed, target message was deleted by someone" % (
                            row.message_id, row.chat_id),
                        backtrace=False)
                subquery = MessageLog.update(marked_to_delete=False).where(MessageLog.id == row.id)
                subquery.execute()

        else:
            pass
        time.sleep(30)


@logger.catch
def process_stickerspam_collector():
    while func_restarter() is None:
        for chat in Chats.select():
            if Chats.get(Chats.chat_id == chat.chat_id).antistickerspam:
                query = MessageLog.select().where(
                    (MessageLog.message_date > int(time.time()) - settings.antisticker_timer) & (
                        MessageLog.message_text.contains('sticker')) & (MessageLog.chat_id == chat.chat_id))
                if query.count() > settings.antisticker_count:
                    target_users = []
                    for stickerspam in query:
                        status = Cobb.get_chat_member(chat.chat_id, stickerspam.from_user_id).status
                        if status != "administrator" or status != "creator":
                            target_users.append(stickerspam.from_user_id)
                    if len(target_users) > 0:
                        selected_user = target_users[random.randint(0, settings.antisticker_count - 1)]
                        Cobb.restrict_chat_member(chat.chat_id, selected_user, int(time.time()) + 1800, True, True,
                                                  False, True)

                        Cobb.send_message(chat.chat_id,
                                          "Я зафиксировал стикерспам. Поскольку я ленивый, "
                                          "то честный (почти) рандом решил, что %s лишается права на "
                                          "использование стикеров (а также гифок и, внезапно, "
                                          "опросов) на полчаса. Причина - участие в спаме стикерами." % Cobb.get_chat_member(
                                              chat.chat_id, selected_user).user.first_name)

        time.sleep(settings.antisticker_timer)


@logger.catch
def process_update_usernames():
    while func_restarter() is None:
        query = MessageLog.select().where(
            (MessageLog.message_date < int(time.time()) - settings.time_to_delete_garbage) & (
                    MessageLog.marked_to_delete == True))
        if query.exists():
            for row in query:
                try:
                    Cobb.delete_message(row.chat_id, row.message_id)
                    logger.info("Message %s in %s successfully deleted " % (row.message_id, row.chat_id))
                except telebot.apihelper.ApiException:
                    logger.exception(
                        "Message %s in %s deleting failed, target message was deleted by someone" % (
                            row.message_id, row.chat_id),
                        backtrace=False)
                subquery = MessageLog.update(marked_to_delete=False).where(MessageLog.id == row.id)
                subquery.execute()

        else:
            pass
        time.sleep(30)


@logger.catch
def func_callback_query_factory(callback_code, *args):
    callback_text = str(callback_code)
    for arg in args:
        callback_text += "|" + str(arg)
    return callback_text


@Cobb.message_handler(commands=['aquote'])
@logger.catch
def bot_add_quote(message):
    if func_have_privileges(message):
        func_add_quote(message)
    else:
        Cobb.reply_to(message, "Действие доступно только модератору чата.")


@Cobb.message_handler(commands=['rmquote'])
@logger.catch
def bot_remove_quote(message):
    if func_have_privileges(message):
        spl = message.text.split(' ')
        if len(spl) != 1 and spl[1].isdigit():
            func_rm_quote(message, int(spl[1]))
        else:
            Cobb.reply_to(message, "Номер цитаты либо не указан, либо не является числом.")
    else:
        Cobb.reply_to(message, "Действие доступно только модератору чата.")


@Cobb.message_handler(commands=['quote'])
@logger.catch
def bot_get_quote(message):
    spl = message.text.split(' ')
    if len(spl) == 1:
        func_get_quote(message)
    elif not spl[1].isdigit():
        Cobb.reply_to(message, "Номер цитаты невалиден")
    else:
        func_get_quote(message, int(spl[1]))


@Cobb.message_handler(commands=['horoscope'])
@logger.catch
def bot_get_quote(message):
    divination = func_get_horoscope()
    spells = ["ахалай-махалай",
              "ляськи-масяськи",
              "сим-салабим",
              "пикапу-трикапу",
              "лорики-ёрики",
              "снип-снап-снурре",
              "снурре-базилюрре",
              "бофара-чуфара",
              "абра-кадабра",
              "трах-тибидох",
              "колдуй бабка, колдуй дед",
              "флюггегехаймен",
              "скорики-морики",
              "крибле-крабле-бумс",
              "крекс-пекс-фекс",
              "керальтус-нивус",
              "бип-боп",
              "бип-буп"]

    reply_text = "╰( ͡° ͜ʖ ͡° )つ──☆\n_- %s, %s! Вижу, вижу судьбу!_\n\n*%s:*\n%s" % (
        random.choice(spells).capitalize(), random.choice(spells),
        divination.author, divination.text)
    Cobb.reply_to(message, reply_text, parse_mode='Markdown')


@Cobb.message_handler(commands=['allquotes'])
@logger.catch
def bot_get_all_quotes(message):
    func_get_all_quote_ids(message)


@Cobb.message_handler(commands=['status'])
def bot_status(message):
    try:
        func_log_chat_message(message)
        if message.from_user.id == settings.master_id:
            func_log_chat_message(message)
            query = Chats.select().where(Chats.chat_id == message.chat.id).get()
            text = "CID: %s\n" \
                   "Title: %s\n" \
                   "Link: %s\n" \
                   "Rules: %s\n" \
                   "Welcome set: %s\n" \
                   "Welcome: %s\n" \
                   "Logging: %s\n" \
                   "Logging pics: %s\n" \
                   "Antibot on: %s\n" \
                   "Antibot: %s\n" \
                   "Remove voices: %s" % (query.chat_id, query.chat_title, query.chat_link, query.rules_text,
                                          query.welcome_set, query.welcome_text, query.log_text, query.log_pics,
                                          query.antibot, query.antibot_text, query.rm_voices)
            dn = os.path.dirname(os.path.realpath(__file__))
            fn = os.path.join(dn, "Cobb.log")
            f = open(fn, 'r')
            Cobb.send_document(message.chat.id, f, caption=text)
            f.close()

    except Exception as e:
        print(e)


# @Cobb.message_handler(commands=['rbt'])
# def bot_reboot(message):
#     uid = message.from_user.id
#     cid = message.chat.id
#     # query = Users.select().where(Users.user_id == uid & Users.chat_id == cid & Users.is_boss == True)
#     if uid == settings.master_id:
#         func_log_chat_message(message)
#         func_clean(Cobb.reply_to(message, "Завершаюсь"))
#         func_restart_writer(cid)
#         os.kill(os.getpid(), signal.SIGTERM)
#     else:
#         func_clean(Cobb.reply_to(message, "Это может сделать только владелец бота."))


@Cobb.message_handler(commands=['antibot'])
@logger.catch
def bot_antibot_trigger(message):
    try:
        func_log_chat_message(message)
        uid = message.from_user.id
        cid = message.chat.id
        title = message.chat.title
        uname = message.from_user.username
        if func_have_privileges(message):
            if Chats.get(Chats.chat_id == cid).antibot:
                query = Chats.update(antibot=False).where(Chats.chat_id == cid)
                query.execute()
                Cobb.reply_to(message, "Антибот выключен.")

                logger.info("User @%s (%s) switch off antibot in chat %s (%s)" % (
                    uname, uid, title, cid))
            else:
                query = Chats.update(antibot=True).where(Chats.chat_id == cid)
                query.execute()
                Cobb.reply_to(message, "Антибот включен.")

                logger.info("User @%s (%s) switch on antibot in chat %s (%s)" % (
                    uname, uid, title, cid))
        else:
            Cobb.reply_to(message, "Nope.")
    except Exception as e:
        logger.exception(e)


@Cobb.message_handler(commands=['welcome'])
@logger.catch
def bot_welcome_trigger(message):
    try:
        uid = message.from_user.id
        cid = message.chat.id
        title = message.chat.title
        uname = message.from_user.username
        if func_have_privileges(message):
            if Chats.get(Chats.chat_id == cid).welcome_set:
                query = Chats.update(welcome_set=False).where(Chats.chat_id == cid)
                query.execute()
                Cobb.reply_to(message, "Приветственное сообщение выключено.")

                logger.info("User @%s (%s) switch off welcome in chat %s (%s)" % (
                    uname, uid, title, cid))
            else:
                query = Chats.update(welcome_set=True).where(Chats.chat_id == cid)
                query.execute()
                Cobb.reply_to(message, "Приветственное сообщение включено.")

                logger.info("User @%s (%s) switch on welcome in chat %s (%s)" % (
                    uname, uid, title, cid))
        else:
            Cobb.reply_to(message, "Nope.")
    except Exception as e:
        logger.exception(e)


@Cobb.message_handler(content_types=["new_chat_members"])
@logger.catch
def bot_new_chat_members(message):
    try:
        cid = message.chat.id
        bot_id = Cobb.get_me()
        if bot_id.id == message.new_chat_member.id:
            if message.from_user.id == settings.master_id:
                func_add_new_chat_or_change_info(message)
        else:
            if Chats.select().where(Chats.chat_id == cid).exists():
                uid = message.from_user.id
                incoming_user_username = '@' + Cobb.get_chat_member(cid, uid).user.username
                query = Chats.select().where(Chats.chat_id == cid).get()
                if Users.select(Users.user_id).where(
                        (Users.chat_id == cid) & (Users.user_id == uid)).exists():
                    if query.welcome_set:
                        func_clean(Cobb.reply_to(message, settings.returning_user_message % incoming_user_username))
                else:
                    if query.antibot:
                        Cobb.restrict_chat_member(cid, message.new_chat_member.id, int(time.time()),
                                                  can_send_messages=False,
                                                  can_send_media_messages=False,
                                                  can_send_other_messages=False)
                        antibot_callback_dataset = func_callback_query_factory(settings.antibot_callback_code,
                                                                               str(message.new_chat_member.id),
                                                                               query.welcome_set)

                        antibot_markup = InlineKeyboardMarkup()
                        antibot_markup.add(InlineKeyboardButton("🦐", callback_data=antibot_callback_dataset))
                        Cobb.reply_to(message, query.antibot_text, reply_markup=antibot_markup)
                    else:
                        if query.welcome_set:
                            func_clean(
                                Cobb.reply_to(message, Chats.select().where(Chats.chat_id == cid).get().welcome_text))
                        func_add_new_user(message)
    except Exception as e:
        logger.exception(e)


@Cobb.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        # noinspection PyShadowingNames
        cid = call.message.chat.id
        mid = call.message.message_id
        call_dataset = call.data.split("|")
        if int(call_dataset[0]) == settings.antibot_callback_code:
            clicking_user = str(call.from_user.id)

            if call_dataset[1] == clicking_user:
                if call_dataset[2] == "True":

                    Cobb.edit_message_text(
                        settings.antibot_passed + "\n" + Chats.select().where(Chats.chat_id == cid).get().welcome_text,
                        cid,
                        mid)
                else:
                    Cobb.edit_message_text(settings.antibot_passed, cid, mid)

                Cobb.answer_callback_query(callback_query_id=call.id, show_alert=True, text="Проверка пройдена.")

                # Cobb.restrict_chat_member(call.message.chat.id, call.from_user.id, int(time.time()), True, True, True,
                #                           True)
                Cobb.restrict_chat_member(cid, call_dataset[1], int(time.time()) + 600,
                                          can_send_messages=True,
                                          can_send_media_messages=False,
                                          can_send_other_messages=False)

                func_add_new_user(call.message, call.from_user.id)

                logger.info("User @%s (%s) in chat %s (%s) succesfully passed verification" % (
                    call.message.from_user.username, call.from_user.id, call.message.chat.title, cid))
        if int(call_dataset[0]) == settings.mute_callback_code:
            clicking_user = str(call.from_user.id)
            if call_dataset[2] == clicking_user:
                if call_dataset[3] != "Cancel":
                    Cobb.restrict_chat_member(cid, call_dataset[1], int(time.time()) + int(call_dataset[3]), False,
                                              False, False, False)
                    Cobb.edit_message_text("На пользователя %s наложена молчанка до: %s" % (
                        Cobb.get_chat_member(cid, call_dataset[1]).user.first_name,
                        str(datetime.datetime.utcfromtimestamp(
                            int(int(time.time()) + int(call_dataset[3]) + 10800)).strftime(
                            '%Y-%m-%d %H:%M:%S'))), cid, mid)
                else:
                    Cobb.edit_message_text("Команда отменена", cid, mid)
                Cobb.answer_callback_query(callback_query_id=call.id, show_alert=False)




    except Exception as e:
        logger.exception(e)


@Cobb.message_handler(commands=['whois'])
@logger.catch
def bot_whois(message):
    try:
        func_add_new_user(message)
        func_clean(message)
        cid = message.chat.id
        if message.reply_to_message is None:
            uid = message.from_user.id
            func_add_new_user(message)
        else:
            uid = message.reply_to_message.from_user.id

        query = Users.select().where((Users.user_id == uid) & (Users.chat_id == cid))

        if not query.exists():
            func_user_is_not_exists(message)
        else:
            requested_user = Cobb.get_chat_member(message.chat.id, uid)
            subquery = query.get()
            whois_info = "Пользователь: {first_name} ({nickname})\n" \
                         "ID: {user_id}\n" \
                         "Титул: {custom_title}\n" \
                         "Добавлен: {first_join}\n" \
                         "Сообщений (за 30 дней/всего): {messages_month}/{messages_all_time}\n" \
                         "Варны: {warn_count}".format(first_name=requested_user.user.first_name,
                                                      nickname=requested_user.user.username,
                                                      user_id=subquery.user_id,
                                                      custom_title=subquery.custom_title,
                                                      # karma=subquery.karma,
                                                      first_join=subquery.first_join,
                                                      messages_all_time=MessageLog.select().where(
                                                          (MessageLog.from_user_id == uid) & (
                                                                  MessageLog.chat_id == cid)).count(),
                                                      messages_month=MessageLog.select().where(
                                                          (MessageLog.from_user_id == uid) & (
                                                                  MessageLog.chat_id == cid) & (
                                                                  MessageLog.message_date > int(
                                                              time.time()) - 2592000)).count(),
                                                      warn_count=subquery.warn_count)

            func_clean(Cobb.reply_to(message, whois_info))
    except Exception as e:
        logger.exception(e)


@Cobb.message_handler(commands=['message_top'])
@logger.catch
def bot_message_top(message):
    func_add_new_user(message)
    func_clean(message)
    cid = message.chat.id
    top_head = "Количество сообщений у пользователей:\n"
    top_all = "- за все время:\n"
    top_month = "- за последние 30 дней:\n"
    func_log_chat_message(message)
    if not Chats.get(Chats.chat_id == cid).log_text:
        func_clean(Cobb.reply_to(message,
                                 "К сожалению, поскольку логирование чата отключено, статистика сообщений не ведется."))
    else:
        query = (MessageLog.select(MessageLog.from_user_username, fn.COUNT(MessageLog.from_user_id).alias('ct')).where(
            MessageLog.chat_id == cid).group_by(
            MessageLog.from_user_id).order_by(SQL('ct').desc()).limit(10))
        iter = 1
        for merged in query:
            top_all += "``` %s. @%s - %s```\n" % (iter, merged.from_user_username, merged.ct)
            iter += 1

        query = (MessageLog.select(MessageLog.from_user_username, fn.COUNT(MessageLog.from_user_id).alias('ct')).where(
            (MessageLog.chat_id == cid) & (
                    MessageLog.message_date > int(time.time()) - 2592000)).group_by(
            MessageLog.from_user_id).order_by(SQL('ct').desc()).limit(10))

        iter = 1
        for merged in query:
            top_month += "``` %s. @%s - %s```\n" % (iter, merged.from_user_username, merged.ct)
            iter += 1

        func_clean(Cobb.reply_to(message, top_head + top_all + "\n" + top_month, parse_mode="markdown"))


@Cobb.message_handler(content_types=['voice'])
@logger.catch
def bot_rm_voices(message):
    try:
        if not Cobb.get_chat_member(message.chat.id, Cobb.get_me().id).can_delete_messages:
            pass
        else:
            if Chats.get(Chats.chat_id == message.chat.id).rm_voices:
                Cobb.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        logger.critical(e)


@Cobb.message_handler(commands=['rm_voice'])
@logger.catch
def bot_rm_voices_trigger(message):
    uid = message.from_user.id
    cid = message.chat.id
    title = message.chat.title
    uname = message.from_user.username
    func_have_privileges(message)
    func_log_chat_message(message)
    if func_have_privileges(message):
        if Chats.get(Chats.chat_id == cid).rm_voices:
            query = Chats.update(rm_voices=False).where(Chats.chat_id == cid)
            query.execute()
            Cobb.reply_to(message, "Автоматическое удаление войсов отключено.")

            logger.info("User @%s (%s) switch off voices deleting in chat %s (%s)" % (
                uname, uid, title, cid))
        else:
            query = Chats.update(rm_voices=True).where(Chats.chat_id == cid)
            query.execute()
            Cobb.reply_to(message, "Автоматическое удаление войсов включено.")

            logger.info("User @%s (%s) switch on voices deleting in chat %s (%s)" % (
                uname, uid, title, cid))
    else:
        Cobb.reply_to(message, "Nope.")


@Cobb.message_handler(commands=['antistickerspam'])
@logger.catch
def bot_antistickerspam_trigger(message):
    uid = message.from_user.id
    cid = message.chat.id
    title = message.chat.title
    uname = message.from_user.username
    func_have_privileges(message)
    func_log_chat_message(message)
    if func_have_privileges(message):
        if Chats.get(Chats.chat_id == cid).antistickerspam:
            query = Chats.update(antistickerspam=False).where(Chats.chat_id == cid)
            query.execute()
            Cobb.reply_to(message, "Детектирование стикерспама отключено.")

            logger.info("User @%s (%s) switch off stickerspam detect in chat %s (%s)" % (
                uname, uid, title, cid))
        else:
            query = Chats.update(antistickerspam=True).where(Chats.chat_id == cid)
            query.execute()
            Cobb.reply_to(message, "Детектирование стикерспама включено.")

            logger.info("User @%s (%s) switch on stickerspam detect in chat %s (%s)" % (
                uname, uid, title, cid))
    else:
        Cobb.reply_to(message, "Nope.")


@Cobb.message_handler(commands=['log'])
@logger.catch
def bot_log_chat_trigger(message):
    uid = message.from_user.id
    cid = message.chat.id
    title = message.chat.title
    uname = message.from_user.username
    func_log_chat_message(message)

    if func_have_privileges(message):
        if Chats.get(Chats.chat_id == cid).log_text:
            query = Chats.update(log_text=False).where(Chats.chat_id == cid)
            query.execute()
            Cobb.reply_to(message, "Логирование чата отключено.")

            logger.info("User @%s (%s) switch off logging in chat %s (%s)" % (
                uname, uid, title, cid))
        else:
            query = Chats.update(log_text=True).where(Chats.chat_id == cid)
            query.execute()
            Cobb.reply_to(message, "Логирование чата включено.")

            logger.info("User @%s (%s) switch on logging in chat %s (%s)" % (
                uname, uid, title, cid))
    else:
        Cobb.reply_to(message, "Nope.")


@Cobb.message_handler(commands=['title'])
@logger.catch
def bot_set_user_title(message):
    func_add_new_user(message)
    func_clean(message)
    cid = message.chat.id
    func_have_privileges(message)
    func_log_chat_message(message)
    if func_have_privileges(message):
        if message.reply_to_message is None:
            uid = message.from_user.id
        else:
            uid = message.reply_to_message.from_user.id

        splitted_command = message.text.split(" ")
        if len(splitted_command) == 1:
            new_title = ""
        else:
            new_title = ' '.join(splitted_command[1:])

        query = Users.select().where((Users.user_id == uid) & (Users.chat_id == cid))

        if not query.exists():
            func_user_is_not_exists(message)
        else:

            updated_user = Users.update(custom_title=new_title).where(Users.user_id == uid)
            updated_user.execute()
            title_change_info = "Титул для %s успешно изменен: %s" % (
                Cobb.get_chat_member(message.chat.id, uid).user.first_name,
                Users.select().where((Users.user_id == uid) & (Users.chat_id == cid)).get().custom_title)
            Cobb.reply_to(message, title_change_info)

    else:
        func_clean(Cobb.reply_to(message, "Nope."))


@Cobb.message_handler(commands=['allow', 'deny', 'rmall'])
@logger.catch
def allow_deny_list(message):
    try:
        if func_have_privileges(message):
            if message.reply_to_message is None:
                func_clean(
                    Cobb.reply_to(message, "Для использования этой команды необходимо ответить ей на сообщение."))
            elif message.from_user.id == message.reply_to_message.from_user.id:
                func_clean(Cobb.reply_to(message, "Эту команду нельзя применить на себя."))
            else:
                cid = message.chat.id
                uid = message.reply_to_message.from_user.id

                if message.text == '/allow':
                    if AllowedUsers.select().where(
                            (AllowedUsers.user_id == uid) & (AllowedUsers.chat_id == message.chat.id)).exists():
                        func_clean(
                            Cobb.reply_to(message, "У пользователя уже есть права"))
                    else:
                        AllowedUsers.insert(user_id=uid, chat_id=cid).execute()
                        func_clean(
                            Cobb.reply_to(message, "Контроль над ботом в этом чате теперь доступен этому пользователю"))
                if message.text == '/deny':
                    if AllowedUsers.select().where(
                            (AllowedUsers.user_id == uid) & (AllowedUsers.chat_id == message.chat.id)).exists():
                        query = AllowedUsers.delete().where(
                            (AllowedUsers.user_id == uid) & (AllowedUsers.chat_id == message.chat.id))
                        query.execute()
                        func_clean(
                            Cobb.reply_to(message, "Пользователь больше не может контролировать бота в этом чате."))
                    else:
                        func_clean(
                            Cobb.reply_to(message, "Пользователь и так не контролирует меня :<"))
                if message.text == '/rmall':
                    if AllowedUsers.select().where((AllowedUsers.user_id == uid)).exists():
                        query = AllowedUsers.delete().where((AllowedUsers.user_id == uid))
                        query.execute()
                        func_clean(
                            Cobb.reply_to(message, "Пользователь больше не может контролировать бота в любом чате."))
                    func_clean(
                        Cobb.reply_to(message, "Пользователь и так не контролирует меня нигде :<"))
        else:
            func_clean(
                Cobb.reply_to(message,
                              "Для использования этой команды необходимо иметь права управления ботом в этом чате или быть создателем."))
    except Exception as e:
        logger.critical(e)


@Cobb.message_handler(commands=['warn'])
@logger.catch
def bot_moderation(message):
    try:
        if func_have_privileges(message):
            if message.reply_to_message is None:
                func_clean(
                    Cobb.reply_to(message, "Для использования этой команды необходимо ответить ей на сообщение."))
            elif message.from_user.id == message.reply_to_message.from_user.id:
                func_clean(Cobb.reply_to(message, "Эту команду нельзя применить на себя."))
            else:
                cid = message.chat.id
                uid = message.reply_to_message.from_user.id
                target_user = Cobb.get_chat_member(message.chat.id, uid)
                if target_user.status == "administrator" or target_user.status == "creator":
                    func_clean(Cobb.reply_to(message, "Эту команду нельзя использовать на модератора/создателя чата!"))
                else:
                    if not Users.select().where((Users.user_id == uid) & (Users.chat_id == cid)).exists():
                        func_add_new_user(message, uid)
                        Cobb.reply_to(message, 'Пользователь отсутствовал в базе данных, добавлен.')
                    func_log_chat_message(message)
                    Users.update(warn_count=Users.warn_count + 1).where(
                        (Users.user_id == uid) & (Users.chat_id == cid)).execute()
                    Cobb.delete_message(cid, message.reply_to_message.message_id)
                    Cobb.send_message(cid, "Пользователю %s выдано предупреждение, сейчас предупреждений: %s" % (
                        target_user.user.first_name,
                        Users.select().where((Users.user_id == uid) & (Users.chat_id == cid)).get().warn_count))
        else:
            func_clean(Cobb.reply_to(message, "Нет прав."))
    except Exception as e:
        logger.critical(e)


@Cobb.message_handler(commands=['unwarn'])
@logger.catch
def bot_moderation(message):
    try:
        if func_have_privileges(message):
            if message.reply_to_message is None:
                func_clean(
                    Cobb.reply_to(message, "Для использования этой команды необходимо ответить ей на сообщение."))
            elif message.from_user.id == message.reply_to_message.from_user.id:
                func_clean(Cobb.reply_to(message, "Эту команду нельзя применить на себя."))
            else:
                cid = message.chat.id
                uid = message.reply_to_message.from_user.id
                if Users.select().where(
                        (Users.user_id == uid) & (Users.chat_id == message.chat.id)).get().warn_count < 1:
                    func_clean(
                        Cobb.reply_to(message, "Количество варнов у пользователя не может быть меньше нуля."))
                else:
                    updating_user = Users.update(warn_count=Users.warn_count - 1).where(
                        (Users.user_id == uid) & (Users.chat_id == cid))
                    updating_user.execute()
                    Cobb.reply_to(message,
                                  "C пользователя %s снято предупреждение, сейчас предупреждений: %s" % (
                                      Cobb.get_chat_member(message.chat.id, uid).user.first_name,
                                      Users.select().where(
                                          (Users.user_id == uid) & (Users.chat_id == cid)).get().warn_count))
        else:
            func_clean(Cobb.reply_to(message, "Нет прав."))
    except Exception as e:
        logger.critical(e)


@Cobb.message_handler(commands=['mute'])
@logger.catch
def bot_moderation(message):
    try:
        if func_have_privileges(message):
            if message.reply_to_message is None:
                func_clean(
                    Cobb.reply_to(message, "Для использования этой команды необходимо ответить ей на сообщение."))
            elif message.from_user.id == message.reply_to_message.from_user.id:
                func_clean(Cobb.reply_to(message, "Эту команду нельзя применить на себя."))
            else:
                target_user_id = message.reply_to_message.from_user.id
                target_user = Cobb.get_chat_member(message.chat.id, target_user_id)
                if target_user.status == "administrator" or target_user.status == "creator":
                    func_clean(Cobb.reply_to(message, "Эту команду нельзя использовать на модератора/создателя чата!"))
                else:
                    func_log_chat_message(message)
                    mute_markup = InlineKeyboardMarkup()
                    mute_markup.add(InlineKeyboardButton("10 минут", callback_data=func_callback_query_factory(
                                        settings.mute_callback_code, str(target_user_id), str(message.from_user.id),
                                        "600")),
                                    InlineKeyboardButton("1 час", callback_data=func_callback_query_factory(
                                        settings.mute_callback_code, str(target_user_id), str(message.from_user.id),
                                        "3600")),
                                    InlineKeyboardButton("8 часов", callback_data=func_callback_query_factory(
                                        settings.mute_callback_code, str(target_user_id), str(message.from_user.id),
                                        "28800")),
                                    InlineKeyboardButton("1 сутки", callback_data=func_callback_query_factory(
                                        settings.mute_callback_code, str(target_user_id), str(message.from_user.id),
                                        "86400")),
                                    InlineKeyboardButton("Отмена", callback_data=func_callback_query_factory(
                                        settings.mute_callback_code, str(target_user_id), str(message.from_user.id),
                                        "Cancel"))
                                    )
                    Cobb.reply_to(message.reply_to_message, "На сколько времени наложить молчанку?",
                                  reply_markup=mute_markup)

        else:
            func_clean(Cobb.reply_to(message, "Нет прав."))
    except Exception as e:
        logger.critical(e)


@Cobb.message_handler(commands=['ban'])
@logger.catch
def bot_moderation(message):
    try:
        if func_have_privileges(message):
            if message.reply_to_message is None:
                func_clean(
                    Cobb.reply_to(message, "Для использования этой команды необходимо ответить ей на сообщение."))
            elif message.from_user.id == message.reply_to_message.from_user.id:
                func_clean(Cobb.reply_to(message, "Эту команду нельзя применить на себя."))
            else:
                cid = message.chat.id
                uid = message.reply_to_message.from_user.id
                target_user = Cobb.get_chat_member(message.chat.id, uid)
                if target_user.status == "administrator" or target_user.status == "creator":
                    func_clean(Cobb.reply_to(message, "Эту команду нельзя использовать на модератора/создателя чата!"))
                else:
                    if not Users.select().where((Users.user_id == uid) & (Users.chat_id == cid)).exists():
                        func_add_new_user(message, uid)
                        Cobb.reply_to(message, 'Пользователь отсутствовал в базе данных, добавлен.')
                    func_log_chat_message(message)
                    Cobb.kick_chat_member(cid, uid)
                    # Cobb.delete_message(cid, message.reply_to_message.message_id)
                    Cobb.send_message(cid, "Пользователь %s был забанен." % target_user.user.first_name)
        else:
            func_clean(Cobb.reply_to(message, "Нет прав."))
    except Exception as e:
        logger.critical(e)

@Cobb.message_handler(commands=['jericho'])
@logger.catch
def bot_moderation(message):
    try:
        if message.from_user.id == settings.master_id:
            # msg = "Система Иерихон запущена.\n"
            #
            # if message.reply_to_message is None:
            #     id_for_ban = message.text.split(' ')[1:]
            #     msg+= "Список id для бана: %s\n" % id_for_ban
            #     for uid in id_for_ban:
            #         for cid in settings.chat_list:
            #             Cobb.kick_chat_member(cid, int(uid))
            #     msg+= "Выполнение завершено."
            #     Cobb.send_message(message.chat.id, msg)
            # elif message.from_user.id == message.reply_to_message.from_user.id:
            if message.reply_to_message is None:
                pass
            else:
                if message.from_user.id == message.reply_to_message.from_user.id:
                    func_clean(Cobb.reply_to(message, "Эту команду нельзя применить на себя."))
                else:
                    for cid in settings.chat_list:
                        Cobb.kick_chat_member(cid, message.reply_to_message.from_user.id)
                    Cobb.delete_message(cid, message.reply_to_message.message_id)
                    # Cobb.send_message(message.chat.id, "Иерихон запущен.\n"
                    #                                    "Пользователь забанен во всех чатах системы.\n"
                    #                                    "Выполнение завершено.")
                    Cobb.send_photo(message.chat.id, 'https://i.ytimg.com/vi/jBfo87raroE/maxresdefault.jpg',
                                    caption="Иерихон запущен.\n"
                                            "Пользователь забанен во всех чатах системы.\n"
                                            "Выполнение завершено.")

        else:
            func_clean(Cobb.reply_to(message, "Нет прав."))
    except Exception as e:
        logger.critical(e)

@Cobb.edited_message_handler()
def bot_message_edited(message):
    if message.chat.type != 'private':
        func_log_chat_message(message)
    else:
        pass


@Cobb.message_handler(commands=['addchat'])
@logger.catch
def bot_add_chat_link(message):
    try:
        if message.from_user.id == settings.master_id:
            spl = message.text.split(" ")
            subquery = ChatLinks.select().where(ChatLinks.command == spl[1])
            if not subquery.exists():
                ChatLinks.insert(command=spl[1], text=spl[2]).execute()
                Cobb.reply_to(message, "Команда %s с линком %s успешно добавлена." % (spl[1], spl[2]))
            else:
                ChatLinks.update(text=spl[2]).where(ChatLinks.command == spl[1]).execute()
                Cobb.reply_to(message, "Линк для команды %s изменен на %s" % (spl[1], spl[2]))
        else:
            func_clean(Cobb.reply_to(message, "Прошу прощения, эта функция доступна только владельцу бота."))
    except Exception as e:
        logger.critical(e)


@Cobb.message_handler(commands=['rules'])
@logger.catch
def bot_get_chat_rules(message):
    try:
        func_log_chat_message(message)
        rules = Chats.select().where(Chats.chat_id == message.chat.id).get().rules_text
        if rules != '':
            func_clean(Cobb.reply_to(message, rules))
        else:
            func_clean(Cobb.reply_to(message, "Правила для чата еще не заданы."))
    except Exception as e:
        logger.exception(e)


@Cobb.message_handler(commands=['setrules'])
@logger.catch
def bot_set_chat_rules(message):
    try:
        func_log_chat_message(message)
        if func_have_privileges(message):
            if len(message.text) < 10:
                func_clean(Cobb.reply_to(message, "Правила заданы некорректно"))
            else:
                rules = message.text[10:]
                Chats.update(rules_text=rules).where(Chats.chat_id == message.chat.id).execute()
                func_clean(Cobb.reply_to(message, "Правила успешно изменены. Новый текст правил:\n%s" % rules))
        else:
            func_clean(Cobb.reply_to(message, "Изменение правил доступно только модераторам и владельцу чата."))
    except Exception as e:
        logger.exception(e)


@Cobb.message_handler(commands=['rmrules'])
@logger.catch
def bot_remove_chat_rules(message):
    try:
        func_log_chat_message(message)
        if func_have_privileges(message):
            Chats.update(rules_text="").where(Chats.chat_id == message.chat.id).execute()
            func_clean(Cobb.reply_to(message, "Правила чата успешно стерты."))
        else:
            func_clean(Cobb.reply_to(message, "Изменение правил доступно только модераторам и владельцу чата."))
    except Exception as e:
        logger.exception(e)


@Cobb.message_handler(commands=['slap'])
@logger.catch
def bot_slap(message):
    try:
        func_log_chat_message(message)

        cid = message.chat.id
        uid = message.from_user.id
        spl = message.text.split(' ')
        Cobb.delete_message(message.chat.id, message.message_id)
        if len(spl) == 1:
            Cobb.send_message(cid, '@' + Cobb.get_chat_member(cid,
                                                              uid).user.username + ' slaps himself around a bit with a large trout')
        else:
            Cobb.send_message(cid, '@' + Cobb.get_chat_member(cid, uid).user.username + ' slaps ' + spl[
                1] + ' around a bit with a large trout')
    except Exception as e:
        logger.exception(e)


@Cobb.message_handler(commands=['me'])
@logger.catch
def bot_me(message):
    try:
        func_log_chat_message(message)

        cid = message.chat.id
        uid = message.from_user.id
        spl = message.text.split(' ')
        Cobb.delete_message(message.chat.id, message.message_id)
        if len(spl) == 1:
            Cobb.send_message(cid,
                              '@' + Cobb.get_chat_member(cid, uid).user.username + ' занимается чем-то подозрительным')
        else:
            Cobb.send_message(cid, '@' + Cobb.get_chat_member(cid, uid).user.username + ' ' + ' '.join(spl[1:]))

    except Exception as e:
        logger.exception(e)

@Cobb.message_handler(content_types=['sticker'])
@logger.catch
def bot__sticker_listener(message):
    func_log_chat_message(message)
    pass


@Cobb.message_handler(content_types=['text'])
@logger.catch
def bot_listener(message):
    try:
        if message.chat.type != 'private':
            func_add_new_user(message)
            func_add_new_chat_or_change_info(message)
            cid = message.chat.id
            if Chats.get(Chats.chat_id == cid).log_text:
                func_log_chat_message(message)

            # bot_automodify_karma(message)

            if message.text.startswith("/") and cid in settings.chat_list:
                available_links = chatlinks_loader()
                if settings.log_link_requests:
                    try:
                        link = Cobb.export_chat_invite_link(cid)
                    except Exception as e:
                        logger.exception(e)
                        link = "Chat link is unavialable"
                    text = "%s (%s/%s) in %s (%s/%s) requests %s\n%s" % (
                        message.from_user.first_name, message.from_user.username, message.from_user.id,
                        message.chat.title, message.chat.username, message.chat.id, message.text, link)
                    logger.info(text)
                    try:
                        Cobb.send_message(settings.master_id, text)
                    except Exception as e:
                        logger.exception(e)
                for key, value in available_links.items():
                    if message.text.startswith(key):
                        func_clean(Cobb.reply_to(message, value))
        else:
            pass
    except Exception as e:
        logger.exception(e)


if __name__ == '__main__':
    freeze_support()

    Users.create_table()
    Chats.create_table()
    MessageLog.create_table()
    Quotes.create_table()
    ChatLinks.create_table()

    GarbageCleaner = Process(target=process_garbage_collector, args=())
    GarbageCleaner.start()
    StickerCollector = Process(target=process_stickerspam_collector, args=())
    StickerCollector.start()

    while True:
        try:
            Cobb.polling(none_stop=True)
        except Exception as e:
            logger.exception(e)
            time.sleep(15)
            break
