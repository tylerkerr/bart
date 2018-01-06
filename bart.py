from flask import Flask
from flask import request
from requests import post
from slackclient import SlackClient
from datetime import datetime
import re
import os
import json

app = Flask(__name__)


@app.route('/bart', methods=['POST'])
def bartapp():
    if request.form.get('token', None) != os.environ.get('SLACK_SECRET'):
        return 'what are you talking about'  # if we get a POST that's not from the real slack
    slashcommand = request.form.get('command', None)
    channel = request.form.get('channel_name', None)
    srcuid = request.form.get('user_id', None)
    srcname = request.form.get('user_name', None)
    text = request.form.get('text', None)

    cmdlog = '#{} @{} {} {}'.format(channel, srcname, slashcommand, text)
    writelog(cmdlog)  # log all incoming commands

    if text.lower() == 'balance':
        return 'You have {} points!'.format(getbalance(srcuid))

    if text.lower() == 'leaderboard' or text.lower() == 'scoreboard' or text.lower() == 'score':
        return leaderboard()

    try:  # at least one of these should fail if it's not valid syntax
        command = text.split(' ')
        if len(command) > 2:  # if we think there's a description
            description = ' '.join(command[2:])
            description = '"_' + description + '_"'
        targetname = command[0]
        targetuid = getuid(targetname)
        if command[1][0] == '+':
            command[1] = command[1][1:]
        amount = int(command[1])
        if amount == 0:
            return "can't bart zero!"
        if targetuid == srcuid:
            return "can't bart yourself!"
    except:
        return 'syntax: bart user ±amount [optional desc] || bart balance || bart score'

    if amount == 1 or amount == -1:
        amountword = 'point'
    else:
        amountword = 'points'

    transferisvalid = validatetransfer(srcuid, targetuid, amount)  # can the user afford it?
    if transferisvalid:
        srcprebalance = getbalance(srcuid)
        targetprebalance = getbalance(targetuid)
        if amount > 0:
            value = amount * givemult  # inflation on positive barts to prevent currency exhaustion
            if value == 1:
                valueword = 'point'
            else:
                valueword = 'points'
            updatebalance(targetuid, value)
            updatebalance(srcuid, amount * -1)
            msg = "👼 <@{}> [{}] has spent {} {} to give <@{}> [{}] {} {}!"\
                .format(srcuid, getbalance(srcuid), amount, amountword, targetuid,
                        getbalance(targetuid), value, valueword)

        elif amount < 0:
            value = amount * takemult  # maybe later the multipliers will flux
            updatebalance(targetuid, value)
            updatebalance(srcuid, amount)
            msg = "😈 <@{}> [{}] has spent {} {} to delete {} of <@{}>'s [{}] points!"\
                .format(srcuid, getbalance(srcuid), abs(amount), amountword, abs(value),
                        targetuid, getbalance(targetuid))
    else:
        return 'not enough bort!'

    sendlog = '{} [{} -> {}] > {} [{} -> {}]'\
        .format(srcname, srcprebalance, getbalance(srcuid), targetname,
                targetprebalance, getbalance(targetuid))
    writelog(sendlog)  # log all successful transactions
    chat(msg)
    try:
        chat(description)
    except:
        pass

    usermsg = '[{} -> {}]'.format(srcprebalance, getbalance(srcuid))  # ephemeral message with balance change
    return usermsg


def getbalance(uid: str):
    uidfile = os.path.join(bartdb, uid)
    if not os.path.isfile(uidfile):
        makeuser(uid)
    with open(uidfile, 'r') as uf:
        balance = int(uf.read())
    return balance


def writelog(logline: str):
    logfile = os.path.join(bartdb, 'ledger.log')
    writeline = datetime.now().isoformat() + ' ' + str(logline) + '\n'
    with open(logfile, 'a') as lf:
        lf.write(writeline)


def validatetransfer(fromuid: str, touid: str, amount: int):
    frombalance = getbalance(fromuid)
    tobalance = getbalance(touid)
    if amount > 0:
        if frombalance >= amount:
            return True
        else:
            return False
    elif amount < 0:
        if frombalance >= abs(amount) and tobalance >= abs(amount):
            return True
        else:
            return False


def updatebalance(uid: str, amount: int):
    uidfile = os.path.join(bartdb, uid)
    newbalance = getbalance(uid) + amount
    with open(uidfile, 'w') as uf:
        uf.write(str(newbalance))


def makeuser(uid: str):
    print('making user', uid)
    uidfile = os.path.join(bartdb, uid)
    with open(uidfile, 'w') as uf:
        uf.write(str(startingbalance))


def chat(text: str):
    chaturl = 'https://hooks.slack.com/services/T0DCWQSBV/B8MRQ1JKU/' + os.environ.get('SLACK_URL')
    payload = {"text": text, "response_type": "in_channel"}
    post(chaturl, json=payload)


def leaderboard():
    balances = [(name, getbalance(getuid(name))) for name in usermap]
    scores = ''
    for bal in sorted(balances, key=lambda x: x[1], reverse=True):  # sort em
        scores += bal[0] + ': ' + str(bal[1]) + '\n'
    return scores


def remapusers():
    slack_client = SlackClient(os.environ.get('SLACK_API_TOKEN'))
    members = slack_client.api_call("users.list")['members']
    global usermap
    usermap = {}
    for memb in members:
        if memb['is_bot'] is False and memb['name'] != 'slackbot':  # slack doesn't purge deleted bots
            usermap[memb['name']] = memb['id']
    usermapfile = os.path.join(bartdb, 'usermap.json')
    with open(usermapfile, 'w') as um:
        json.dump(usermap, um, ensure_ascii=False)


def getuid(name):  # people can change their display names, so we want a static, unique ID to store balances
    cleanname = re.sub('@', '', name)  # so people can 'bart person' or 'bart @person' for autocomplete
    if cleanname in usermap:
        return usermap[cleanname]
    else:  # if they're not in the list, make a new API query
        print('remap')
        remapusers()
    if cleanname in usermap:  # then try again
        return usermap[cleanname]
    else:  # and if they're still not in the list, error out and trigger the syntax help message
        print('no such user:', name)
        raise ValueError('no such user')


def init():
    global bartdb
    bartdb = os.path.join(os.getcwd(), 'bartdb')
    if not os.path.isdir(bartdb):
        os.mkdir(bartdb)

    global usermap
    usermapfile = os.path.join(bartdb, 'usermap.json')
    if not os.path.isfile(usermapfile):
        remapusers()
    else:
        with open(usermapfile, 'r') as um:
            usermap = json.load(um)

    global startingbalance
    startingbalance = 128  # can't help it
    global givemult
    givemult = 10  # i think this is how stackexchange works
    global takemult
    takemult = 1  # TODO: something that causes this to change daily


def main():
    init()
    app.run(host='127.0.0.1', port=4999, debug=False)


if __name__ == '__main__':
    main()
