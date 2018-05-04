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
            except MessageException:
                return

            command = message["text"].split(" ", 1)[0]
            msg = ''
            if len(message["text"].split(" ", 1)) > 1:
                msg = message["text"].split(" ", 1)[1].strip()

            chat = message["chat"]["id"]

            print(command, msg, chat)

            if command == '/new':
                self.task_manager.new_task(msg, chat)

            elif command == '/newIssue':
                self.issue_manager.new_issue(msg, chat)

            elif command == '/renameIssue':
                self.issue_manager.rename_issue(msg, chat)

            elif command == '/rename':
                self.task_manager.rename_task(msg, chat)

            elif command == '/duplicate':
                self.task_manager.duplicate_task(msg, chat)

            elif command == '/delete':
                self.task_manager.delete_task(msg, chat)

            elif command == '/todo':
                self.task_manager.set_task_status(msg, chat, constants.TODO)

            elif command == '/doing':
                self.task_manager.set_task_status(msg, chat, constants.DOING)

            elif command == '/done':
                self.task_manager.set_task_status(msg, chat, constants.DONE)

            elif command == '/listP':
                order = Task.priority
                self.task_manager.list_tasks(chat, order)

            elif command == '/listI':
                order = Task.id
                self.task_manager.list_tasks(chat, order)

            elif command == '/listIssues':
                self.issue_manager.list_issues(chat)

            elif command == '/dependson':
                self.task_manager.depend_on_task(msg, chat)

            elif command == '/priority':
                self.task_manager.prioritize_task(msg, chat)

            elif command == '/duedate':
                self.task_manager.duedate_task(msg, chat)

            elif command == '/start':
                self.url_handler.send_message("Welcome! Here is a list of things you can do.", chat)
                self.url_handler.send_message(constants.HELP, chat)

            elif command == '/help':
                self.url_handler.send_message("Here is a list of things you can do.", chat)
                self.url_handler.send_message(constants.HELP, chat)

            else:
                response = chat_bot.predict([message['text']])
                print(response)
                print(message['text'])
                response = str(response)
                print(response)
                self.url_handler.send_message(response[2:-2], chat)
