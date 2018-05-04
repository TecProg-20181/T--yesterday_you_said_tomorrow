import sqlalchemy
import db
import datetime
import constants
from urlhandler import UrlHandler
from db import Task


class MessageException(Exception):
    """Just to specify a kind of Exception"""
    pass


class TaskManager:
    def __init__(self):
        self.url_handler = UrlHandler()
        
    def deps_text(self, task, chat, preceed=''):
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

            icon = constants.NEW_ICON
            if dep.status == 'DOING':
                icon = constants.DOING_ICON
            elif dep.status == 'DONE':
                icon = constants.DONE_ICON

            if i + 1 == len(task.dependencies.split(',')[:-1]):
                line += '└── [[{}]] {} {}\n'.format(dep.id, icon, dep.name)
                line += self.deps_text(dep, chat, preceed + '    ')
            else:
                line += '├── [[{}]] {} {}\n'.format(dep.id, icon, dep.name)
                line += self.deps_text(dep, chat, preceed + '│   ')

            text += line

        return text

    def get_task(self, msg, chat):
        """send message acusing missing id in the command"""
        if not msg.isdigit():
            self.url_handler.send_message("You must inform the task id", chat)
            raise MessageException('id not provided')
        task_id = int(msg)
        query = db.SESSION.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            self.url_handler.send_message("_404_ Task {} not found x.x".format(task_id), chat)
            raise MessageException('task not found')
        return task

    def new_task(self, name, chat):
        """Create and returns a new task named by the user"""
        task = Task(chat=chat,
                    name=name,
                    status='TODO',
                    dependencies='',
                    parents='',
                    priority='2')
        db.SESSION.add(task)
        db.SESSION.commit()
        self.url_handler.send_message("New task *TODO* [[{}]] {}".format(task.id, task.name), chat)
        return task

    def rename_task(self, msg, chat):
        """rename a task by id"""
        msg, text = self.split_message(msg)

        try:
            task = self.get_task(msg, chat)
        except MessageException:
            return
        if text == '':
            self.url_handler.send_message("""
                          You want to modify task {},
                          but you didn't provide any new text
                         """.format(task.id), chat)
            return

        old_text = task.name
        task.name = text
        db.SESSION.commit()
        self.url_handler.send_message("""
                      Task {} redefined from {} to {}
                     """.format(task.id, old_text, text), chat)

    def duplicate_task(self, msg, chat):
        """copy a task by id"""
        try:
            task = self.get_task(msg, chat)
        except MessageException:
            return

        dtask = self.new_task(task.name, chat)

        for item in task.dependencies.split(',')[:-1]:
            querry = db.SESSION.query(Task).filter_by(id=int(item), chat=chat)
            item = querry.one()
            item.parents += '{},'.format(dtask.id)

    def delete_task(self, msg, chat):
        """delete a task by id"""
        try:
            task = self.get_task(msg, chat)
        except MessageException:
            return
        dependencies = []
        for item in task.dependencies.split(',')[:-1]:
            dependencies.append(item)
        for item in task.parents.split(',')[:-1]:
            querry = db.SESSION.query(Task).filter_by(id=int(item), chat=chat)
            item = querry.one()
            item.dependencies = item.dependencies.replace('{},'.format(task.id), '')
        for item in dependencies:
            querry = db.SESSION.query(Task).filter_by(id=int(item), chat=chat)
            item = querry.one()
            item.parents = item.parents.replace('{},'.format(task.id), '')
        db.SESSION.delete(task)
        db.SESSION.commit()
        self.url_handler.send_message("Task [[{}]] deleted".format(task.id), chat)

    def set_task_status(self, msg, chat, status):
        """set status of task to TODO"""
        try:
            task = self.get_task(msg, chat)
        except MessageException:
            return
        task.status = status
        db.SESSION.commit()
        self.url_handler.send_message("*{}* task [[{}]] {}".format(status, task.id, task.name), chat)

    def list_tasks(self, chat, order):
        """lists all the tasks"""
        msg = ''

        msg += '\U0001F4CB Task List\n'
        query = (db.SESSION
                 .query(Task)
                 .filter_by(parents='', chat=chat)
                 .order_by(Task.id))
        for task in query.all():
            icon = constants.NEW_ICON
            if task.status == 'DOING':
                icon = constants.DOING_ICON
            elif task.status == 'DONE':
                icon = constants.DONE_ICON

            msg += '[[{}]] {} {}\n'.format(task.id, icon, task.name)
            msg += self.deps_text(task, chat)

        self.url_handler.send_message(msg, chat)

        msg = ''

        msg += constants.STATUS_ICON + '_Status_\n'

        status = ['TODO', 'DOING', 'DONE']
        status_icon = [constants.NEW_ICON, constants.DOING_ICON, constants.DONE_ICON]
        for status, status_icon in status, status_icon:

            query = query(status, chat, order)
            msg += '\n'+ status_icon + '*' + status + '*\n'
            for task in query.all():
                msg += '[[{}]] {} {} {}\n'.format(task.id, task.name, self.dict_priority(task.priority), task.duedate)

        self.url_handler.send_message(msg, chat)

    def query(self, status, chat, order):
        query = (db.SESSION
                 .query(Task)
                 .filter_by(status=status, chat=chat)
                 .order_by(order))
        return query


    def circular_dependency(self, task_id, depid, chat):
        """checks if link the task with a circular dependency
           will cause some circular dependency deadlock"""
        try:
            task = self.get_task(str(task_id), chat)
        except MessageException:
            return True
        if str(depid) in task.parents.split(',')[:-1]:
            return True
        for i in task.parents.split(',')[:-1]:
            if self.circular_dependency(i, depid, chat):
                return True
        return False

    def depend_on_task(self, msg, chat):
        """set dependencies of the task"""
        msg, text = self.split_message(msg)


        try:
            task = self.get_task(msg, chat)
        except MessageException:
            return

        if text == '':
            for i in task.dependencies.split(',')[:-1]:
                i = int(i)
                querry = db.SESSION.query(Task).filter_by(id=i, chat=chat)
                item = querry.one()
                item.parents = item.parents.replace('{},'.format(task.id), '')

            task.dependencies = ''
            self.url_handler.send_message("Dependencies removed from task {}".format(task.id),
                         chat)
        else:
            for depid in text.split(' '):
                if task.id == int(depid):
                    self.url_handler.send_message("Invalid task: {}".format(depid), chat)
                elif self.circular_dependency(task.id, depid, chat):
                    self.url_handler.send_message("Circular dependency, task {} depends on a task {}"
                                 .format(depid, task.id), chat)
                    continue
                else:
                    try:
                        taskdep = self.get_task(depid, chat)
                    except MessageException:
                        continue

                    taskdep.parents += str(task.id) + ','
                    deplist = task.dependencies.split(',')
                    if str(depid) not in deplist:
                        task.dependencies += str(depid) + ','

        db.SESSION.commit()
        self.url_handler.send_message("Task {} dependencies up to date".format(task.id), chat)

    def split_message(self, msg):
        text = ''
        if msg != '':
            if len(msg.split(' ', 1)) > 1:
                text = msg.split(' ', 1)[1]
            msg = msg.split(' ', 1)[0]
        return msg, text

    def prioritize_task(self, msg, chat):
        """set the priority of given task"""

        msg, text = self.split_message(msg)

        try:
            task = self.get_task(msg, chat)
        except MessageException:
            return

        if text == '':
            task.priority = ''
            self.url_handler.send_message("_Cleared_ all priorities from task {}"
                         .format(task.id), chat)
        else:
            if text.lower() not in ['high', 'medium', 'low']:
                self.url_handler.send_message("""
                                The priority *must be* one of the following:
                                high, medium, low
                            """, chat)
            else:
                task.priority = self.dict_priority(text.lower())
                self.url_handler.send_message("*Task {}* priority has priority *{}*"
                             .format(task.id, text.lower()), chat)
            db.SESSION.commit()

    def duedate_task(self, msg, chat):
        """set the priority of given task"""
        text = ''
        msg, text = self.split_message(msg)
        print(msg)


        try:
            task = self.get_task(msg, chat)
        except MessageException:
            return

        if text == '':
            task.duedate = ''
            self.url_handler.send_message("_Cleared_ duedate from task {}"
                         .format(task.name), chat)
        else:
            if self.validate_date(text, chat) is True:
                task.duedate = text
                self.url_handler.send_message("*Task {}* duedate is *{}*"
                             .format(task.id, text), chat)
        db.SESSION.commit()

    def validate_date(self, text, chat):
        try:
            datetime.datetime.strptime(text, '%Y-%m-%d')
        except ValueError:
            self.url_handler.send_message("""
                                     Incorrect data format, should be YYYY-MM-DD
                                 """, chat)
            return

        if datetime.datetime.strptime(text, '%Y-%m-%d') < datetime.datetime.now():
            self.url_handler.send_message("""You can't travel to the past, if you can please tell us how :) """, chat)
            return False
        return True

    def dict_priority(self, priority):
        """translate priority by the following dictionary"""
        return {
            'high': '1',
            'medium': '2',
            'low': '3',
            '1': 'high',
            '2': 'medium',
            '3': 'low',
        }[priority]