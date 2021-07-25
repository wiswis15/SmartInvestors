#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import coloredlogs
import getpass
import logging
import os
import requests
import schedule
import tarfile
import time
import traceback

from libs.etoro import (
    get_position_by_id,
    Etoro,
)

from datetime import date
from filelock import FileLock
from slack import WebClient as SlackWebClient
from slack.errors import SlackApiError
from tinydb import TinyDB, Query


# {{{ Globals

''' Database '''
DB = None
TRADERS_TABLE = None

''' List of traders to watch.

Each entry is a dict with the following fields:
    * login: trader's login
    * cron_freq: frequency of the cron, in minutes
    * full_refresh_freq: frequency of full refresh, in minutes
    * do_copy: if true, the positions of this trader will be copied
    * copy_total_equity: mandatory if do_copy is true, amount in dollars;
                         used to compute the amount of each copied position
    * copy_account_type: etoro account type of the copy positions;
                         can be 'Demo' (default) or 'Real'.
'''
TRADERS = [
    {
        'login': 'rapidstock',
        'cron_freq': 1,
        'full_refresh_freq': 3600 * 24,
        #'do_copy': True,
        #'copy_total_equity': 10000,
        #'copy_account_type': 'Real',
    },
]

''' Token of the slack application '''
SLACK_TOKEN = 'xoxb-XXXXXXXXXXXXX-XXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXX'

''' Slack client handle '''
SLACK_CLIENT = SlackWebClient(token=SLACK_TOKEN)

''' Etoro connection handle '''
ETORO = None

# }}}

# {{{ Slack

def slack_get_channel_id(name):
    channels_cache = getattr(slack_get_channel_id, 'channels', dict())

    channel = channels_cache.get(name, None)
    if channel:
        return channel

    channels = SLACK_CLIENT.conversations_list(types="public_channel")
    for channel in channels['channels']:
        if channel['name'] == name:
            channels_cache[name] = channel['id']
            slack_get_channel_id.channels = channels_cache
            return channel['id']

    raise RuntimeError('cannot get slack channel %s' % name)

def slack_send_message(channel, text):
    try:
        SLACK_CLIENT.chat_postMessage(
            channel=channel,
            text=text,
        )
    except SlackApiError as e:
        logging.error('cannot send message `%s` message to slack: %s',
                      text, str(e))

def slack_send_trader_message(trader, text):
    slack_send_message(trader['slack_channel_id'], text)

def slack_send_general_message(text):
    slack_send_message(slack_get_channel_id('general'), text)

def slack_send_maintenance_needed():
    last_warn = getattr(slack_send_maintenance_needed, 'last_warn', 0)
    if last_warn + 3600 < time.time():
        slack_send_general_message(':warning: maintenance needed!')
        slack_send_maintenance_needed.last_warn = time.time()

# }}}
# {{{ on_position_open

def on_position_open(trader_conf, trader_obj, pos):
    copy_total_equity = trader_conf.get('copy_total_equity', 0)
    copy_amount = int(copy_total_equity * pos['Amount'] / 100.)
    do_copy = trader_conf.get('do_copy', False)
    data = {
        'trader': trader_conf['login'],
        'id': pos['PositionID'],
        'direction': 'buy' if pos['IsBuy'] else 'sell',
        'instrument': ETORO.instrument_name_from_id(pos['InstrumentID']),
        'instrument_id': pos['InstrumentID'],
        'amount': pos['Amount'],
        'leverage': pos['Leverage'],
        'open_rate': pos['OpenRate'],
        'stop_loss': pos['StopLossRate'],
        'take_profit': pos['TakeProfitRate'],
        'copy_msg': '',
    }

    # Emit log
    log = ('`{trader}`: new {direction} position {id} on '
           '`{instrument}` (id {instrument_id})')
    logging.info('%s', log.format(**data))

    # Copy position?
    if do_copy:
        copied_positions = trader_obj.get('copied_positions', [])
        copy_pos = get_position_by_id(copied_positions, pos['PositionID'],
                                      'original_id')
        if copy_pos:
            logging.info('position already copied with id %s',
                         copy_pos['copy_id'])
            msg = '\nPosition already copied with id {0}.'
            data['copy_msg'] = msg.format(copy_pos['copy_id'])
        else:
            try:
                # Open copy position
                copy_id = ETORO.open_position(
                    instrument_id=pos['InstrumentID'],
                    is_buy=pos['IsBuy'],
                    leverage=pos['Leverage'],
                    amount=copy_amount,
                    stop_loss=pos['StopLossRate'],
                    take_profit=pos['TakeProfitRate'],
                    is_tsl_enabled=False,
                    account_type=trader_conf.get('copy_account_type', 'Demo'),
                    price=pos['OpenRate'],
                )

                msg = '\nCopied as position `{0}` with ${1}.'
                data['copy_msg'] = msg.format(copy_id, copy_amount)

                # Update database
                copied_positions.append({
                    'instrument_id': pos['InstrumentID'],
                    'original_id': pos['PositionID'],
                    'copy_id': copy_id,
                })
                TRADERS_TABLE.update({'copied_positions': copied_positions},
                                     Query().login == trader_conf['login'])

            except requests.exceptions.RequestException:
                msg = '\n:warning: Failed to open copy position with ${0}!'
                data['copy_msg'] = msg.format(copy_amount)
            except RuntimeError as e:
                msg = ('\n:warning: Failed to open copy position with ${0}: '
                       '{1}')
                data['copy_msg'] = msg.format(copy_amount, str(e))

    elif copy_amount > 0:
        msg = '\nSuggested copy amount: ${0}.'
        data['copy_msg'] = msg.format(copy_amount)

    # Notify on slack
    msg = (':new: New {direction} position on `{instrument}` '
           '(id {instrument_id}) with {amount:.02f}% of equity.\n'
           'Id `{id}`.\n'
           'Leverage x{leverage}.\n'
           'Opened at ${open_rate}.\n'
           'Stop loss: ${stop_loss}.\n'
           'Take profit: ${take_profit}.'
           '{copy_msg}')
    slack_send_trader_message(trader_obj, msg.format(**data))

# }}}
# {{{ on_position_close

def on_position_close(trader_conf, trader_obj, pos):
    data = {
        'trader': trader_conf['login'],
        'id': pos['PositionID'],
        'direction': 'buy' if pos['IsBuy'] else 'sell',
        'instrument': ETORO.instrument_name_from_id(pos['InstrumentID']),
        'instrument_id': pos['InstrumentID'],
        'amount': pos['Amount'],
        'leverage': pos['Leverage'],
        'open_rate': pos['OpenRate'],
        'copy_msg': '',
    }

    # Emit log
    log = ('`{trader}`: closed {direction} position with id {id} on '
           '`{instrument}` (id {instrument_id})')
    logging.info('%s', log.format(**data))

    # Close potential copy position
    copied_positions = trader_obj.get('copied_positions', [])
    copy_pos = get_position_by_id(copied_positions, pos['PositionID'],
                                  'original_id')
    if copy_pos:
        try:
            account_type = trader_conf.get('copy_account_type', 'Demo')
            ETORO.close_position(pos['InstrumentID'], copy_pos['copy_id'],
                                 account_type)
            msg = '\nAssociated copy position `{0}` closed.'
            data['copy_msg'] = msg.format(copy_pos['copy_id'])
            copied_positions.remove(copy_pos)
            TRADERS_TABLE.update({'copied_positions': copied_positions},
                                 Query().login == trader_conf['login'])
        except requests.exceptions.RequestException:
            msg = ('\n:warning: Failed to close associated copy position '
                   '`{0}`!')
            data['copy_msg'] = msg.format(copy_pos['copy_id'])
    elif trader_conf.get('do_copy', False):
        data['copy_msg'] = '\nNo associated copy position to close.'

    # Notify on slack
    msg = (':black_square_for_stop: Closed {direction} position on '
           '`{instrument}` (id {instrument_id}).\n'
           'Id `{id}`.\n'
           'Leverage x{leverage}.\n'
           'Opened at ${open_rate}.'
           '{copy_msg}')
    slack_send_trader_message(trader_obj, msg.format(**data))

# }}}
# {{{ on_position_modified

def on_position_modified(trader_conf, trader_obj, prev_pos, cur_pos):
    data = {
        'trader': trader_conf['login'],
        'id': cur_pos['PositionID'],
        'direction': 'buy' if cur_pos['IsBuy'] else 'sell',
        'instrument': ETORO.instrument_name_from_id(cur_pos['InstrumentID']),
        'instrument_id': cur_pos['InstrumentID'],
        'leverage': cur_pos['Leverage'],
        'open_rate': cur_pos['OpenRate'],
        'old_stop_loss': prev_pos['StopLossRate'],
        'old_take_profit': prev_pos['TakeProfitRate'],
        'new_stop_loss': cur_pos['StopLossRate'],
        'new_take_profit': cur_pos['TakeProfitRate'],
        'copy_msg': '',
    }

    # Emit log
    log = ('`{trader}`: modified {direction} position {id} on '
           '`{instrument}` (id {instrument_id})')
    logging.info('%s', log.format(**data))

    # Update potential copy position
    copied_positions = trader_obj.get('copied_positions', [])
    copy_pos = get_position_by_id(copied_positions, cur_pos['PositionID'],
                                  'original_id')
    if copy_pos:
        try:
            account_type = trader_conf.get('copy_account_type', 'Demo')
            ETORO.edit_position(instrument_id=cur_pos['InstrumentID'],
                                position_id=copy_pos['copy_id'],
                                stop_loss=cur_pos['StopLossRate'],
                                take_profit=cur_pos['TakeProfitRate'],
                                account_type=account_type)
            msg = '\nAssociated copy position `{0}` updated accordingly.'
            data['copy_msg'] = msg.format(copy_pos['copy_id'])
        except (requests.exceptions.RequestException, RuntimeError):
            msg = ('\n:warning: Failed to update associated copy position '
                   '`{0}`!')
            data['copy_msg'] = msg.format(copy_pos['copy_id'])
    elif trader_conf.get('do_copy', False):
        data['copy_msg'] = '\nNo associated copy position to update.'

    # Notify on slack
    msg = (':pencil2: Modified {direction} position on '
           '`{instrument}` (id {instrument_id}).\n'
           'Id `{id}`.\n'
           'Leverage x{leverage}.\n'
           'Opened at ${open_rate}.\n')
    if data['old_stop_loss'] != data['new_stop_loss']:
        msg += 'Stop loss: ${old_stop_loss} -> ${new_stop_loss}.\n'
    if data['old_take_profit'] != data['new_take_profit']:
        msg += 'Take profit: ${old_take_profit} -> ${new_take_profit}.\n'
    msg += '{copy_msg}'
    slack_send_trader_message(trader_obj, msg.format(**data))

# }}}
# {{{ close_copied_obsolete_positions

''' Close our positions that do not correspond to any current position of
    the trader.
    This should not happen, but do it just to be safe.
'''
def close_copied_obsolete_positions(trader_conf):
    trader_obj = TRADERS_TABLE.get(Query().login == trader_conf['login'])
    positions = trader_obj.get('positions', [])
    copied_positions = trader_obj.get('copied_positions', [])

    for pos in copied_positions:
        original_pos = get_position_by_id(positions, pos['original_id'],
                                          'PositionID')
        if original_pos:
            continue

        data = {
            'trader': trader_conf['login'],
            'original_id': pos['original_id'],
            'copy_id': pos['copy_id'],
            'instrument': ETORO.instrument_name_from_id(pos['instrument_id']),
            'instrument_id': pos['instrument_id'],
        }

        # Emit log
        log = ('`{trader}`: close copy position {copy_id} on `{instrument}` '
               '(id {instrument_id}) because the associated original '
               'position {original_id} does not exist anymore')
        logging.info('%s', log.format(**data))

        # Try to close position
        try:
            ETORO.close_position(pos['instrument_id'], pos['copy_id'])
            msg = (':black_square_for_stop: Closed copy position `{copy_id}` '
                   'on `{instrument}` (id {instrument_id}) because '
                   'associated original position `{original_id}` does not '
                   'exist anymore')
            copied_positions.remove(pos)
            TRADERS_TABLE.update({'copied_positions': copied_positions},
                                 Query().login == trader_conf['login'])

        except requests.exceptions.RequestException:
            msg = (':warning: Failed to close copy position `{copy_id}` '
                   'on `{instrument}` (id {instrument_id}), that we tried to '
                   'close because associated original position '
                   '`{original_id}` does not exist anymore!')

        finally:
            # Notify on slack
            slack_send_trader_message(trader_obj, msg.format(**data))


# }}}
# {{{ remove_copied_obsolete_positions

''' Remove from copied positions the positions that are not anymore in our
    portfolio.
'''
def remove_copied_obsolete_positions(trader_conf):
    if not trader_conf.get('do_copy', False):
        return

    try:
        account_type = trader_conf.get('copy_account_type', 'Demo')
        cur_positions = ETORO.get_own_all_current_positions(account_type)
    except requests.exceptions.RequestException:
        return

    trader_obj = TRADERS_TABLE.get(Query().login == trader_conf['login'])
    copied_positions = trader_obj.get('copied_positions', [])
    new_copied_positions = []

    for copy_pos in copied_positions:
        cur_pos = get_position_by_id(cur_positions, copy_pos['copy_id'],
                                     'PositionID')
        if cur_pos:
            new_copied_positions.append(copy_pos)
            continue

        data = {
            'trader': trader_conf['login'],
            'id': copy_pos['copy_id'],
            'instrument': ETORO.instrument_name_from_id(
                copy_pos['instrument_id']),
            'instrument_id': copy_pos['instrument_id'],
        }
        log = ('`{trader}`: remove copy position {id} on `{instrument}` '
               '(id {instrument_id}): manually closed?')
        logging.info('%s', log.format(**data))

    if len(new_copied_positions) != len(copied_positions):
        TRADERS_TABLE.update({'copied_positions': new_copied_positions},
                             Query().login == trader_conf['login'])

# }}}
# {{{ Detect position changes

''' Compares the current positions with the ones saved in database to detect
    changes. Returns the new, modified and closed positions as lists.
'''
def compare_positions(trader, cur_positions):
    new = []
    modified = []
    closed = []

    def pos_was_modified(prev_pos, cur_pos):
        return prev_pos['StopLossRate'] != cur_pos['StopLossRate'] \
            or prev_pos['TakeProfitRate'] != cur_pos['TakeProfitRate']

    # Detect modified or closed positions
    prev_positions = trader['positions']
    for prev_pos in prev_positions:
        cur_pos = get_position_by_id(cur_positions, prev_pos['PositionID'],
                                     'PositionID')
        if cur_pos is None:
            closed.append(prev_pos)
        elif pos_was_modified(prev_pos, cur_pos):
            modified.append((prev_pos, cur_pos))

    # Detect new positions
    for cur_pos in cur_positions:
        prev_pos = get_position_by_id(prev_positions, cur_pos['PositionID'],
                                      'PositionID')
        if prev_pos is None:
            new.append(cur_pos)

    return (new, modified, closed)

''' Checks if there were changes in the aggregated positions of a trader '''
def aggregated_positions_changed(trader, cur_aggr_pos):
    if not 'aggregated_positions' in trader:
        return True

    prev_aggr_pos = trader['aggregated_positions']

    if len(cur_aggr_pos) != len(prev_aggr_pos):
        return True

    for _, (prev_pos, cur_pos) in enumerate(zip(prev_aggr_pos, cur_aggr_pos)):
        if prev_pos['InstrumentID'] != cur_pos['InstrumentID'] or \
           prev_pos['Direction'] != cur_pos['Direction'] or \
           prev_pos['Invested'] != cur_pos['Invested']:
            return True

    return False

# }}}
# {{{ Trader cron

''' Main cron for a trader '''
def trader_cron(trader_conf):
    login = trader_conf['login']
    query = Query()
    trader_obj = TRADERS_TABLE.get(query.login == login)

    try:
        # Get aggregated positions
        aggr_pos = ETORO.get_trader_aggregated_positions(trader_obj['cid'])
        aggr_pos.sort(key=lambda pos: pos['InstrumentID'])

        # Check if we need to refresh the current positions
        full_refresh_freq = trader_conf['full_refresh_freq'] * 60
        do_positions_refresh = False
        last_positions_refresh = trader_obj.get('last_positions_refresh', 0)
        if last_positions_refresh < time.time() - full_refresh_freq:
            # Do it if the last refresh is "old" (mostly to detect SL/TP
            # changes)
            logging.info('`%s`: force refreshing all positions', login)
            do_positions_refresh = True
        elif aggregated_positions_changed(trader_obj, aggr_pos):
            # Or if aggregated positions changed
            logging.info('`%s`: refresh all positions because aggregated '
                         'positions changed', login)
            do_positions_refresh = True

        # Refresh positions?
        new = []
        modified = []
        closed = []
        if do_positions_refresh:
            start_time = time.time()
            cur_positions = ETORO.get_trader_all_current_positions(
                trader_obj['cid'],
                aggr_pos,
            )
            if last_positions_refresh > 0:
                (new, modified, closed) = compare_positions(trader_obj,
                                                            cur_positions)
            else:
                (new, modified, closed) = (cur_positions, [], [])
                msg = 'Initialized with {0} positions.'.format(len(new))
                slack_send_trader_message(trader_obj, msg)
            logging.info('`%s`: positions refreshed in %s seconds: %s new, '
                         '%s modified, %s closed, %s total',
                         trader_obj['login'],
                         int(time.time() - start_time),
                         len(new), len(modified), len(closed),
                         len(cur_positions))

    except requests.exceptions.RequestException as e:
        logging.error('`%s`: error when looking for changes: %s',
                      login, str(e))
        slack_send_maintenance_needed()
        return


    # Notify for position changes / replicate trades; do not do it at
    # initialization
    if last_positions_refresh > 0:
        for closed_pos in closed:
            on_position_close(trader_conf, trader_obj, closed_pos)
        for new_pos in new:
            on_position_open(trader_conf, trader_obj, new_pos)
        for (prev_pos, cur_pos) in modified:
            on_position_modified(trader_conf, trader_obj, prev_pos, cur_pos)

    # Update db
    TRADERS_TABLE.update({'aggregated_positions': aggr_pos},
                         query.login == login)
    if do_positions_refresh:
        TRADERS_TABLE.update({
            'positions': cur_positions,
            'last_positions_refresh': time.time(),
        }, query.login == login)

    if do_positions_refresh:
        # Remove from copied positions the positions that are not anymore in
        # our portfolio
        remove_copied_obsolete_positions(trader_conf)

        # Close our positions that do not correspond to any current position
        # of the trader
        close_copied_obsolete_positions(trader_conf)


''' Main cron for a trader, wrapper to catch exceptions '''
def trader_cron_wrapper(trader_conf):
    try:
        trader_cron(trader_conf)
    except Exception as e: # pylint: disable=broad-except
        slack_send_maintenance_needed()
        logging.error('`%s`: non-catched exception when running cron: %s.',
                      trader_conf['login'], repr(e))
        traceback.print_exc()

# }}}
# {{{ do_backup

def do_backup():
    today = date.today()
    today_str = today.strftime('%Y-%b-%d')

    backup_path = 'etoro-bot-backup-{0}.tar.gz'.format(today_str)

    with tarfile.open(backup_path, 'w:gz') as archive:
        archive.add('db.json')

    SLACK_CLIENT.files_upload(channels=slack_get_channel_id('general'),
                              title='Backup of {0}'.format(today_str),
                              file=backup_path)

    os.remove(backup_path)

# }}}
# {{{ main

def main():
    coloredlogs.install(level=logging.INFO,
                        fmt='%(asctime)s %(levelname)s {%(name)s}: '
                            '%(message)s')

    # Open etoro connection handle
    login = input('Etoro username: ')
    password = getpass.getpass(prompt='Etoro password: ')
    global ETORO
    ETORO = Etoro(login=login, password=password)

    # Open database
    global DB
    global TRADERS_TABLE
    lock = FileLock('db.json.lock', timeout=0)
    lock.acquire()
    DB = TinyDB('db.json')
    TRADERS_TABLE = DB.table('traders')

    # Loop on traders to watch
    for trader_conf in TRADERS:
        login = trader_conf['login']

        # Get trader CID if not already in database
        if TRADERS_TABLE.get(Query().login == login) is None:
            trader = {
                'login': login,
                'cid': ETORO.get_trader_cid(login),
                'slack_channel_id': slack_get_channel_id(login),
            }
            TRADERS_TABLE.insert(trader)

        # Register cron
        freq = trader_conf['cron_freq']
        schedule.every(freq).minutes.do(trader_cron_wrapper, trader_conf)

    # Register backup cron
    schedule.every().day.at('23:59').do(do_backup)

    # Schedule events
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        lock.release()

# }}}

if __name__ == '__main__':
    main()
