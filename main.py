#!/usr/bin/python3
# coding=utf-8
import argparse
from peewee import *
import os
import sys
import signal
import time
import telebot
import datetime
from multiprocessing import Process, freeze_support
from loguru import logger
import csv
import settings

parser = argparse.ArgumentParser(add_help=True, description='Cobb Bot for Telegram')
parser.add_argument('--token', action='store', help='Authentication token [required]', required=True)
csv.register_dialect('localeDialect', quoting=csv.QUOTE_ALL, skipinitialspace=True, lineterminator='\n')

args = parser.parse_args()

bot_token = args.token  # Lenore token
Cobb = telebot.TeleBot(bot_token)
db = SqliteDatabase('JayneCobbDatabase.db', check_same_thread=False)
logger.add(sys.stderr, format="{time} {level} {message}", filter="my_module", level="INFO")
logger.add("Cobb.log", rotation="1 MB", enqueue=True)

restart_flag = False


class Users(Model):
    user_id = CharField()
    chat_id = IntegerField()
    first_join = DateField()
    messages_month = IntegerField()
    messages_all_time = IntegerField()
    warn_count = IntegerField()
    custom_title = CharField()
    is_boss = BooleanField()
    karma = IntegerField()

    class Meta:
        database = db


class Chats(Model):
    chat_id = IntegerField()
    chat_title = IntegerField()
    chat_link = CharField()
    rules_text = CharField()
    log_text = BooleanField()
    log_pics = BooleanField()
    antibot = BooleanField()
    rm_voices = BooleanField()

    class Meta:
        database = db


class Garbage(Model):
    chat_id = IntegerField()
    message_id = IntegerField()
    message_time = IntegerField()

    class Meta:
        database = db


class MonthlyResetMessages(Model):
    reset_month = IntegerField()


@logger.catch
def restarter():
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


restart_cid = restarter()
if restart_cid is not None:
    Cobb.send_message(restart_cid, "Новый код принят и запущен.")
    logger.info("Bot live at %s" % datetime.time)


@logger.catch
def restart_writer(cid):
    file = open("/tmp/JayneCobb.tmp", 'w')
    file.write(str(cid))
    file.close()


@logger.catch
def clean(message):
    subquery = Garbage.select().where(
        (Garbage.chat_id == message.chat.id) & (Garbage.message_id == message.message_id))
    if not subquery.exists():
        merked_message = Garbage.create(chat_id=message.chat.id,
                                        message_id=message.message_id,
                                        message_time=int(time.time()))
        merked_message.save()
        logger.info("Message %s in chat %s (%s) marked for deleting" % (
            message.message_id, message.chat.title, message.chat.id))
        return True


@logger.catch
def add_new_user_or_update_msg_count(message, given_uid=None):
    if given_uid is None:
        uid = message.from_user.id
    else:
        uid = given_uid
    cid = message.chat.id

    is_boss = False
    if uid == settings.master_id:
        is_boss = True

    subquery = Users.select().where((Users.user_id == uid) & (Users.chat_id == cid))
    if not subquery.exists():
        new_user = Users.create(user_id=uid,
                                chat_id=cid,
                                first_join=datetime.datetime.now(),
                                messages_month=0,
                                messages_all_time=0,
                                warn_count=0,
                                custom_title='',
                                is_boss=is_boss,
                                karma=0)
        new_user.save()

        logger.info("User @%s (%s) in chat %s (%s) added to db" % (
            message.from_user.username, uid, message.chat.title, cid))
    else:
        updated_user = Users.update(messages_all_time=Users.messages_all_time + 1,
                                    messages_month=Users.messages_month + 1).where(
            (Users.user_id == uid) & (Users.chat_id == cid))
        updated_user.execute()

        logger.info("Message count for  @%s (%s) in chat %s (%s) updated" % (
            message.from_user.username, uid, message.chat.title, cid))


@logger.catch
def add_new_chat_or_change_info(message):
    cid = message.chat.id

    if message.chat.type != 'private':

        subquery = Chats.select().where(Chats.chat_id == cid)
        if not subquery.exists():
            new_chat = Chats.create(chat_id=cid,
                                    chat_title=message.chat.title,
                                    chat_link=Cobb.export_chat_invite_link(cid),
                                    rules_text='',
                                    log_text=True,
                                    log_pics=False,
                                    antibot=False,
                                    rm_voices=True)
            new_chat.save()

            logger.info("New chat %s (%s) added to database" % (message.chat.title, cid))
        else:
            if Chats.select().where(Chats.chat_id == cid).get().chat_title != message.chat.title:
                update_chat_title = Chats.update(chat_title=message.chat.title).where(Chats.chat_id == cid)
                update_chat_title.execute()

                logger.info("Chat %s changed name to %s" % (cid, message.chat.title))


@logger.catch
def karma_change(cid, uid, change):
    #     change inc/dec == +/-
    if change == 1:
        updated_user = Users.update(karma=Users.karma + 1).where((Users.user_id == uid) & (Users.chat_id == cid))
    else:
        updated_user = Users.update(karma=Users.karma - 1).where((Users.user_id == uid) & (Users.chat_id == cid))
    updated_user.execute()


@logger.catch
def have_privileges(message):
    try:
        status = Cobb.get_chat_member(message.chat.id, message.from_user.id).status
        who = Users.select().where((Users.user_id == message.from_user.id) & (Users.chat_id == message.chat.id)).get()
        if status == "administrator" or status == "creator" or who.is_boss:
            return True
        else:
            return False
    except Exception as e:
        logger.critical(e)
        return False


@logger.catch
def add_chat_message_to_log(message, moderation=False, editing=False):
    if moderation == True:
        filename = "moderation_%s.csv" % message.chat.id
        row = [message.date, message.from_user.id, message.message_id, message.from_user.username,
               Cobb.get_chat_member(message.chat.id, message.reply_to_message.from_user.id).user.first_name,
               message.text]
    elif editing == True:
        filename = "%s.csv" % message.chat.id
        row = [message.date, message.from_user.id, message.message_id, message.from_user.username,
               "[EDITED]: " + message.text]
    else:
        filename = "%s.csv" % message.chat.id
        row = [message.date, message.from_user.id, message.message_id, message.from_user.username, message.text]
    try:
        with open(filename, 'a', encoding='utf-8') as csvFile:
            writer = csv.writer(csvFile, dialect='localeDialect')
            writer.writerow(row)
            csvFile.close()
    except Exception as e:
        logger.critical(e)


@logger.catch
def garbage_collector():
    while restarter() is None:
        query = Garbage.select().where(Garbage.message_time < int(time.time()) - settings.time_to_delete_garbage)
        if query.exists():
            for row in query:
                try:
                    Cobb.delete_message(row.chat_id, row.message_id)
                    logger.info("Message %s in %s successfully deleted " % (row.message_id, row.chat_id))
                except telebot.apihelper.ApiException:
                    logger.exception(
                        "Message %s in %s deleting failed, user deleted message first" % (row.message_id, row.chat_id),
                        backtrace=False)
                instance = Garbage.get(Garbage.id == row.id)
                instance.delete_instance()
        else:
            pass
        time.sleep(10)


@Cobb.message_handler(commands=['status'])
def bot_status(message):
    try:
        clean(Cobb.reply_to(message, "Online"))
    except Exception as e:
        print(e)


@Cobb.message_handler(commands=['rbt'])
def bot_reboot(message):
    uid = message.from_user.id
    cid = message.chat.id
    query = Users.select().where(Users.user_id == uid & Users.chat_id == cid & Users.is_boss == True)
    if query.exists():
        clean(Cobb.reply_to(message, "Завершаюсь"))
        restart_writer(cid)
        os.kill(os.getpid(), signal.SIGTERM)
    else:
        pass
        clean(Cobb.reply_to(message, "Nope"))


@Cobb.message_handler(commands=['whois'])
@logger.catch
def bot_whois(message):
    add_new_user_or_update_msg_count(message)
    clean(message)
    cid = message.chat.id
    if message.reply_to_message is None:
        uid = message.from_user.id
        add_new_user_or_update_msg_count(message)
    else:
        uid = message.reply_to_message.from_user.id

    query = Users.select().where((Users.user_id == uid) & (Users.chat_id == cid))

    if not query.exists():
        whois_info = "К сожалению, у меня пока нет информации об этом пользователе.\n" \
                     "Видимо, он еще не писал в чате с момента моего включения."
    else:
        requested_user = Cobb.get_chat_member(message.chat.id, uid)
        subquery = query.get()
        whois_info = "Пользователь: {first_name} ({nickname})\n" \
                     "ID: {user_id}\n" \
                     "Титул: {custom_title}\n" \
                     "Карма: {karma}\n" \
                     "Добавлен: {first_join}\n" \
                     "Сообщений (за месяц/всего): {messages_month}/{messages_all_time}\n" \
                     "Варны: {warn_count}".format(first_name=requested_user.user.first_name,
                                                  nickname=requested_user.user.username,
                                                  user_id=subquery.user_id,
                                                  custom_title=subquery.custom_title,
                                                  karma=subquery.karma,
                                                  first_join=subquery.first_join,
                                                  messages_all_time=subquery.messages_all_time,
                                                  messages_month=subquery.messages_month,
                                                  warn_count=subquery.warn_count)

    clean(Cobb.reply_to(message, whois_info))


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
    have_privileges(message)
    if have_privileges(message):
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


@Cobb.message_handler(commands=['log'])
@logger.catch
def bot_log_chat_trigger(message):
    uid = message.from_user.id
    cid = message.chat.id
    title = message.chat.title
    uname = message.from_user.username

    if have_privileges(message):
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


@Cobb.message_handler(commands=['+', '-'])
@logger.catch
def bot_modify_karma(message):
    add_new_user_or_update_msg_count(message)
    clean(message)
    if message.reply_to_message is None:
        clean(
            Cobb.reply_to(message, "Чтобы изменить кому-то карму, нужно ответить на его сообщение командой /+ или /-"))
    elif message.from_user.id == message.reply_to_message.from_user.id:
        clean(Cobb.reply_to(message, "Самому себе карму изменить нельзя!"))
    else:
        cid = message.chat.id
        uid = message.reply_to_message.from_user.id
        if not Users.select().where((Users.user_id == uid) & (Users.chat_id == cid)).exists():
            clean(Cobb.reply_to(message,
                                "К сожалению, пользователя еще нет в моей базе данных, изменить карму невозможно."))
        else:
            if message.text == '/+':
                karma_change(cid, uid, 1)
            else:
                karma_change(cid, uid, -1)

            clean(Cobb.reply_to(message, "Карма изменена для %s, текущее значение: %s" %
                                (Cobb.get_chat_member(cid, uid).user.first_name,
                                 Users.select().where((Users.user_id == uid) & (Users.chat_id == cid)).get().karma)))


@Cobb.message_handler(commands=['title'])
@logger.catch
def bot_set_user_title(message):
    add_new_user_or_update_msg_count(message)
    clean(message)
    cid = message.chat.id
    have_privileges(message)
    if have_privileges(message):
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
            title_change_info = "К сожалению, у меня пока нет информации об этом пользователе.\n" \
                                "Видимо, он еще не писал в чате с момента моего включения."
        else:

            updated_user = Users.update(custom_title=new_title).where((Users.user_id == uid) & (Users.chat_id == cid))
            updated_user.execute()
            title_change_info = "Титул для %s успешно изменен: %s" % (
                Cobb.get_chat_member(message.chat.id, uid).user.first_name,
                Users.select().where((Users.user_id == uid) & (Users.chat_id == cid)).get().custom_title)
        clean(Cobb.reply_to(message, title_change_info))

    else:
        Cobb.reply_to(message, "Nope.")


@Cobb.message_handler(commands=['warn'])
@logger.catch
def bot_modify_karma(message):
    add_new_user_or_update_msg_count(message)
    clean(message)
    if message.reply_to_message is None:
        clean(
            Cobb.reply_to(message, "Чтобы выдать кому-то варн, необходимо ответить на его сообщение командой /warn"))
    elif message.from_user.id == message.reply_to_message.from_user.id:
        clean(Cobb.reply_to(message, "Самому себе выдать варн нельзя!"))
    else:
        cid = message.chat.id
        uid = message.reply_to_message.from_user.id
        target_user = Cobb.get_chat_member(message.chat.id, uid)
        if target_user.status == "administrator" or target_user.status == "creator":
            clean(Cobb.reply_to(message, "Модератору/создателю выдать варн нельзя!"))
        else:
            if not Users.select().where((Users.user_id == uid) & (Users.chat_id == cid)).exists():
                clean(Cobb.reply_to(message,
                                    "К сожалению, пользователя еще нет в моей базе данных, выдать ему варн невозможно"))
            else:
                updating_user = Users.update(warn_count=Users.warn_count + 1).where(
                    (Users.user_id == uid) & (Users.chat_id == cid))
                updating_user.execute()
                add_chat_message_to_log(message, moderation=True)
                Cobb.reply_to(message, "Пользователю %s выдано предупреждение, сейчас предупреждений: %s" % (
                    target_user.user.first_name,
                    Users.select().where((Users.user_id == uid) & (Users.chat_id == cid)).get().warn_count))


@Cobb.edited_message_handler()
def bot_message_edited(message):
    if message.chat.type != 'private':
        uid = message.from_user.id
        cid = message.chat.id
        if Chats.get(Chats.chat_id == cid).log_text:
            LogMessage = Process(target=add_chat_message_to_log, args=(message, False, True,))
            LogMessage.start()
    else:
        pass


@Cobb.message_handler(content_types=['text'])
@logger.catch
def bot_listener(message):
    if message.chat.type != 'private':


        add_new_user_or_update_msg_count(message)
        add_new_chat_or_change_info(message)

        uid = message.from_user.id
        cid = message.chat.id
        if Chats.get(Chats.chat_id == cid).log_text:
            LogMessage = Process(target=add_chat_message_to_log, args=(message,))
            LogMessage.start()
    else:
        pass


if __name__ == '__main__':
    freeze_support()

    Users.create_table()
    Chats.create_table()
    Garbage.create_table()

    GarbageCleaner = Process(target=garbage_collector, args=())
    GarbageCleaner.start()

    while True:
        try:
            Cobb.polling(none_stop=True)
        except Exception as e:
            logger.exception(e)
            time.sleep(15)
            break
