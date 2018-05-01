"""
    Main code of Taskbot
    Generate a token from BotFather and make the following command at
        the terminal:
    export BOT_API_TOKEN="<your token here>"
    then, call python3 taskbot.py and voila, your bot is now running
"""
#!/usr/bin/env python3

import os
import time
import urllib
import json
import requests
import sqlalchemy
import db
from db import Task

TOKEN = os.environ['BOT_API_TOKEN']
URL = "https://api.telegram.org/bot{}/".format(TOKEN)

HELP = """
 /new NOME
 /todo ID
 /doing ID
 /done ID
 /delete ID
 /list
 /rename ID NOME
 /dependson ID ID...
 /duplicate ID
 /priority ID PRIORITY{low, medium, high}
 /help
"""


def get_url(url):
    """get response content of given url"""
    response = requests.get(url)
    content = response.content.decode("utf8")
    return content


def get_json_from_url(url):
    """get json content of the given url"""
    content = get_url(url)
    payload = json.loads(content)
    return payload


def get_updates(offset=None):
    """request new information from API"""
    url = URL + "getUpdates?timeout=100"
    if offset:
        url += "&offset={}".format(offset)
    payload = get_json_from_url(url)
    return payload


def send_message(text, chat_id, reply_markup=None):
    """send message to the user"""
    text = urllib.parse.quote_plus(text)
    url = URL + ("sendMessage?text={}&chat_id={}&parse_mode=Markdown"
                 .format(text, chat_id))
    if reply_markup:
        url += "&reply_markup={}".format(reply_markup)
    get_url(url)


def get_last_update_id(updates):
    """get the last update"""
    update_ids = []
    for update in updates["result"]:
        update_ids.append(int(update["update_id"]))

    return max(update_ids)


def deps_text(task, chat, preceed=''):
    """list tasks in a tree view"""
    text = ''

    for i in range(len(task.dependencies.split(',')[:-1])):
        line = preceed
        query = (db.SESSION
                 .query(Task)
                 .filter_by(id=int(task
                                   .dependencies
                                   .split(',')[:-1][i]), chat=chat))
        dep = query.one()

        icon = '\U0001F195'
        if dep.status == 'DOING':
            icon = '\U000023FA'
        elif dep.status == 'DONE':
            icon = '\U00002611'

        if i + 1 == len(task.dependencies.split(',')[:-1]):
            line += '└── [[{}]] {} {}\n'.format(dep.id, icon, dep.name)
            line += deps_text(dep, chat, preceed + '    ')
        else:
            line += '├── [[{}]] {} {}\n'.format(dep.id, icon, dep.name)
            line += deps_text(dep, chat, preceed + '│   ')

        text += line

    return text


def missing_id_error(chat):
    """send message acusing missing id in the command"""
    send_message("You must inform the task id", chat)


def new_task(name, chat):
    """Create a new issue with the named by user"""
    task = Task(chat=chat,
                name=name,
                status='TODO',
                dependencies='',
                parents='',
                priority='')
    db.SESSION.add(task)
    db.SESSION.commit()
    send_message("New task *TODO* [[{}]] {}".format(task.id, task.name), chat)


def rename_task(msg, chat):
    """rename a task by id"""
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        missing_id_error(chat)
    else:
        task_id = int(msg)
        query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        if text == '':
            send_message("""
                          You want to modify task {},
                          but you didn't provide any new text
                         """.format(task_id), chat)
            return

        old_text = task.name
        task.name = text
        db.SESSION.commit()
        send_message("""
                      Task {} redefined from {} to {}
                     """.format(task_id, old_text, text), chat)


def duplicate_task(msg, chat):
    """copy a task by id"""
    if not msg.isdigit():
        missing_id_error(chat)
    else:
        task_id = int(msg)
        query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        dtask = Task(chat=task.chat,
                     name=task.name,
                     status=task.status,
                     dependencies=task.dependencies,
                     parents=task.parents,
                     priority=task.priority,
                     duedate=task.duedate)
        db.SESSION.add(dtask)

        for item in task.dependencies.split(',')[:-1]:
            querry = db.SESSION.query(Task).filter_by(id=int(item), chat=chat)
            item = querry.one()
            item.parents += '{},'.format(dtask.id)

        db.SESSION.commit()
        send_message("New task *TODO* [[{}]] {}"
                     .format(dtask.id, dtask.name), chat)


def delete_task(msg, chat):
    """delete a task by id"""
    if not msg.isdigit():
        missing_id_error(chat)
    else:
        task_id = int(msg)
        query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return
        for item in task.dependencies.split(',')[:-1]:
            querry = db.SESSION.query(Task).filter_by(id=int(item), chat=chat)
            item = querry.one()
            item.parents = item.parents.replace('{},'.format(task.id), '')
        db.SESSION.delete(task)
        db.SESSION.commit()
        send_message("Task [[{}]] deleted".format(task_id), chat)


def todo_task(msg, chat):
    """set status of task to TODO"""
    if not msg.isdigit():
        missing_id_error(chat)
    else:
        task_id = int(msg)
        query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return
        task.status = 'TODO'
        db.SESSION.commit()
        send_message("*TODO* task [[{}]] {}".format(task.id, task.name), chat)


def doing_task(msg, chat):
    """set status of task to DOING"""
    if not msg.isdigit():
        missing_id_error(chat)
    else:
        task_id = int(msg)
        query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return
        task.status = 'DOING'
        db.SESSION.commit()
        send_message("*DOING* task [[{}]] {}".format(task.id, task.name), chat)


def done_task(msg, chat):
    """set status of task to DONE"""
    if not msg.isdigit():
        missing_id_error(chat)
    else:
        task_id = int(msg)
        query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return
        task.status = 'DONE'
        db.SESSION.commit()
        send_message("*DONE* task [[{}]] {}".format(task.id, task.name), chat)


def list_tasks(chat):
    """lists all the tasks"""
    msg = ''

    msg += '\U0001F4CB Task List\n'
    query = (db.SESSION
             .query(Task)
             .filter_by(parents='', chat=chat)
             .order_by(Task.id))
    for task in query.all():
        icon = '\U0001F195'
        if task.status == 'DOING':
            icon = '\U000023FA'
        elif task.status == 'DONE':
            icon = '\U00002611'

        msg += '[[{}]] {} {}\n'.format(task.id, icon, task.name)
        msg += deps_text(task, chat)

    send_message(msg, chat)
    msg = ''

    msg += '\U0001F4DD _Status_\n'

    query = (db.SESSION
             .query(Task)
             .filter_by(status='TODO', chat=chat)
             .order_by(Task.priority))
    msg += '\n\U0001F195 *TODO*\n'

    for task in query.all():
        msg += '[[{}]] {} {}\n'.format(task.id, task.name, dict_priority(task.priority))

    query = (db.SESSION
             .query(Task)
             .filter_by(status='DOING', chat=chat)
             .order_by(Task.priority))
    msg += '\n\U000023FA *DOING*\n'

    for task in query.all():
        msg += '[[{}]] {} {}\n'.format(task.id, task.name, dict_priority(task.priority))
    query = (db.SESSION
             .query(Task)
             .filter_by(status='DONE', chat=chat)
             .order_by(Task.priority))
    msg += '\n\U00002611 *DONE*\n'

    for task in query.all():
        msg += '[[{}]] {} {}\n'.format(task.id, task.name, dict_priority(task.priority))

    send_message(msg, chat)


def depend_on_task(msg, chat):
    """set dependencies of the task"""
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        missing_id_error(chat)
    else:
        task_id = int(msg)
        query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        if text == '':
            for i in task.dependencies.split(',')[:-1]:
                i = int(i)
                querry = db.SESSION.query(Task).filter_by(id=i, chat=chat)
                item = querry.one()
                item.parents = item.parents.replace('{},'.format(task.id), '')

            task.dependencies = ''
            send_message("Dependencies removed from task {}".format(task_id),
                         chat)
        else:
            for depid in text.split(' '):
                if not depid.isdigit():
                    send_message("""
                                    All dependencies ids must be numeric,
                                    and not {}
                                 """.format(depid), chat)
                else:
                    depid = int(depid)
                    query = (db.SESSION
                             .query(Task)
                             .filter_by(id=depid, chat=chat))
                    try:
                        taskdep = query.one()
                        taskdep.parents += str(task.id) + ','
                    except sqlalchemy.orm.exc.NoResultFound:
                        send_message("_404_ Task {} not found x.x"
                                     .format(depid), chat)
                        continue

                    deplist = task.dependencies.split(',')
                    if str(depid) not in deplist:
                        task.dependencies += str(depid) + ','

        db.SESSION.commit()
        send_message("Task {} dependencies up to date".format(task_id), chat)


def prioritize_task(msg, chat):
    """set the priority of given task"""
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        missing_id_error(chat)
    else:
        task_id = int(msg)
        query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        if text == '':
            task.priority = ''
            send_message("_Cleared_ all priorities from task {}"
                         .format(task_id), chat)
        else:
            if text.lower() not in ['high', 'medium', 'low']:
                send_message("""
                                The priority *must be* one of the following:
                                high, medium, low
                            """, chat)
            else:

                task.priority = dict_priority(text.lower())
                send_message("*Task {}* priority has priority *{}*"
                             .format(task_id, text.lower()), chat)
        db.SESSION.commit()


def dict_priority(priority):
    return {
        'high': '1',
        'medium': '2',
        'low': '3',
        '1': 'high',
        '2': 'medium',
        '3': 'low',
    }[priority]


def handle_updates(updates):
    """read the user command and calls the property methods"""
    for update in updates["result"]:
        if 'message' in update:
            message = update['message']
        elif 'edited_message' in update:
            message = update['edited_message']
        else:
            print('Can\'t process! {}'.format(update))
            return

        command = message["text"].split(" ", 1)[0]
        msg = ''
        if len(message["text"].split(" ", 1)) > 1:
            msg = message["text"].split(" ", 1)[1].strip()

        chat = message["chat"]["id"]

        print(command, msg, chat)

        if command == '/new':
            new_task(msg, chat)

        elif command == '/rename':
            rename_task(msg, chat)

        elif command == '/duplicate':
            duplicate_task(msg, chat)

        elif command == '/delete':
            delete_task(msg, chat)

        elif command == '/todo':
            todo_task(msg, chat)

        elif command == '/doing':
            doing_task(msg, chat)

        elif command == '/done':
            done_task(msg, chat)

        elif command == '/list':
            list_tasks(chat)

        elif command == '/dependson':
            depend_on_task(msg, chat)

        elif command == '/priority':
            prioritize_task(msg, chat)

        elif command == '/start':
            send_message("Welcome! Here is a list of things you can do.", chat)
            send_message(HELP, chat)

        elif command == '/help':
            send_message("Here is a list of things you can do.", chat)
            send_message(HELP, chat)

        else:
            send_message("I'm sorry " + str(message['chat']['first_name']) +
                         ". I'm afraid I can't do that.", chat)


def main():
    """get updates continuosly and manage instructions"""
    last_update_id = None

    while True:
        print("Updates")
        updates = get_updates(last_update_id)

        if updates["result"]:
            last_update_id = get_last_update_id(updates) + 1
            handle_updates(updates)

        time.sleep(0.5)


if __name__ == '__main__':
    main()
