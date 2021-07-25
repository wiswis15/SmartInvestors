#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import polling2
import requests
import time

from seleniumwire import webdriver as webdriver_wire
from selenium import webdriver as webdriver_standard
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
import sys
import datetime
from loglib import logger as log 


# {{{ get_position_by_id

def get_position_by_id(positions, pos_id, id_field):
    pos_id = int(pos_id)
    return next((pos for pos in positions if int(pos[id_field]) == pos_id),
                None)

# }}}
# {{{ handle_selenium_exn

def take_selenium_screenshot(driver, context):
    directory = 'selenium-screenshots'
    if not os.path.exists(directory):
        os.makedirs(directory)
    path = '{0}/{1}-{2}.png'
    path = path.format(directory, int(time.time()), context.replace(' ', '_'))
    driver.save_screenshot(path)

def handle_selenium_exn(context):

    def decorator(func):

        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except NoSuchElementException as e:
                # There was a selenium exception, take a screenshot to help
                # debugging
                etoro = args[0]
                take_selenium_screenshot(etoro.driver, context)

                # Rethrow
                raise RuntimeError('cannot %s: %s' % (context, str(e)))

        return wrapper

    return decorator

# }}}

class Etoro:

    ''' Dict of instrument name by id.
        For example, instruments_by_id[1] -> EUR/USD
    '''
    instruments_by_id = None

    ''' Initialize an Etoro connection handle.

        If login/password are not provided, only public requests will work.
    '''
    def __init__(self, login=None, password=None):
        if login:
            # Authenticate
            assert(password)
            self.login = login
            self.password = password
            self.auth()
        else:
            # Create an empty non-authenticated python requests session
            self.session = requests.Session()

            #added by wissem
            self.driver =  self.__open_driver(webdriver_wire)

    def __del__(self):
        if getattr(self, 'driver', None):
            self.driver.quit()


    # {{{ Authenticate

    ''' Authenticate or re-authenticate with a login/password on eToro.

        For this purpose, we use selenium to fill the web login form.
        Once logged-in, the headers (and cookies) used by selenium are taken
        and placed in a python requests session, that will be used afterwards
        to make eToro authenticated requests.

        Actually, seleniumwire is used to capture a request and get the
        headers.

        This, for now, does not support 2FA.
    '''
    def auth(self):
        # First close a potential current session
        if getattr(self, 'driver', None):
            self.driver.quit()
        self.driver = None

        if getattr(self, 'session', None):
            self.session.post('https://www.etoro.com/api/sts/v2/logout/')
        self.session = requests.Session()

        # Create chrome headless selenium driver
        driver =  self.__open_driver(webdriver_wire)

        # Set a selenium-wire scope to capture an authenticated request
        driver.scopes = [ '.*www.etoro.com.*/instruments/private/index.*' ]

        # Authenticate with selenium-wire
        self.__login(driver)

        # There should be at least one request captured; no need to capture
        # anything else
        assert driver.requests
        req = driver.requests[0]

        # Create a python requests session with the headers and params (for
        # the client_request_id) of the captured request
        self.session.headers = { key: req.headers[key] for key in [
            'Host',
            'Authorization',
            'User-Agent',
            'X-CSRF-TOKEN',
            'ApplicationIdentifier',
            'ApplicationVersion',
            'Origin',
            'Sec-Fetch-Site',
            'Sec-Fetch-Mode',
            'Referer',
            'Cookie',
        ]}
        self.session.params = req.params

        # Close the selenium-wire session. A standard session will be opened
        # lazily later if needed. Do not keep the selenium-wire one because it
        # is slow, and triggers exceptions regularly
        driver.quit()

    @staticmethod
    def __open_driver(webdriver):
        # Create chrome headless selenium driver
        # Force the user agent and other options so that it is not detected
        # as a bot by cloudflare
        options = ChromeOptions()
        options.headless = True
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent='
                             'Mozilla/5.0 (X11; Linux x86_64) '
                             'AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/86.0.4240.111 '
                             'Safari/537.36')
        options.add_experimental_option('excludeSwitches',
                                        ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        if webdriver == webdriver_wire:
            # XXX: change the selenium-wire backend because it seems that the
            #      default one is detected by cloudflare...
            wire_options = {
                'backend': 'mitmproxy'
            }
            driver = webdriver.Chrome(chrome_options=options,
                                      seleniumwire_options=wire_options)
        else:
            driver = webdriver.Chrome(chrome_options=options)

        driver.implicitly_wait(10)

        return driver

    def __ensure_driver_opened(self):
        if not self.driver:
            self.driver = self.__open_driver(webdriver_standard)
            self.__login(self.driver)

    @handle_selenium_exn('login on etoro')
    def __login(self, driver):
        logging.info('logging to eToro as user `%s`...', self.login)
        start_time = time.time()

        url = 'https://www.etoro.com/portfolio'
        driver.get(url)
        assert driver.current_url == 'https://www.etoro.com/login'

        # Fill username
        username_input = driver.find_element_by_id("username")
        username_input.clear()
        username_input.send_keys(self.login)

        # Fill password and validate
        password_input = driver.find_element_by_id("password")
        password_input.clear()
        password_input.send_keys(self.password)

        # Validate form
        password_input.send_keys(Keys.RETURN)

        # Wait for the portfolio page to be loaded
        polling2.poll(lambda: driver.current_url == url, step=0.1, timeout=20)
        driver.find_element_by_class_name('footer-unit-button-icon')
        logging.info('successfully logged-in in %s seconds',
                     int(time.time() - start_time))

    # }}}
    # {{{ Make Etoro query

    ''' Make a query to Etoro, retrying and re-authenticating if needed.

    Queries to Etoro can fail because Etoro blocks when performing too many
    queries. This function retries the query when if fails, with an increasing
    delay between each try.
    '''
    def __make_etoro_query(self, url, params=None):
        retry_policy = [2, 5]
        r = self.session.get(url, params=params)
        # First tries
        for retry_delay in retry_policy:
            r = self.session.get(url, params=params)
            if r.status_code == requests.codes.ok:
                return r
            time.sleep(retry_delay)

        # It failed, force a re-authenticate
        logging.error('request `%s` still fails after %s tries, '
                      'reconnect: %s', r.url, len(retry_policy), r.text)
        self.auth()

        # And retry
        for retry_delay in retry_policy:
            r = self.session.get(url, params=params)
            if r.status_code == requests.codes.ok:
                return r
            time.sleep(retry_delay)

        logging.error('request `%s` still fails after %s tries and a '
                      'reconnection: %s', r.url, len(retry_policy), r.text)
        r.raise_for_status()
        return r # unreachable

    # }}}
    # {{{ Get instrument name by id (public request)

    def __build_instruments_cache(self):
        url = ('https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/'
               'instruments')
        r = requests.get(url)

        instruments = r.json()['InstrumentDisplayDatas']

        self.instruments_by_id = {
            i['InstrumentID']: {
                'name': i['InstrumentDisplayName'],
                'symbol': i['SymbolFull'],
            } for i in instruments
        }

        logging.info('%s instruments loaded in cache',
                     len(self.instruments_by_id))

    def __instrument_field_from_id(self, instrument_id, field):
        if self.instruments_by_id is None:
            self.__build_instruments_cache()
        try:
            return self.instruments_by_id[instrument_id][field]
        except KeyError:
            return '<unknown>'

    def instrument_name_from_id(self, instrument_id):
        return self.__instrument_field_from_id(instrument_id, 'name')

    def instrument_symbol_from_id(self, instrument_id):
        return self.__instrument_field_from_id(instrument_id, 'symbol')

    # }}}
    # {{{ Get trader CID (public request)

    @staticmethod
    def get_trader_cid(trader_login):
        url = 'https://www.etoro.com/api/logininfo/v1.1/users/{0}'
        r = requests.get(url.format(trader_login))
        res = r.json()['realCID']
        logging.info('fetched trader CID for `%s`: %s', trader_login, res)
        return res

    # }}}
    # {{{ Get realtime information about an instrument

    ''' Get information about an instrument:
         - is the master open?
         - general price
         - buy price, if available
         - sell price, if available

      It uses selenium (which is slow and not really reliable) in best effort
      as it seems the only API to get these informations is lightstreamer,
      with no proper python SDK.
    '''
    @handle_selenium_exn('get instrument realtime information')
    def get_instrument_realtime_info(self, instrument_id):
        self.__ensure_driver_opened()
        res = dict()

        # Browse to the instrument page on Etoro
        url = 'https://www.etoro.com/markets/{0}'
        url = url.format(self.instrument_symbol_from_id(instrument_id))
        self.driver.get(url)

        # Get market close or open
        self.__get_market_status(res)

        # Get the price HTML element
        self.__get_main_price(res)

        # If market is open, get buy and sell prices
        if not res['is_market_open']:
            return res

        # Open the trade dialog
        self.__open_trade_dialog()

        # Get the buy price
        price_xpath = ("//span[contains(@class,"
                       "'execution-main-head-price-value')]")
        self.__get_buy_price(res, price_xpath)

        # Get the sell price?
        self.__get_sell_price(res, price_xpath)

        return res

    @handle_selenium_exn('get market status')
    def __get_market_status(self, res):
        market_class = 'market-clock-icon'
        market = self.driver.find_element_by_class_name(market_class)
        res['is_market_open'] = 'market-open' in market.get_attribute('class')

    @handle_selenium_exn('get main price')
    def __get_main_price(self, res):
        price_class = 'head-info-stats-value'
        price = self.driver.find_element_by_class_name(price_class)
        try:
            res['price'] = float(price.text)
        except ValueError as e:
            take_selenium_screenshot(self.driver, 'parse main price')
            raise RuntimeError('cannot parse main price: %s' % str(e))

    @handle_selenium_exn('open trade dialog')
    def __open_trade_dialog(self):
        xpath = "//div[@automation-id='trade-button']"
        trade_button = self.driver.find_element_by_xpath(xpath)
        trade_button.click()

    @handle_selenium_exn('get buy price')
    def __get_buy_price(self, res, price_xpath):
        buy_price = self.driver.find_element_by_xpath(price_xpath)
        try:
            res['buy_price'] = float(buy_price.text)
        except ValueError as e:
            take_selenium_screenshot(self.driver, 'parse buy price')
            raise RuntimeError('cannot parse buy price: %s' % str(e))

    @handle_selenium_exn('get sell price')
    def __get_sell_price(self, res, price_xpath):
        self.driver.implicitly_wait(0)
        try:
            xpath = ("//button[@data-etoro-automation-id="
                     "'execution-sell-button']")
            sell_button = self.driver.find_element_by_xpath(xpath)
        except NoSuchElementException:
            sell_button = None
        finally:
            self.driver.implicitly_wait(10)
        if sell_button:
            sell_button.click()
            sell_price = self.driver.find_element_by_xpath(price_xpath)
            res['sell_price'] = float(sell_price.text)

    # }}}
    # {{{ Open position

    def __get_last_position(self, instrument_id, account_type):
        pos = self.get_own_all_current_positions(account_type)
        pos = [p for p in pos if p['InstrumentID'] == instrument_id]
        pos.sort(key=lambda pos: pos['PositionID'], reverse=True)
        return pos[0]['PositionID'] if pos else None

    def __open_position(self, what, instrument_id, is_buy, price, leverage,
                        amount, stop_loss, take_profit, is_tsl_enabled,
                        prev_pos, account_type):
        # Make position open query
        url = 'https://www.etoro.com/sapi/trade-{0}/positions'
        url = url.format(account_type.lower())

        headers = {
            'AccountType': account_type,
        }
        params = {
            'InstrumentID': instrument_id,
            'IsBuy': is_buy,
            'Leverage': leverage,
            'Amount': amount,
            'StopLossRate': stop_loss,
            'TakeProfitRate': take_profit,
            'IsTslEnabled': is_tsl_enabled,
            'ViewRateContext': {
                'ClientViewRate': price,
            },
        }
        r = self.session.post(url, json=params, headers=headers)

        if r.status_code != requests.codes.ok:
            logging.error('cannot open %s: %s', what, r.text)
        r.raise_for_status()

        # Now we need to guess what is the opened position, to return its id
        def get_new_position():
            new_pos = self.__get_last_position(instrument_id, account_type)
            if not new_pos or new_pos == prev_pos:
                return None
            return new_pos
        try:
            new_pos = polling2.poll(get_new_position, step=2, timeout=30)
        except polling2.PollingException:
            msg = 'cannot open %s: no new position found after query' % what
            raise RuntimeError(msg)

        logging.info('opened %s: id %s', what, new_pos)
        return new_pos

    def open_position(self, instrument_id, is_buy, leverage, amount,
                      stop_loss, take_profit, is_tsl_enabled,
                      account_type='Demo', price=None):
        instrument_name = self.instrument_name_from_id(instrument_id)
        what = '{0} position on {1} with ${2}, leverage x{3}'
        what = what.format('buy' if is_buy else 'sell',
                           instrument_name, amount, leverage)

        # Get our last opened position on this instrument, to be able to guess
        # which one we'll open
        prev_pos = self.__get_last_position(instrument_id, account_type)

        # First try at the wanted price, if provided
        if price:
            try:
                return self.__open_position(what, instrument_id, is_buy,
                                            price, leverage, amount,
                                            stop_loss, take_profit,
                                            is_tsl_enabled, prev_pos,
                                            account_type)
            except (requests.exceptions.RequestException, RuntimeError):
                logging.warning('opening %s at given price $%s failed, retry '
                                'by getting the current price', what, price)

        # Get instrument information, to know if the market is open and get
        # the price
        instrument_info = self.get_instrument_realtime_info(instrument_id)
        if not instrument_info['is_market_open']:
            raise RuntimeError('market is closed for', instrument_name)

        price = 'buy_price' if is_buy else 'sell_price'
        price = instrument_info.get(price, None)
        if price is None:
            raise RuntimeError('no {0} price for {1}'.format(
                'buy' if is_buy else 'sell',
                instrument_name,
            ))

        return self.__open_position(what, instrument_id, is_buy, price,
                                    leverage, amount, stop_loss, take_profit,
                                    is_tsl_enabled, prev_pos, account_type)

    # }}}
    # {{{ Close position

    def close_position(self, instrument_id, position_id, account_type='Demo'):
        url = 'https://www.etoro.com/sapi/trade-{0}/positions/{1}'
        url = url.format(account_type.lower(), position_id)

        headers = {
            'AccountType': account_type,
        }
        params = {
            'PositionID': position_id,
        }
        r = self.session.delete(url, params=params, headers=headers, json={})

        if r.status_code != requests.codes.ok:
            logging.error('cannot close position %s on %s: %s',
                          position_id,
                          self.instrument_name_from_id(instrument_id), r.text)
        r.raise_for_status()

        logging.info('position %s on %s closed',
                     position_id,
                     self.instrument_name_from_id(instrument_id))

    # }}}
    # {{{ Edit position

    def edit_position(self, instrument_id, position_id, stop_loss,
                      take_profit, account_type='Demo'):
        what = 'position {0} on {1}'
        what = what.format(position_id,
                           self.instrument_name_from_id(instrument_id))

        # First get current version of the position
        def get_position():
            positions = self.get_own_all_current_positions(account_type)
            pos = get_position_by_id(positions, position_id, 'PositionID')
            if not pos:
                raise RuntimeError('position %s not found in portfolio' %
                                   position_id)
            return pos
        prev_pos = get_position()
        if prev_pos['StopLossRate'] == stop_loss and \
           prev_pos['TakeProfitRate'] == take_profit:
            logging.info('%s not modified: nothing to do', what)
            return

        # Make position edit query
        url = 'https://www.etoro.com/sapi/trade-{0}/positions/{1}'
        url = url.format(account_type.lower(), position_id)

        headers = {
            'AccountType': account_type,
        }
        params = {
            'PositionID': position_id,
            'StopLossRate': stop_loss,
            'TakeProfitRate': take_profit,
        }
        r = self.session.put(url, json=params, headers=headers)

        if r.status_code != requests.codes.ok:
            logging.error('cannot edit %s: %s', what, r.text)
        r.raise_for_status()

        # Check it worked; wait until the position is modified, whatever what.
        # It could have worked for stop loass and not take profit, or the
        # opposite. At the moment, do not check for details.
        try:
            polling2.poll(lambda: get_position() != prev_pos,
                          step=2, timeout=30)
        except polling2.PollingException:
            msg = 'cannot %s: the position did not change after query' % what
            raise RuntimeError(msg)

        logging.info('%s modified: stop loss $%s, take profit $%s',
                     what, stop_loss, take_profit)

    # }}}
    # {{{ Get public portfolio positions of a trader

    ''' Get all the current positions for a given client ID, from aggregated
        positions.

    Returns an array of elements like that:
    {
        "Amount": 4.54822482784969,  # Amount in % of total portfolio
        "CID": 13735765,             # Client ID
        "CurrentRate": 12.21,        # Current value of the instrument
        "InstrumentID": 5664,
        "IsBuy": true,
        "IsTslEnabled": false,
        "Leverage": 5,
        "MirrorID": 0,
        "NetProfit": 315.0867815,    # Profit (or loss) in %
        "OpenDateTime": "2020-09-21T13:48:30.7970000Z",
        "OpenRate": 7.49,            # Value of the instrument at position open
        "ParentPositionID": 0,
        "PipDifference": 472.0,
        "PositionID": 735837152,
        "StopLossRate": 9.1,
        "TakeProfitRate": 35.0
    }
    '''
    def get_trader_all_current_positions(self, cid, aggregated_positions):
        url = ('https://www.etoro.com/sapi/trade-data-real/live/public'
               '/positions')
        all_positions = []

        for aggregated in aggregated_positions:
            params = {
                'format': 'json',
                'cid': cid,
                'InstrumentID': aggregated['InstrumentID'],
            }
            r = self.__make_etoro_query(url, params=params)
            all_positions += r.json()['PublicPositions']

        return all_positions


    ''' Get aggregated positions for a given client ID.

    Returns an array of elements like that:
    {
        "Direction": "Buy",
        "InstrumentID": 5820,
        "Invested": 1.9543,
        "NetProfit": 9.3755,
        "Value": 2.0504311053322777
    }
    '''
    def get_trader_aggregated_positions(self, cid):
        url = ('https://www.etoro.com/sapi/trade-data-real/live/public'
               '/portfolios')
        params = {
            'format': 'json',
            'cid': cid,
        }
        r = self.__make_etoro_query(url, params=params)
        return r.json()['AggregatedPositions']

    # }}}
    # {{{ Get own portfolio positions

    ''' Get all the current positions of our portfolio.

    Returns an array of elements like that:
    {
        "Amount": 252.0,
        "CID": 15276631,
        "InitialAmountInDollars": 252.0,
        "InitialUnits": 8.205796,
        "InstrumentID": 4489,
        "IsBuy": true,
        "IsDiscounted": true,
        "IsPartiallyAltered": false,
        "IsSettled": true,
        "IsTslEnabled": true,
        "Leverage": 1,
        "MirrorID": 0,
        "OpenDateTime": "2020-10-10T17:01:32.39Z",
        "OpenRate": 30.71,
        "OrderID": 0,
        "ParentPositionID": 0,
        "PositionID": 1111111111,
        "RedeemStatusID": 0,
        "StopLossRate": 23.23,
        "StopLossVersion": 1,
        "TakeProfitRate": 61.42,
        "TotalFees": 0.0,
        "Units": 8.205796,
        "UnitsBaseValueDollars": 252.0
    }
    '''
    def get_own_all_current_positions(self, account_type='Demo'):
        url = 'https://www.etoro.com/api/logininfo/v1.1/logindata'
        params = {
            'conditionIncludeDisplayableInstruments': False,
            'conditionIncludeMarkets': False,
            'conditionIncludeMetadata': False,
            'conditionIncludeMirrorValidation': False,
        }
        headers = {
            'AccountType': account_type,
        }
        r = self.session.get(url, params=params, headers=headers)

        if r.status_code != requests.codes.ok:
            logging.error('cannot get own positions: %s', r.text)
        r.raise_for_status()

        res = r.json()
        # res if of type list
        res = res['AggregatedResult']['ApiResponses']['PrivatePortfolio'] \
                ['Content']['ClientPortfolio']['Positions']
        

        return res

    # }}}


# {{{ Get own portfolio positions

    ''' Get all the current positions of instrumentid and portfolio with cid 

    Returns an array of elements like that:
    {
        "Amount": 252.0,
        "CID": 15276631,
        "InitialAmountInDollars": 252.0,
        "InitialUnits": 8.205796,
        "InstrumentID": 4489,
        "IsBuy": true,
        "IsDiscounted": true,
        "IsPartiallyAltered": false,
        "IsSettled": true,
        "IsTslEnabled": true,
        "Leverage": 1,
        "MirrorID": 0,
        "OpenDateTime": "2020-10-10T17:01:32.39Z",
        "OpenRate": 30.71,
        "OrderID": 0,
        "ParentPositionID": 0,
        "PositionID": 1111111111,
        "RedeemStatusID": 0,
        "StopLossRate": 23.23,
        "StopLossVersion": 1,
        "TakeProfitRate": 61.42,
        "TotalFees": 0.0,
        "Units": 8.205796,
        "UnitsBaseValueDollars": 252.0
    }
    '''
    def get_all_current_positions(self, cid,instrumentid,account_type='Demo'):
        url = 'https://www.etoro.com/sapi/trade-data-real/live/public/positions?InstrumentID={}&cid={}&format=json'.format(instrumentid,cid)
        params = {
            'conditionIncludeDisplayableInstruments': False,
            'conditionIncludeMarkets': False,
            'conditionIncludeMetadata': False,
            'conditionIncludeMirrorValidation': False
        }
        headers = {
            'AccountType': account_type,
        }
        #r = self.session.get(url, params=params, headers=headers)
        r = self.session.get(url)

        if r.status_code != requests.codes.ok:
            logging.error('cannot get  positions: %s', r.text)
        r.raise_for_status()

        res = r.json()
        # res if of type list
        res = res['PublicPositions']

        return res

    # }}}

    def get_closed_positions(self, cid,account_type='Demo'):
        initialTime="2021-01-10T23:00:00.000Z"
        startDate=datetime.datetime.now()-datetime.timedelta(days=7)
        newDate=startDate.strftime("%Y-%m-%d, %H:%M:%S")[0:10] #shall give someting like 2021-02-03
        initialTime.replace("2021-01-10",newDate)
        url = 'https://www.etoro.com/sapi/trade-data-real/history/public/credit/flat?CID={}&ItemsPerPage=30&PageNumber=1&StartTime={}&format=json'.format(cid,initialTime)
        params = {
            'conditionIncludeDisplayableInstruments': False,
            'conditionIncludeMarkets': False,
            'conditionIncludeMetadata': False,
            'conditionIncludeMirrorValidation': False
        }
        headers = {
            'AccountType': account_type,
        }
        r = self.session.get(url,params=params,headers=headers)
        #try with no login
        

        if r.status_code != requests.codes.ok:
            logging.error('Error in get_closed_positions(): %s', r.text)
            time.sleep(2)
        r.raise_for_status()

        res = r.json()
        # res if of type list
        res = res['PublicHistoryPositions']

        return res

    # }}}

    def GetProfilePicture(self,profile):
        try:
            """
            Get profile picture from etoro
            """
            link="https://www.etoro.com/people/{}".format(profile)#https://www.etoro.com/people/beatrice7972
            self.driver.get(link)
            avatar=self.driver.find_element_by_xpath("//img[@automation-id='user-head-add-photo-button']")
            path= avatar.get_attribute('src')
            return path
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in GetProfilePicture:{} {} {} {} profile= {}".format(exc_type, fname, exc_tb.tb_lineno,ex,profile))



