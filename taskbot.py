import os
import time
import urllib
import json
import requests
import sqlalchemy
import db
import datetime
import pandas
import yaml
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.feature_extraction.text import CountVectorizer
from db import Task
from sklearn.linear_model import SGDClassifier

TOKEN = os.environ['BOT_API_TOKEN']
URL_TELEGRAM = "https://api.telegram.org/bot{}/".format(TOKEN)
URL_GITHUB = "https://api.github.com/repos/TecProg-20181/T--yesterday_you_said_tomorrow/issues"

TODO = 'TODO'
DOING = 'DOING'
DONE = 'DONE'
HELP = """
 /newIssue NOME
 /new NOME
 /todo ID
 /doing ID
 /done ID
 /delete ID
 /list{I (list by id), P (list by priority)}
 /listIssues
 /rename ID NOME
 /dependson ID ID...
 /duplicate ID
 /priority ID PRIORITY{low, medium, high}
 /duedate ID DATE{YYYY-MM-DD}
 /help
"""


class MessageException(Exception):
    """Just to specify a kind of Exception"""
    pass


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
    url = URL_TELEGRAM + "getUpdates?timeout=100"
    if offset:
        url += "&offset={}".format(offset)
    payload = get_json_from_url(url)
    return payload


def send_message(text, chat_id, reply_markup=None):
    """send message to the user"""
    text = urllib.parse.quote_plus(text)
    url = URL_TELEGRAM + ("sendMessage?text={}&chat_id={}&parse_mode=Markdown"
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


def get_task(msg, chat):
    """send message acusing missing id in the command"""
    if not msg.isdigit():
        send_message("You must inform the task id", chat)
        raise MessageException('id not provided')
    task_id = int(msg)
    query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
    try:
        task = query.one()
    except sqlalchemy.orm.exc.NoResultFound:
        send_message("_404_ Task {} not found x.x".format(task_id), chat)
        raise MessageException('task not found')
    return task


def new_task(name, chat):
    """Create and returns a new task named by the user"""
    task = Task(chat=chat,
                name=name,
                status='TODO',
                dependencies='',
                parents='',
                priority='2')
    db.SESSION.add(task)
    db.SESSION.commit()
    send_message("New task *TODO* [[{}]] {}".format(task.id, task.name), chat)
    return task


def new_issue(name, chat):
    """Create an Issue"""
    payload = "{\n  \"title\": \""+name+"\",\n  \"labels\": [\n    \"telegram\"\n  ]\n}"
    print(payload)
    headers = {
        'Content-Type': "application/json",
        'Authorization': "Basic WWVzdGVyZGF5WW91U2FpZFRvbW9ycm93Qm90Olllc3RlcmRheVlvdVNhaWRUb21vcnJvdw==",
        'Cache-Control': "no-cache",
        'Postman-Token': "49817fa1-698d-496d-b6e3-252e81bc792f"
    }

    response = requests.request("POST", URL_GITHUB, data=payload, headers=headers)

    print(response.text)

    return send_message("New Issue created {}".format(name), chat)


def rename_task(msg, chat):
    """rename a task by id"""
    text = ''
    msg, text = split_message(msg)

    try:
        task = get_task(msg, chat)
    except MessageException:
        return
    if text == '':
        send_message("""
                      You want to modify task {},
                      but you didn't provide any new text
                     """.format(task.id), chat)
        return

    old_text = task.name
    task.name = text
    db.SESSION.commit()
    send_message("""
                  Task {} redefined from {} to {}
                 """.format(task.id, old_text, text), chat)


def duplicate_task(msg, chat):
    """copy a task by id"""
    try:
        task = get_task(msg, chat)
    except MessageException:
        return

    dtask = new_task(task.name, chat)

    for item in task.dependencies.split(',')[:-1]:
        querry = db.SESSION.query(Task).filter_by(id=int(item), chat=chat)
        item = querry.one()
        item.parents += '{},'.format(dtask.id)


def delete_task(msg, chat):
    """delete a task by id"""
    try:
        task = get_task(msg, chat)
    except MessageException:
        return
    for item in task.dependencies.split(',')[:-1]:
        querry = db.SESSION.query(Task).filter_by(id=int(item), chat=chat)
        item = querry.one()
        item.parents = item.parents.replace('{},'.format(task.id), '')
    db.SESSION.delete(task)
    db.SESSION.commit()
    send_message("Task [[{}]] deleted".format(task.id), chat)


def set_task_status(msg, chat, status):
    """set status of task to TODO"""
    try:
        task = get_task(msg, chat)
    except MessageException:
        return
    task.status = status
    db.SESSION.commit()
    send_message("*{}* task [[{}]] {}".format(status, task.id, task.name), chat)


def list_tasks(chat, order):
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
             .order_by(order))
    msg += '\n\U0001F195 *TODO*\n'

    for task in query.all():
        msg += '[[{}]] {} {} {}\n'.format(task.id, task.name, dict_priority(task.priority), task.duedate)

    query = (db.SESSION
             .query(Task)
             .filter_by(status='DOING', chat=chat)
             .order_by(order))
    msg += '\n\U000023FA *DOING*\n'

    for task in query.all():
        msg += '[[{}]] {} {} {}\n'.format(task.id, task.name, dict_priority(task.priority), task.duedate)
    query = (db.SESSION
             .query(Task)
             .filter_by(status='DONE', chat=chat)
             .order_by(order))
    msg += '\n\U00002611 *DONE*\n'

    for task in query.all():
        msg += '[[{}]] {} {} {}\n'.format(task.id, task.name, dict_priority(task.priority), task.duedate)

    send_message(msg, chat)


def list_issues(chat):
    """lists all the issues active in the T--yesterday_you_said_tomorrow repo"""
    issues = get_json_from_url(URL_GITHUB)
    msg = ''
    msg += '\U0001F4CB Issues List\n\n'
    for aux in issues:
        msg += aux['title'] + '\n\n'

    send_message(msg, chat)


def circular_dependency(task_id, depid, chat):
    """checks if link the task with a circular dependency
       will cause some circular dependency deadlock"""
    try:
        task = get_task(str(task_id), chat)
    except MessageException:
        return True
    if str(depid) in task.parents.split(',')[:-1]:
        return True
    for i in task.parents.split(',')[:-1]:
        if circular_dependency(i, depid, chat):
            return True
    return False


def depend_on_task(msg, chat):
    """set dependencies of the task"""
    text = ''
    msg, text = split_message(msg)


    try:
        task = get_task(msg, chat)
    except MessageException:
        return

    if text == '':
        for i in task.dependencies.split(',')[:-1]:
            i = int(i)
            querry = db.SESSION.query(Task).filter_by(id=i, chat=chat)
            item = querry.one()
            item.parents = item.parents.replace('{},'.format(task.id), '')

        task.dependencies = ''
        send_message("Dependencies removed from task {}".format(task.id),
                     chat)
    else:
        for depid in text.split(' '):
            if task.id == int(depid):
                send_message("Invalid task: {}".format(depid), chat)
            elif circular_dependency(task.id, depid, chat):
                send_message("Circular dependency, task {} depends on a task {}"
                             .format(depid, task.id), chat)
                continue
            else:
                try:
                    taskdep = get_task(depid, chat)
                except MessageException:
                    continue

                taskdep.parents += str(task.id) + ','
                deplist = task.dependencies.split(',')
                if str(depid) not in deplist:
                    task.dependencies += str(depid) + ','

    db.SESSION.commit()
    send_message("Task {} dependencies up to date".format(task.id), chat)


def split_message(msg):
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]
    return msg, text


def prioritize_task(msg, chat):
    """set the priority of given task"""
    text = ''

    msg, text = split_message(msg)

    try:
        task = get_task(msg, chat)
    except MessageException:
        return

    if text == '':
        task.priority = ''
        send_message("_Cleared_ all priorities from task {}"
                     .format(task.id), chat)
    else:
        if text.lower() not in ['high', 'medium', 'low']:
            send_message("""
                            The priority *must be* one of the following:
                            high, medium, low
                        """, chat)
        else:
            task.priority = dict_priority(text.lower())
            send_message("*Task {}* priority has priority *{}*"
                         .format(task.id, text.lower()), chat)
        db.SESSION.commit()


def duedate_task(msg, chat):
    """set the priority of given task"""
    text = ''
    msg, text = split_message(msg)
    print(msg)


    try:
        task = get_task(msg, chat)
    except MessageException:
        return

    if text == '':
        task.duedate = ''
        send_message("_Cleared_ duedate from task {}"
                     .format(task.name), chat)
    else:
        if validate_date(text, chat) is True:
            task.duedate = text
            send_message("*Task {}* duedate is *{}*"
                         .format(task.id, text), chat)
    db.SESSION.commit()


def validate_date(text, chat):
    try:
        datetime.datetime.strptime(text, '%Y-%m-%d')
    except ValueError:
        send_message("""
                                 Incorrect data format, should be YYYY-MM-DD
                             """, chat)
        return

    if datetime.datetime.strptime(text, '%Y-%m-%d') < datetime.datetime.now():
        send_message("""You can't travel to the past, if you can please tell us how :) """, chat)
        return False
    return True


def get_message(update):
    """return the message catched by update"""
    if 'message' in update:
        message = update['message']
    elif 'edited_message' in update:
        message = update['edited_message']
    else:
        print('Can\'t process! {}'.format(update))
        raise MessageException('Not recognizable message')
    return message


def dict_priority(priority):
    """translate priority by the following dictionary"""
    return {
        'high': '1',
        'medium': '2',
        'low': '3',
        '1': 'high',
        '2': 'medium',
        '3': 'low',
    }[priority]


def handle_updates(updates, chat_bot):
    """read the user command and calls the property methods"""
    for update in updates["result"]:
        try:
            message = get_message(update)
        except MessageException:
            return

        command = message["text"].split(" ", 1)[0]
        msg = ''
        if len(message["text"].split(" ", 1)) > 1:
            msg = message["text"].split(" ", 1)[1].strip()

        chat = message["chat"]["id"]

        print(command, msg, chat)

        if command == '/new':
            new_task(msg, chat)

        if command == '/newIssue':
            new_issue(msg, chat)

        elif command == '/rename':
            rename_task(msg, chat)

        elif command == '/duplicate':
            duplicate_task(msg, chat)

        elif command == '/delete':
            delete_task(msg, chat)

        elif command == '/todo':
            set_task_status(msg, chat, TODO)

        elif command == '/doing':
            set_task_status(msg, chat, DOING)

        elif command == '/done':
            set_task_status(msg, chat, DONE)

        elif command == '/listP':
            order = Task.priority
            list_tasks(chat, order)

        elif command == '/listI':
            order = Task.id
            list_tasks(chat, order)

        elif command == '/listIssues':
            list_issues(chat)

        elif command == '/dependson':
            depend_on_task(msg, chat)

        elif command == '/priority':
            prioritize_task(msg, chat)

        elif command == '/duedate':
            duedate_task(msg, chat)

        elif command == '/start':
            send_message("Welcome! Here is a list of things you can do.", chat)
            send_message(HELP, chat)

        elif command == '/help':
            send_message("Here is a list of things you can do.", chat)
            send_message(HELP, chat)

        else:
            response = chat_bot.predict([message['text']])
            print(response)
            print(message['text'])
            response = str(response)
            print(response)
            send_message(response[2:-2], chat)


def chat_bot_start():
    """start the module to chat with the bot"""
    os.chdir("english/")
    files = os.listdir(os.getcwd())

    text_clf = Pipeline([('vect', CountVectorizer()),
                         ('tfidf', TfidfTransformer()),
                         ('clf', SGDClassifier(loss='hinge', penalty='l2',
                                               alpha=1e-3, random_state=42,
                                               max_iter=5, tol=None)),
                         ])
    readX = []
    readY = []
    for file in files:
        print(file)
        with open(file, 'r') as stream:
            dict = yaml.load(stream)

        jsonDump = json.dumps(dict, indent=4, sort_keys=True)

        read = pandas.read_json(jsonDump)
        readX.extend(read[0])
        readY.extend(read[1])

    text_clf.fit(readX, readY)
    return text_clf


def main():
    """get updates continuosly and manage instructions"""
    last_update_id = None
    chat_bot = chat_bot_start()
    while True:
        print("Updates")
        updates = get_updates(last_update_id)

        if updates["result"]:
            last_update_id = get_last_update_id(updates) + 1
            handle_updates(updates, chat_bot)

        time.sleep(0.5)


if __name__ == '__main__':
    main()
