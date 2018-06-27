import constants
from db import Task
from urlhandler import UrlHandler
from taskmanager import TaskManager
from issuemanager import IssueManager


class MessageException(Exception):
    """Just to specify a kind of Exception"""
    pass


class BotManager:
    def __init__(self):
        self.task_manager = TaskManager()
        self.issue_manager = IssueManager()
        self.url_handler = UrlHandler()

    def handle_updates(self, updates, chat_bot):
        """read the user command and calls the property methods"""
        for update in updates["result"]:
            try:
                message = self.url_handler.get_message(update)
                command = message["text"].split(" ", 1)[0]
            except:
                return
            msg = ''
            if len(message["text"].split(" ", 1)) > 1:
                msg = message["text"].split(" ", 1)[1].strip()

            chat = message["chat"]["id"]

            print('\n\n\n')
            print(command, msg, chat)
            print('\n\n\n')

        menu_simple_command(command)

    def menu_simple_command(self, command):
        return {
            '/newIssue' or '/ni': self.issue_manager.new_issue(msg, chat),
            '/renameIssue' or '/ri': self.issue_manager.rename_issue(msg, chat),
            '/rename' or '/r': self.task_manager.rename_task(msg, chat),
            '/duplicate' or '/dc': self.task_manager.duplicate_task(msg, chat),
            '/delete' or '/d': self.task_manager.delete_task(msg, chat),
            '/todo': self.task_manager.set_task_status(msg, chat, constants.TODO),
            '/doing': self.task_manager.set_task_status(msg, chat, constants.DOING),
            '/done': self.task_manager.set_task_status(msg, chat, constants.DONE),
            '/listIssues' or '/li': self.issue_manager.list_issues(chat),
            '/dependson' or '/dp': self.task_manager.depend_on_task(msg, chat),
            '/priority' or '/p': self.task_manager.prioritize_task(msg, chat),
            '/duedate' or '/dd': self.task_manager.duedate_task(msg, chat),
        }.get(menu_command(command)) 

    def menu_command(self, command):
        if command == '/listP' or command == '/lp':
            order = Task.priority
            self.task_manager.list_tasks(chat, order)
        elif command == '/list' or command == '/l':
            order = Task.id
            self.task_manager.list_tasks(chat, order)
        elif command == '/start':
            self.url_handler.send_message("Welcome! Here is a list of things you can do.", chat)
            self.url_handler.send_message(constants.HELP, chat)
        elif command == '/help' or command == '/h':
            self.url_handler.send_message("Here is a list of things you can do.", chat)
            self.url_handler.send_message(constants.HELP, chat)
        else:
            response = chat_bot.predict([message['text']])
            print(response)
            print(message['text'])
            response = str(response)
            print(response)
            self.url_handler.send_message(response[2:-2], chat)
