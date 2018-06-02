
import re
import os
import sys
import pickle
import scrapy
import lxml.html
import urllib.parse
from collections import defaultdict
from scrapy.selector import Selector
from scrapy.http import HtmlResponse
from cssselect import GenericTranslator, SelectorError
from json import dumps, loads, JSONEncoder, JSONDecoder

class BliBliSpider(scrapy.Spider):
    name = "blibli"
    PAGE_LIMIT = 10
    output_path = 'output/blibli/'
    list_urls = ['https://www.blibli.com/coffee-maker/54650',
            'https://www.blibli.com/televisi/54650',
            'https://www.blibli.com/perangkat-kecantikan/54650',
            'https://www.blibli.com/perlengkapan-elektronik-dapur/54650',
            'https://www.blibli.com/microwave-dan-oven/54650',
            'https://www.blibli.com/pendingin-ruangan/54650',
            'https://www.blibli.com/elektronik-dapur/54650',
            'https://www.blibli.com/home-appliances/54650',
            'https://www.blibli.com/multimedia/53270',
            'https://www.blibli.com/media-penyimpanan/53270',
            'https://www.blibli.com/aksesoris-komputer/53270',
            'https://www.blibli.com/peralatan-gaming/53270',
            'https://www.blibli.com/scanner/53270',
            'https://www.blibli.com/printer-refill/53270',
            'https://www.blibli.com/wearable-gadget/54593',
            'https://www.blibli.com/handphone/54593',
            'https://www.blibli.com/aksesoris-handphone-tablet/54593',
            'https://www.blibli.com/tablet/54593'
            ]

    def as_python_object(self,dct):
        if '_python_object' in dct:
            return pickle.loads(str(dct['_python_object']))
        return dct

    def getselector(self,getter):
        try:
            expression = GenericTranslator().css_to_xpath(getter)
            return expression
        except SelectorError:
            self.logger.info('Invalid selector')
            return None

    def translatespecification(self,table):
        cleanr = re.compile('<.*?>')
        result = defaultdict(list)
        allrows = lxml.html.fromstring(table).cssselect('tr')
        for row in allrows:
            allcols = row.cssselect('td')
            label = re.sub(cleanr, '', allcols[0].text_content())
            value = re.sub(cleanr, '', allcols[1].text_content())
            value = value if value else None
            value = None if value == '-' else value
            result[label] = value
        return result

    def translateprice(self,price_info):
        cleanr = re.compile('<.*?>')
        diff_price = []

        labels = scrapy.Selector(text=price_info).xpath('//*[@class="product__detail-info-section--label"]/text()').extract()
        values = scrapy.Selector(text=price_info).xpath('//div[@class="product__detail-info-section--value price"]//span[@class="product__price"]//text()[normalize-space() and not(ancestor-or-self::span[@class="product__price-discount"])]').extract()

        elements = defaultdict(list)
        for (label,value) in zip(labels,values):
            label = ' '.join(re.sub(r'(?<!\n)\n(?![\n\t])', '',label.replace('\r', '')).split()) if label else None
            value = int(''.join([s for s in re.findall(r'\b\d+\b', value)])) if value else None
                       
            if label and value:
                elements[label] = value
            
        if(len(elements))>1:
            for key, value in elements.items():
                diff_price.append(value)

        if len(diff_price) > 1:
            elements['Diskon'] = round((abs(diff_price[0] - diff_price[1]))/diff_price[0] * 100,1)
        else:
            elements['Diskon'] = 0.0
        return elements

    def translatecode(self, produk_code):
        cleanr = re.compile('<.*?>')
        elements = defaultdict(list)
        for codes in produk_code:
            code_type = scrapy.Selector(text=codes).xpath('//span[@class="content__product-code--label"]/text()').extract_first()
            code_value = scrapy.Selector(text=codes).xpath('//span[@class="content__product-code--value"]/text()').extract_first()
            elements[code_type] = code_value
        return elements

    def translateshipping(self,shipping_option):
        cleanr = re.compile('<.*?>')
        result = defaultdict(list)
        for option in shipping_option:
            shipment = defaultdict(list)
            ship_name = scrapy.Selector(text=option).xpath('//div[@class="shipping__name"]/span/img').xpath('@alt').extract_first()
            ship_url = scrapy.Selector(text=option).xpath('//div[@class="shipping__name"]/span/img').xpath('@src').extract_first()
            price = scrapy.Selector(text=option).xpath('//div[@class="shipping__price"]/text()').extract_first()
            shipment['name'] = re.sub(cleanr, '', ship_name) if ship_name else None
            shipment['image'] = re.sub(cleanr, '', ship_url) if ship_url else None
            price = int(''.join([s for s in re.findall(r'\b\d+\b', price)])) if price else None
            shipment['price'] = price if price else 0
            if shipment['name'] and shipment['image']:
                result.update(shipment)
        return result

    def start_requests(self):
        self.logger.info('current working directory is : %s' % os.getcwd())
        
        for url in self.list_urls:
            proxy_meta = ''
            request = scrapy.Request(url=url, callback=self.parse)
            request.meta['proxy'] = proxy_meta
            request.meta['pages'] = 0
            yield request

    def parse_page(self, response):
        filename = response.meta['filepath']
        product = []
        cleanr = re.compile('<.*?>')
        product_details = defaultdict(list)
        selector = scrapy.Selector(text=response.body, type="html")
        product_details["brand"] = response.css('div.product__brand-name a span::text').extract_first()
        product_details["brand_image"] = response.css('div.product__brand-logo div img::attr(src)').extract_first()
        product_details["produk_url"] = response.meta['url_product']
        product_details["brand_link"] = response.css('div.product__brand-name a::attr(href)').extract_first()
        product_details["title"] = response.xpath('//*[@class="product__name-text"]/text()').extract_first()
        product_details["category"] = [e for e in response.xpath('//*[@class="breadcrumb__link"]/span/text()').extract() if e != 'Home']
        product_details["harga"] = self.translateprice(selector.xpath('//*[@class="product__detail-info-section"]').extract_first())
        product_details["produk_features"] = list(filter(lambda a: a != '',map(lambda e: ' '.join(re.sub(r'(?<!\n)\n(?![\n\t])', '',e).split()),response.css('.product__section-list ul li::text').extract())))
        product_details["produk_services"] = list(filter(lambda a: a != '',map(lambda e : ' '.join(re.sub(r'(?<!\n)\n(?![\n\t])', '',e).split()),response.css('.product__services ul li::text').extract())))
        desc = selector.css('div#product-tabs-area.product__tabs div.product__tabs--left div.tab.product-detail-tabs div.tab__container div.tab__section div.tab__section-content.content div.content--text div.content-description.content-item').extract_first()
        product_details["produk_description"] = re.sub(cleanr, '', desc)
        spec = selector.css('div#product-tabs-area.product__tabs div.product__tabs--left div.tab.product-detail-tabs div.tab__container div.tab__section div.tab__section-content.content div.content--text div.content-specification.content-item table.table').extract_first()
        product_details["produk_specification"] = self.translatespecification(spec) if spec else None  
        product_details["produk_code"] = self.translatecode(response.xpath('//ul[@class="content__product-code"]/li').extract())
        product_details["url_images"] = response.css('div.product__image-thumbnails--item img::attr(src)').extract()
        shipment = response.xpath('//*[@class="shipping__option"]').extract()
        product_details["shipping_option"] = self.translateshipping(shipment) if shipment else None
        location_merchant = response.xpath('//*[@class="location-name"]/text()').extract_first()
        product_details["merchant_location"] =  ' '.join(re.sub(r'(?<!\n)\n(?![\n\t])', '',location_merchant.replace('\r', '')).split()) if location_merchant else None
        product = product_details

        a = []

        directory = os.path.join(os.path.dirname(os.getcwd()),self.output_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        filename = os.path.join(directory,filename)
        if not os.path.isfile(filename):
            a.append(product)
            with open(filename, mode='w',encoding='utf-8') as f:
                f.write(dumps(a, indent=4,cls=PythonObjectEncoder))
        else:
            with open(filename) as feedsjson:
                feeds = loads(feedsjson.read(),object_hook=self.as_python_object)
            feeds.append(product)
            with open(filename, mode='w',encoding='utf-8') as f:
                f.write(dumps(feeds, indent=4,cls=PythonObjectEncoder))
        self.logger.info('Processed : %s' % product_details["title"])

    def parse(self, response):
        count_pages = response.meta['pages']
        if count_pages < self.PAGE_LIMIT:
            page = response.url.split("/")[-2]
            filename = 'produk-%s.json' % page
            list_url_product = response.css('a.single-product::attr(href)').extract()
            if list_url_product is not None:
                for url_product in list_url_product:                    
                    url = url_product
                    url_product = "http://192.168.99.100:8050/render.html?" + urllib.parse.urlencode({ 'url' : url_product})
                    product_request = scrapy.Request(url=url_product,callback=self.parse_page)
                    product_request.meta['proxy'] = ''
                    product_request.meta['dont_obey_robotstxt'] = True
                    product_request.meta['url_product'] = url
                    product_request.meta['filepath'] = filename
                    yield product_request
            self.log('Saved file %s' % filename)
            href = response.css('div.paging a#next::attr(onclick)').extract_first()
            if href is not None:
                count_pages = count_pages + 1
                href = re.findall("'([^' ]+)'",href)
                next_page = response.urljoin(href[0])                
                request = scrapy.Request(url=next_page, callback=self.parse)
                request.meta['proxy'] = response.meta['proxy']
                request.meta['pages'] = count_pages
                yield request

class PythonObjectEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (list, dict, str, int, float, bool, type(None))):
            return JSONEncoder.default(self, obj)
        return {'_python_object': pickle.dumps(obj)}