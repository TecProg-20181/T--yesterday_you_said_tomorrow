"""
    File containing constants useds in the rest of
    the program
"""
import os

TOKEN = os.environ['BOT_API_TOKEN']
URL_TELEGRAM = "https://api.telegram.org/bot{}/".format(TOKEN)
URL_GITHUB = "https://api.github.com/repos/TecProg-20181/T--yesterday_you_said_tomorrow/issues"

TODO = 'TODO'
DOING = 'DOING'
DONE = 'DONE'
HELP = """
 /new NOME
 /newIssue NOME
 /todo ID
 /doing ID
 /done ID
 /delete ID
 /list{I (list by id), P (list by priority)}
 /listIssues
 /rename ID NOME
 /renameIssue ID NOME
 /dependson ID ID...
 /duplicate ID
 /priority ID PRIORITY{low, medium, high}
 /duedate ID DATE{YYYY-MM-DD}
 /help
"""

# ICONS
NEW_ICON = '\U0001F195'
DOING_ICON = '\U000023FA'
DONE_ICON = '\U00002611'
TASK_ICON = '\U0001F4CB'
STATUS_ICON = '\U0001F4DD'
HI_PRIORITY_ICON = '\U0001F534'
MED_PRIORITY_ICON = '\U0001F535'
LOW_PRIORITY_ICON = '\U000026AA'
PRIORITY = {
    'high':'\U0001F534',
    'medium':'\U0001F535',
    'low':'\U000026AA'
}