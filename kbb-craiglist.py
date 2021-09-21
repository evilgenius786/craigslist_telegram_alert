import datetime
import json
import os
import threading
import time
import traceback

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from strsimpy.normalized_levenshtein import Levenshtein
from telegram import InputMediaPhoto
from telegram.ext import Updater

t = 1
timeout = 10
monitor = 60
debug = True

headless = False
images = False
maximize = False

incognito = False
testing = True
craigslist = 'https://denver.craigslist.org/search/cto?max_price=15000&postal=80016&search_distance=250'
tkn = 'YourChannelToken'
chat_id = -1001598038923
updater = Updater(tkn, use_context=True)
levenshtein = Levenshtein()

lock = threading.Lock()


def main():
    logo()
    res = requests.get(craigslist).content
    soup = BeautifulSoup(res, 'lxml')
    cars = [li.find('a', {'class': "result-title hdrlnk"}).text for li in soup.find_all('li', {'class': 'result-row'})]
    print("Cars", cars)
    cars.pop(2)
    # cars.clear()
    while True:
        print(datetime.datetime.now(), f"Monitoring every {int(monitor / 60)} min...")
        for li in soup.find_all('li', {'class': 'result-row'}):
            info = [x.strip() for x in li.find('div', {'class': "result-info"}).text.split('\n') if x.strip()][1:-3]
            link = li.find('a', {'class': 'result-title hdrlnk'})['href']
            data = {
                'title': li.find('a', {'class': "result-title hdrlnk"}).text if li.find('a', {
                    'class': "result-title hdrlnk"}) is not None else "",
                'map': li.find('span', {'class': "maptag"}).text if li.find('span',
                                                                            {'class': "maptag"}) is not None else "",
                'time': li.find('time', {'class': "result-date"})['datetime'] if li.find('time', {
                    'class': "result-date"}) is not None else "",
                'loc': li.find('span', {'class': "result-hood"}).text[2:-1] if li.find('span', {
                    'class': "result-hood"}) is not None else "",
                'price': int(li.find('span', {'class': "result-price"}).text[1:].replace(',', '')) if li.find('span', {
                    'class': "result-price"}) is not None else "",
                'link': link
            }
            car = (" - ".join(info))
            if data['title'] not in cars:
                print("New car", car)
                cars.append(data['title'])
                page = requests.get(link).content
                psoup = BeautifulSoup(page, 'lxml')
                # print(psoup)
                attr = psoup.find_all('p', {'class': "attrgroup"})
                data['name'] = attr[0].find('span').text
                for span in attr[1].find_all('span'):
                    s = span.text.split(": ")
                    data[s[0]] = s[1]
                data['desc'] = psoup.find('section', {'id': 'postingbody'}).text.replace('QR Code Link to This Post',
                                                                                         '').strip() if psoup.find(
                    'section', {'id': 'postingbody'}) is not None else ""
                data['img'] = [x['href'] for x in psoup.find_all('a', {"class": "thumb"})]
                print(json.dumps(data, indent=4))
                kbb(data)
        time.sleep(monitor)


def kbb(data):
    with lock:
        driver = getChromeDriver()
        driver.get("https://www.kbb.com/whats-my-car-worth/")
        c = data['name']
        try:
            car = c.replace('-', ' ')
            # print(car)
            getElement(driver, '//select[@aria-label="Year"]/option[2]')
            year = Select(getElement(driver, '//select[@aria-label="Year"]'))
            year.select_by_value(car.split(' ')[0])
            # time.sleep(1)
            getElement(driver, '//select[@aria-label="Make"]/option[2]')
            make = Select(getElement(driver, '//select[@placeholder="Make"]'))
            if car.split(' ')[1].lower() not in [x.text for x in make.options[1:]]:
                make.select_by_visible_text(similar(" ".join(car.split(" ")[1:]), [x.text for x in make.options[1:]]))
            else:
                make.select_by_visible_text(car.split(' ')[1])
            time.sleep(1)
            getElement(driver, '//select[@aria-label="Model"]/option[2]')
            model = Select(getElement(driver, '//select[@placeholder="Model"]'))
            if car.split(' ')[2] not in [x.text for x in model.options]:
                model.select_by_visible_text(similar(" ".join(car.split(" ")[2:]), [x.text for x in model.options]))
            else:
                model.select_by_visible_text(car.split(' ')[2])
            time.sleep(1)
            data[
                'kbb_car'] = f"{year.first_selected_option.text} {make.first_selected_option.text} " \
                             f"{model.first_selected_option.text} "
            print("Car:", car, "\tSelected:", data['kbb_car'])
            sendkeys(driver, '//input[contains(@class,"mileage")]', data['odometer'])
            sendkeys(driver, '//input[contains(@class,"zipcode")]', '80016', True)
            click(driver, '//button[@data-lean-auto="vehiclePickerBtn"]')
            # click(driver, '//button[@data-lean-auto="categoryPickerButton"]')
            time.sleep(1)
            if "Which Category Is Your Vehicle?" in driver.page_source:
                click(driver,'//input[@name="group1"]/../div')
                time.sleep(1)
            if "Which Style Is Your Vehicle" in driver.page_source:
                click(driver, '//input[@id="0"]/../..')
                time.sleep(1)
            click(driver, '//button[@data-lean-auto="categoryPickerButton"]')

            try:
                click(driver, '//button[@title="No thanks"]')
            except:
                pass
            click(driver, '//div[contains(text(),"Price with standard equipment")]')
            click(driver, f'//div[contains(text(),"{data["paint color"].capitalize()}")]')
            click(driver, '//div[@data-lean-auto="fair"]')
            click(driver, '//button[@data-lean-auto="optionsNextButton"]')
            click(driver, '//button[@data-lean-auto="next-btn"]')
            while "offeroption" in driver.current_url:
                time.sleep(1)
            #
            # click(driver, '//button[@data-lean-auto="private-party"]')
            # getElement(driver, '//object[text()="Price Advisor"]')
            # while '{"type":"PP_Fair",' not in driver.page_source:
            #     time.sleep(1)
            print(driver.current_url)
            content = requests.get(driver.current_url.replace('pricetype=trade-in', 'pricetype=private-party')).content
            # print(content)
            soup = BeautifulSoup(content, 'lxml')
            for script in soup.find_all('script'):
                if "__SSR_SUCCESSFUL__" in str(script):
                    if testing:
                        print('__SSR_SUCCESSFUL__')
                    scr = \
                        json.loads(
                            script.string.replace("window.__SSR_SUCCESSFUL__ = true; window.__APOLLO_STATE__  = ", ""))[
                            '_INITIAL_QUERY']
                    print(json.dumps(scr, indent=4))
                    for key in scr.keys():
                        if "priceAdvisorQuery" in key:
                            if testing:
                                print('priceAdvisorQuery')
                            kbbprice = scr[key]["result"]["priceAdvisor"]["Data"]["APIData"]["vehicle"]["values"][-1][
                                'low']
                            print("KBB Price", kbbprice, "Price", data['price'])
                            if data['price'] < (kbbprice - 1500) or testing:
                                data['kbb_price'] = kbbprice
                                data['(kbb-1500) - price'] = (kbbprice - 1500) - data['price']
                                send(data)
                            break
                    break
        except:
            traceback.print_exc()
            send(data, "*Error*\n")


def send(data, msg=""):
    print(json.dumps(data, indent=4))
    for key in data.keys():
        if key != "img" and key != "desc":
            msg += f"\n{key}: {data[key]}"
    if "img" in data.keys() and len(data['img']) > 0:
        imgs = [InputMediaPhoto(data['img'][0], caption=msg)]
        imgs.extend([InputMediaPhoto(x) for x in data['img'][1:10]])
        updater.bot.send_media_group(chat_id=chat_id, media=imgs)
        updater.bot.send_message(chat_id=chat_id, text=data['desc'])

    else:
        updater.bot.send_message(chat_id=chat_id, text=msg)


def get(soup, tag, attrib, val):
    return soup.find(tag, {attrib: val})


def similar(car, options):
    # print('car', car)
    # print('option', options)
    data = {}
    for option in options:
        res = levenshtein.distance(car.lower(), option.lower())
        if option.lower() in car.lower():
            return option
        elif res not in data.keys():
            data[res] = option
            # print(data[res], option, res)
    # print(json.dumps(data, sort_keys=True, indent=4))
    return data[min(data.keys())]


def click(driver, xpath, js=False):
    time.sleep(1)
    if js:
        driver.execute_script("arguments[0].click();", getElement(driver, xpath))
    else:
        WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()


def getElement(driver, xpath):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))


def sendkeys(driver, xpath, keys, js=False):
    if js:
        driver.execute_script(f"arguments[0].value='{keys}';", getElement(driver, xpath))
    else:
        getElement(driver, xpath).send_keys(keys)


def getChromeDriver(proxy=None):
    options = webdriver.ChromeOptions()
    if debug:
        # print("Connecting existing Chrome for debugging...")
        options.debugger_address = "127.0.0.1:9222"
    else:
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
    if not images:
        # print("Turning off images to save bandwidth")
        options.add_argument("--blink-settings=imagesEnabled=false")
    if headless:
        # print("Going headless")
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080")
    if maximize:
        # print("Maximizing Chrome ")
        options.add_argument("--start-maximized")
    if proxy:
        # print(f"Adding proxy: {proxy}")
        options.add_argument(f"--proxy-server={proxy}")
    if incognito:
        # print("Going incognito")
        options.add_argument("--incognito")
    return webdriver.Chrome(options=options)


def getFirefoxDriver():
    options = webdriver.FirefoxOptions()
    if not images:
        # print("Turning off images to save bandwidth")
        options.set_preference("permissions.default.image", 2)
    if incognito:
        # print("Enabling incognito mode")
        options.set_preference("browser.privatebrowsing.autostart", True)
    if headless:
        # print("Hiding Firefox")
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080")
    return webdriver.Firefox(options)


def logo():
    os.system('color 0a')
    print("""
    _________               .__               .____    .__          __   
    \_   ___ \____________  |__| ____  ______ |    |   |__| _______/  |_ 
    /    \  \/\_  __ \__  \ |  |/ ___\/  ___/ |    |   |  |/  ___/\   __\\
    \     \____|  | \// __ \|  / /_/  >___ \  |    |___|  |\___ \  |  |  
     \______  /|__|  (____  /__\___  /____  > |_______ \__/____  > |__|  
            \/            \/  /_____/     \/          \/       \/        
=================================================================================
        CraigsList.com cars alert sender by fiverr.com/muhammadhassan7
=================================================================================
[+] Monitor craigslist without browser
[+] Send alert over Telegram
[+] Compare price with KBB
[+] 24/7 running...
_________________________________________________________________________________
""")


if __name__ == "__main__":
    main()
